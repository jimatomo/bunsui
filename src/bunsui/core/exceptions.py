"""
Core exception classes for Bunsui.

This module contains the base exception classes and error handling utilities.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class BunsuiError(Exception):
    """Base exception class for all Bunsui errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.utcnow()
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', error_code='{self.error_code}', recoverable={self.recoverable})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "recoverable": self.recoverable,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class SessionError(BunsuiError):
    """Session related errors."""
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="SESSION_ERROR",
            recoverable=recoverable,
            context=context
        )
        self.session_id = session_id


class PipelineError(BunsuiError):
    """Pipeline related errors."""
    
    def __init__(
        self,
        message: str,
        pipeline_id: Optional[str] = None,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="PIPELINE_ERROR",
            recoverable=recoverable,
            context=context
        )
        self.pipeline_id = pipeline_id


class ConfigurationError(BunsuiError):
    """Configuration related errors."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            recoverable=False,
            context=context
        )
        self.config_key = config_key


class ValidationError(BunsuiError):
    """Data validation errors."""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            recoverable=False,
            context=context
        )
        self.field_name = field_name
        self.field_value = field_value 