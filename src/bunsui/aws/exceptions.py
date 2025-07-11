"""
AWS service integration exceptions.

This module contains custom exception classes for AWS service interactions.
"""

from typing import Dict, Any, Optional
from bunsui.core.exceptions import BunsuiError


class AWSError(BunsuiError):
    """Base exception for AWS service related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        service_name: str,
        operation_name: str,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, error_code, recoverable, context)
        self.service_name = service_name
        self.operation_name = operation_name
        self.original_error = original_error
    
    def __str__(self) -> str:
        return f"AWS {self.service_name} error in {self.operation_name}: {self.message}"


class AWSAuthenticationError(AWSError):
    """Authentication/Authorization errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="AWS_AUTH_ERROR",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=False,
            context=context,
            original_error=original_error
        )


class AWSThrottlingError(AWSError):
    """Rate limiting/throttling errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="AWS_THROTTLING_ERROR",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=True,
            context=context,
            original_error=original_error
        )
        self.retry_after = retry_after


class AWSServiceError(AWSError):
    """General AWS service errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        error_code: str,
        status_code: Optional[int] = None,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=f"AWS_SERVICE_ERROR_{error_code}",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=recoverable,
            context=context,
            original_error=original_error
        )
        self.status_code = status_code


class AWSConfigurationError(AWSError):
    """Configuration related errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="AWS_CONFIG_ERROR",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=False,
            context=context,
            original_error=original_error
        )


class AWSResourceNotFoundError(AWSError):
    """Resource not found errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        resource_type: str,
        resource_id: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="AWS_RESOURCE_NOT_FOUND",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=False,
            context=context,
            original_error=original_error
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class AWSTimeoutError(AWSError):
    """Request timeout errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation_name: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="AWS_TIMEOUT_ERROR",
            service_name=service_name,
            operation_name=operation_name,
            recoverable=True,
            context=context,
            original_error=original_error
        )
        self.timeout_seconds = timeout_seconds


# Exception mapping for common boto3 exceptions
BOTO3_EXCEPTION_MAP = {
    "NoCredentialsError": AWSAuthenticationError,
    "PartialCredentialsError": AWSAuthenticationError,
    "UnauthorizedOperation": AWSAuthenticationError,
    "AccessDenied": AWSAuthenticationError,
    "Throttling": AWSThrottlingError,
    "ThrottlingException": AWSThrottlingError,
    "TooManyRequestsException": AWSThrottlingError,
    "ResourceNotFound": AWSResourceNotFoundError,
    "ResourceNotFoundException": AWSResourceNotFoundError,
    "NoSuchBucket": AWSResourceNotFoundError,
    "NoSuchKey": AWSResourceNotFoundError,
    "ConnectTimeoutError": AWSTimeoutError,
    "ReadTimeoutError": AWSTimeoutError,
    "EndpointConnectionError": AWSServiceError,
    "ConnectionError": AWSServiceError,
} 