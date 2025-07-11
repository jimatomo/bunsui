"""
AWS client wrapper with retry logic and error handling.

This module provides a common wrapper for AWS services with 
built-in retry logic, error handling, and logging.
"""

import boto3
import logging
from typing import Any, Dict, Optional
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime, timedelta

from .exceptions import (
    AWSAuthenticationError, AWSConfigurationError, 
    AWSServiceError
)
from .retry import RetryConfig, retry_on_exception


logger = logging.getLogger(__name__)


class AWSClient:
    """
    Common AWS client wrapper with retry logic and error handling.
    
    This class provides a unified interface for AWS service interactions
    with built-in retry logic, error handling, and logging.
    """
    
    def __init__(
        self,
        service_name: str,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: int = 30,
        max_pool_connections: int = 50
    ):
        """
        Initialize AWS client.
        
        Args:
            service_name: AWS service name (e.g., 'dynamodb', 's3')
            region_name: AWS region name
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            aws_session_token: AWS session token
            profile_name: AWS profile name
            retry_config: Retry configuration
            timeout: Request timeout in seconds
            max_pool_connections: Maximum connection pool size
        """
        self.service_name = service_name
        self.region_name = region_name or boto3.Session().region_name or 'us-east-1'
        self.retry_config = retry_config or RetryConfig()
        
        # Create boto3 config
        self.config = Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            max_pool_connections=max_pool_connections,
            retries={'max_attempts': 0}  # We handle retries ourselves
        )
        
        # Session management
        self.session = self._create_session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            profile_name=profile_name
        )
        
        # Initialize client
        self._client = None
        self._client_created_at = None
        self._client_ttl = timedelta(hours=1)  # Refresh client hourly
        
        # Rate limiting
        self._last_request_time = datetime.min
        self._min_request_interval = timedelta(milliseconds=100)  # 10 RPS max
        
        logger.info(
            f"Initialized AWS client for {service_name} in region {self.region_name}",
            extra={
                "service_name": service_name,
                "region_name": self.region_name,
                "retry_config": self.retry_config.__dict__
            }
        )
    
    def _create_session(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None
    ) -> boto3.Session:
        """Create boto3 session with credentials."""
        try:
            if profile_name:
                session = boto3.Session(
                    profile_name=profile_name,
                    region_name=self.region_name
                )
            else:
                session = boto3.Session(
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    aws_session_token=aws_session_token,
                    region_name=self.region_name
                )
            
            # Test credentials
            sts_client = session.client('sts')
            identity = sts_client.get_caller_identity()
            
            logger.info(
                f"Authenticated as {identity.get('Arn', 'unknown')}",
                extra={
                    "account_id": identity.get('Account'),
                    "user_id": identity.get('UserId'),
                    "arn": identity.get('Arn')
                }
            )
            
            return session
            
        except NoCredentialsError as e:
            raise AWSAuthenticationError(
                message="No AWS credentials found",
                service_name=self.service_name,
                operation_name="create_session",
                original_error=e
            )
        except ClientError as e:
            raise AWSAuthenticationError(
                message=f"Failed to authenticate: {str(e)}",
                service_name=self.service_name,
                operation_name="create_session",
                original_error=e
            )
        except Exception as e:
            raise AWSConfigurationError(
                message=f"Failed to create session: {str(e)}",
                service_name=self.service_name,
                operation_name="create_session",
                original_error=e
            )
    
    @property
    def client(self):
        """Get or create boto3 client with automatic refresh."""
        now = datetime.utcnow()
        
        # Check if client needs refresh
        if (
            self._client is None or
            self._client_created_at is None or
            now - self._client_created_at > self._client_ttl
        ):
            try:
                self._client = self.session.client(
                    self.service_name,
                    region_name=self.region_name,
                    config=self.config
                )
                self._client_created_at = now
                
                logger.debug(
                    f"Created/refreshed boto3 client for {self.service_name}",
                    extra={
                        "service_name": self.service_name,
                        "region_name": self.region_name
                    }
                )
                
            except Exception as e:
                raise AWSConfigurationError(
                    message=f"Failed to create client: {str(e)}",
                    service_name=self.service_name,
                    operation_name="create_client",
                    original_error=e
                )
        
        return self._client
    
    def get_resource(self, service_name: str):
        """Get boto3 resource."""
        try:
            return self.session.resource(
                service_name,
                region_name=self.region_name,
                config=self.config
            )
        except Exception as e:
            raise AWSConfigurationError(
                message=f"Failed to create resource: {str(e)}",
                service_name=service_name,
                operation_name="create_resource",
                original_error=e
            )
    
    def _rate_limit(self) -> None:
        """Apply rate limiting to requests."""
        now = datetime.utcnow()
        time_since_last_request = now - self._last_request_time
        
        if time_since_last_request < self._min_request_interval:
            sleep_time = (self._min_request_interval - time_since_last_request).total_seconds()
            if sleep_time > 0:
                import time
                time.sleep(sleep_time)
        
        self._last_request_time = datetime.utcnow()
    
    def call_api(
        self,
        operation_name: str,
        **kwargs
    ) -> Any:
        """
        Call AWS API with retry logic and error handling.
        
        Args:
            operation_name: AWS API operation name
            **kwargs: Operation parameters
            
        Returns:
            API response
            
        Raises:
            AWSError: If API call fails
        """
        @retry_on_exception(
            config=self.retry_config,
            service_name=self.service_name,
            operation_name=operation_name
        )
        def _call_api():
            # Apply rate limiting
            self._rate_limit()
            
            # Get operation method
            try:
                operation = getattr(self.client, operation_name)
            except AttributeError:
                raise AWSServiceError(
                    message=f"Operation '{operation_name}' not found on {self.service_name} client",
                    service_name=self.service_name,
                    operation_name=operation_name,
                    error_code="OPERATION_NOT_FOUND"
                )
            
            # Execute operation
            start_time = datetime.utcnow()
            try:
                response = operation(**kwargs)
                
                # Log successful call
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.debug(
                    f"API call successful: {self.service_name}.{operation_name}",
                    extra={
                        "service_name": self.service_name,
                        "operation_name": operation_name,
                        "duration_seconds": duration,
                        "parameters": self._sanitize_params(kwargs)
                    }
                )
                
                return response
                
            except Exception as e:
                # Log failed call
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.error(
                    f"API call failed: {self.service_name}.{operation_name}",
                    extra={
                        "service_name": self.service_name,
                        "operation_name": operation_name,
                        "duration_seconds": duration,
                        "parameters": self._sanitize_params(kwargs),
                        "error": str(e)
                    }
                )
                raise
        
        return _call_api()
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize parameters for logging (remove sensitive data).
        
        Args:
            params: Original parameters
            
        Returns:
            Sanitized parameters
        """
        sensitive_keys = {
            'password', 'secret', 'token', 'key', 'credential',
            'auth', 'private', 'confidential'
        }
        
        sanitized = {}
        for key, value in params.items():
            key_lower = key.lower()
            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_params(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information and capabilities.
        
        Returns:
            Service information
        """
        return {
            "service_name": self.service_name,
            "region_name": self.region_name,
            "client_version": self.client._service_model.api_version,
            "operations": list(self.client._service_model.operation_names),
            "retry_config": self.retry_config.__dict__
        }
    
    def __str__(self) -> str:
        return f"AWSClient(service={self.service_name}, region={self.region_name})"
    
    def __repr__(self) -> str:
        return f"AWSClient(service_name='{self.service_name}', region_name='{self.region_name}')"


class AWSClientFactory:
    """Factory for creating AWS clients with consistent configuration."""
    
    def __init__(
        self,
        default_region: Optional[str] = None,
        default_retry_config: Optional[RetryConfig] = None,
        default_timeout: int = 30,
        default_profile: Optional[str] = None
    ):
        """
        Initialize client factory.
        
        Args:
            default_region: Default AWS region
            default_retry_config: Default retry configuration
            default_timeout: Default request timeout
            default_profile: Default AWS profile
        """
        self.default_region = default_region
        self.default_retry_config = default_retry_config or RetryConfig()
        self.default_timeout = default_timeout
        self.default_profile = default_profile
        
        # Client cache
        self._clients: Dict[str, AWSClient] = {}
    
    def create_client(
        self,
        service_name: str,
        region_name: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: Optional[int] = None,
        profile_name: Optional[str] = None,
        cache_client: bool = True
    ) -> AWSClient:
        """
        Create AWS client with factory defaults.
        
        Args:
            service_name: AWS service name
            region_name: AWS region name
            retry_config: Retry configuration
            timeout: Request timeout
            profile_name: AWS profile name
            cache_client: Whether to cache client
            
        Returns:
            AWS client
        """
        # Use defaults if not provided
        region_name = region_name or self.default_region
        retry_config = retry_config or self.default_retry_config
        timeout = timeout or self.default_timeout
        profile_name = profile_name or self.default_profile
        
        # Create cache key
        cache_key = f"{service_name}_{region_name}_{profile_name}"
        
        # Check cache
        if cache_client and cache_key in self._clients:
            return self._clients[cache_key]
        
        # Create new client
        client = AWSClient(
            service_name=service_name,
            region_name=region_name,
            retry_config=retry_config,
            timeout=timeout,
            profile_name=profile_name
        )
        
        # Cache if requested
        if cache_client:
            self._clients[cache_key] = client
        
        return client
    
    def get_cached_clients(self) -> Dict[str, AWSClient]:
        """Get all cached clients."""
        return self._clients.copy()
    
    def clear_cache(self) -> None:
        """Clear client cache."""
        self._clients.clear()


# Global factory instance
client_factory = AWSClientFactory() 