"""
Retry logic for AWS API calls.

This module implements exponential backoff and retry logic for AWS service calls.
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps
from dataclasses import dataclass

from botocore.exceptions import ClientError
from .exceptions import (
    AWSError, AWSThrottlingError, AWSTimeoutError, AWSServiceError, 
    BOTO3_EXCEPTION_MAP
)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        AWSThrottlingError,
        AWSTimeoutError,
    )


class RetryableError(Exception):
    """Marker exception for retryable errors."""
    pass


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        backoff_factor: Exponential backoff factor
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter
        
    Returns:
        Delay in seconds
    """
    delay = base_delay * (backoff_factor ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        # Add random jitter (±25% of delay)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, delay)  # Ensure minimum delay
    
    return delay


def convert_boto3_exception(
    error: Exception,
    service_name: str,
    operation_name: str
) -> AWSError:
    """
    Convert boto3 exception to Bunsui AWS exception.
    
    Args:
        error: Original boto3 exception
        service_name: AWS service name
        operation_name: Operation name
        
    Returns:
        Converted AWSError
    """
    if isinstance(error, ClientError):
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        status_code = error.response['ResponseMetadata']['HTTPStatusCode']
        
        # Map known error codes to specific exceptions
        exception_class = BOTO3_EXCEPTION_MAP.get(error_code, AWSServiceError)
        
        if exception_class == AWSThrottlingError:
            return AWSThrottlingError(
                message=error_message,
                service_name=service_name,
                operation_name=operation_name,
                context={"status_code": status_code, "error_code": error_code},
                original_error=error
            )
        elif exception_class == AWSTimeoutError:
            return AWSTimeoutError(
                message=error_message,
                service_name=service_name,
                operation_name=operation_name,
                timeout_seconds=30,  # Default timeout
                context={"status_code": status_code, "error_code": error_code},
                original_error=error
            )
        else:
            return exception_class(
                message=error_message,
                service_name=service_name,
                operation_name=operation_name,
                error_code=error_code,
                status_code=status_code,
                recoverable=error_code in ["InternalError", "ServiceUnavailable"],
                context={"status_code": status_code, "error_code": error_code},
                original_error=error
            )
    else:
        # Handle other types of exceptions
        error_type = type(error).__name__
        exception_class = BOTO3_EXCEPTION_MAP.get(error_type, AWSServiceError)
        
        return exception_class(
            message=str(error),
            service_name=service_name,
            operation_name=operation_name,
            error_code=error_type,
            context={"error_type": error_type},
            original_error=error
        )


def retry_on_exception(
    config: Optional[RetryConfig] = None,
    service_name: str = "unknown",
    operation_name: str = "unknown"
) -> Callable:
    """
    Decorator to add retry logic to functions.
    
    Args:
        config: Retry configuration
        service_name: AWS service name for error handling
        operation_name: Operation name for error handling
        
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Convert boto3 exceptions to Bunsui exceptions
                    bunsui_error = convert_boto3_exception(e, service_name, operation_name)
                    last_exception = bunsui_error
                    
                    # Check if error is retryable
                    is_retryable = (
                        bunsui_error.recoverable or
                        any(isinstance(bunsui_error, exc_type) for exc_type in config.retryable_exceptions)
                    )
                    
                    if not is_retryable or attempt == config.max_attempts - 1:
                        logger.error(
                            f"Non-retryable error or max attempts reached: {bunsui_error}",
                            extra={
                                "service_name": service_name,
                                "operation_name": operation_name,
                                "attempt": attempt + 1,
                                "max_attempts": config.max_attempts
                            }
                        )
                        raise bunsui_error
                    
                    # Calculate delay for next attempt
                    delay = exponential_backoff(
                        attempt,
                        config.base_delay,
                        config.backoff_factor,
                        config.max_delay,
                        config.jitter
                    )
                    
                    logger.warning(
                        f"Retryable error occurred, attempt {attempt + 1}/{config.max_attempts}: {bunsui_error}",
                        extra={
                            "service_name": service_name,
                            "operation_name": operation_name,
                            "attempt": attempt + 1,
                            "max_attempts": config.max_attempts,
                            "delay": delay,
                            "error": str(bunsui_error)
                        }
                    )
                    
                    # Handle throttling with respect to retry_after
                    if isinstance(bunsui_error, AWSThrottlingError) and bunsui_error.retry_after:
                        delay = max(delay, bunsui_error.retry_after)
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception is not None:
                raise last_exception
            else:
                raise AWSServiceError(
                    message="Unexpected error in retry logic",
                    service_name=service_name,
                    operation_name=operation_name,
                    error_code="RETRY_LOGIC_ERROR"
                )
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for AWS API calls.
    
    Prevents cascading failures by temporarily stopping calls
    when error rate exceeds threshold.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = AWSError
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker pattern.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise AWSServiceError(
                    message="Circuit breaker is open",
                    service_name="circuit-breaker",
                    operation_name="call",
                    error_code="CIRCUIT_BREAKER_OPEN",
                    recoverable=True
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures",
                extra={
                    "failure_count": self.failure_count,
                    "failure_threshold": self.failure_threshold
                }
            )


def create_retry_decorator(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    service_name: str = "unknown",
    operation_name: str = "unknown"
) -> Callable:
    """
    Create a retry decorator with specified configuration.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Exponential backoff factor
        jitter: Whether to add random jitter
        service_name: AWS service name
        operation_name: Operation name
        
    Returns:
        Retry decorator
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter
    )
    
    return retry_on_exception(config, service_name, operation_name) 