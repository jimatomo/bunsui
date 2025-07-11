"""
Session model for pipeline execution management.

This module contains the Session model that manages pipeline execution lifecycle,
state transitions, and metadata storage.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field, field_validator

from ..exceptions import SessionError, ValidationError


class SessionStatus(str, Enum):
    """Session status enumeration."""
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class CheckpointType(str, Enum):
    """Checkpoint type enumeration."""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    ERROR = "error"
    MILESTONE = "milestone"


@dataclass
class Checkpoint:
    """Checkpoint data for session recovery."""
    checkpoint_id: str
    checkpoint_type: CheckpointType
    job_id: str
    operation_id: Optional[str]
    created_at: datetime
    state_data: Dict[str, Any]
    message: Optional[str] = None
    
    def __post_init__(self):
        """Validate checkpoint data."""
        if not self.checkpoint_id:
            self.checkpoint_id = str(uuid.uuid4())
        
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create checkpoint from dictionary."""
        return cls(**data)


class SessionMetadata(BaseModel):
    """Session metadata model."""
    
    # Core identification
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = Field(..., description="Pipeline identifier")
    pipeline_name: Optional[str] = Field(None, description="Pipeline name")
    
    # Status and lifecycle
    status: SessionStatus = Field(default=SessionStatus.CREATED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    
    # Execution details
    execution_arn: Optional[str] = Field(None, description="Step Functions execution ARN")
    execution_name: Optional[str] = Field(None, description="Step Functions execution name")
    
    # Progress tracking
    total_jobs: int = Field(0, ge=0)
    completed_jobs: int = Field(0, ge=0)
    failed_jobs: int = Field(0, ge=0)
    
    # Configuration
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    
    # Error handling
    error_message: Optional[str] = Field(None)
    error_code: Optional[str] = Field(None)
    retry_count: int = Field(0, ge=0)
    max_retries: int = Field(3, ge=0)
    
    # Checkpoints
    checkpoints: List[Checkpoint] = Field(default_factory=list)
    
    # User context
    user_id: Optional[str] = Field(None)
    user_name: Optional[str] = Field(None)
    
    # Environment
    environment: Optional[str] = Field(None)
    region: Optional[str] = Field(None)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate session status."""
        if isinstance(v, str):
            try:
                return SessionStatus(v)
            except ValueError:
                raise ValidationError(
                    message=f"Invalid session status: {v}",
                    field_name="status",
                    field_value=v
                )
        return v
    
    @field_validator('updated_at', mode='before')
    @classmethod
    def set_updated_at(cls, v):
        """Always update the updated_at timestamp."""
        return datetime.utcnow()
    
    def add_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        job_id: str,
        state_data: Dict[str, Any],
        operation_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> Checkpoint:
        """
        Add a checkpoint to the session.
        
        Args:
            checkpoint_type: Type of checkpoint
            job_id: Job identifier
            state_data: State data for recovery
            operation_id: Operation identifier (optional)
            message: Optional message
            
        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            checkpoint_type=checkpoint_type,
            job_id=job_id,
            operation_id=operation_id,
            created_at=datetime.utcnow(),
            state_data=state_data,
            message=message
        )
        
        self.checkpoints.append(checkpoint)
        return checkpoint
    
    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get the latest checkpoint."""
        if not self.checkpoints:
            return None
        return max(self.checkpoints, key=lambda c: c.created_at)
    
    def get_checkpoints_by_job(self, job_id: str) -> List[Checkpoint]:
        """Get all checkpoints for a specific job."""
        return [c for c in self.checkpoints if c.job_id == job_id]
    
    def update_progress(self, completed_jobs: int, failed_jobs: int) -> None:
        """Update progress counters."""
        self.completed_jobs = completed_jobs
        self.failed_jobs = failed_jobs
        self.updated_at = datetime.utcnow()
    
    def set_error(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Set error information."""
        self.error_message = error_message
        self.error_code = error_code
        self.status = SessionStatus.FAILED
        self.updated_at = datetime.utcnow()
    
    def clear_error(self) -> None:
        """Clear error information."""
        self.error_message = None
        self.error_code = None
        self.updated_at = datetime.utcnow()
    
    def is_terminal_state(self) -> bool:
        """Check if session is in a terminal state."""
        return self.status in {
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
            SessionStatus.TIMEOUT
        }
    
    def is_running_state(self) -> bool:
        """Check if session is in a running state."""
        return self.status in {
            SessionStatus.QUEUED,
            SessionStatus.RUNNING
        }
    
    def can_transition_to(self, new_status: SessionStatus) -> bool:
        """
        Check if session can transition to new status.
        
        Args:
            new_status: Target status
            
        Returns:
            True if transition is allowed
        """
        # Define allowed transitions
        transitions = {
            SessionStatus.CREATED: {
                SessionStatus.QUEUED,
                SessionStatus.CANCELLED
            },
            SessionStatus.QUEUED: {
                SessionStatus.RUNNING,
                SessionStatus.CANCELLED
            },
            SessionStatus.RUNNING: {
                SessionStatus.PAUSED,
                SessionStatus.COMPLETED,
                SessionStatus.FAILED,
                SessionStatus.CANCELLED,
                SessionStatus.TIMEOUT
            },
            SessionStatus.PAUSED: {
                SessionStatus.RUNNING,
                SessionStatus.CANCELLED
            },
            SessionStatus.COMPLETED: set(),  # Terminal state
            SessionStatus.FAILED: {
                SessionStatus.QUEUED,  # Retry
                SessionStatus.CANCELLED
            },
            SessionStatus.CANCELLED: set(),  # Terminal state
            SessionStatus.TIMEOUT: {
                SessionStatus.QUEUED,  # Retry
                SessionStatus.CANCELLED
            }
        }
        
        return new_status in transitions.get(self.status, set())
    
    def transition_to(self, new_status: SessionStatus, message: Optional[str] = None) -> None:
        """
        Transition session to new status.
        
        Args:
            new_status: Target status
            message: Optional transition message
            
        Raises:
            SessionError: If transition is not allowed
        """
        if not self.can_transition_to(new_status):
            raise SessionError(
                message=f"Cannot transition from {self.status} to {new_status}",
                session_id=self.session_id
            )
        
        # Update timestamps based on status
        now = datetime.utcnow()
        if new_status == SessionStatus.RUNNING and self.started_at is None:
            self.started_at = now
        elif new_status in {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED, SessionStatus.TIMEOUT}:
            self.completed_at = now
        
        self.status = new_status
        self.updated_at = now
        
        # Add checkpoint for important transitions
        if new_status in {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED}:
            self.add_checkpoint(
                checkpoint_type=CheckpointType.MILESTONE,
                job_id="session",
                state_data={"status": new_status.value},
                message=message or f"Session transitioned to {new_status.value}"
            )
    
    def get_duration(self) -> Optional[float]:
        """Get session duration in seconds."""
        if self.started_at is None:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    def get_progress_percentage(self) -> float:
        """Get completion percentage."""
        if self.total_jobs == 0:
            return 0.0
        return (self.completed_jobs / self.total_jobs) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        data = self.dict()
        
        # Convert datetime objects to ISO format
        for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
            if data[field] is not None:
                data[field] = data[field].isoformat()
        
        # Convert checkpoints
        data['checkpoints'] = [c.to_dict() for c in self.checkpoints]
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionMetadata':
        """Create session from dictionary."""
        # Convert datetime fields
        for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
            if data.get(field) is not None and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        
        # Convert checkpoints
        if 'checkpoints' in data:
            data['checkpoints'] = [
                Checkpoint.from_dict(c) if isinstance(c, dict) else c
                for c in data['checkpoints']
            ]
        
        return cls(**data)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        arbitrary_types_allowed = True


class Session(SessionMetadata):
    """Session model for pipeline execution management."""
    
    def __init__(self, **data):
        """Initialize session with default values."""
        super().__init__(**data)
    
    @property
    def progress(self) -> float:
        """Get progress percentage."""
        return self.get_progress_percentage()
    
    def dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return self.to_dict()
    
    @classmethod
    def create(
        cls,
        pipeline_id: str,
        user_id: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> 'Session':
        """Create a new session."""
        return cls(
            pipeline_id=pipeline_id,
            user_id=user_id,
            pipeline_name=pipeline_name,
            configuration=configuration or {},
            tags=tags or {},
            status=SessionStatus.CREATED
        ) 