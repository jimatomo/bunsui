"""
Session management business logic.

This module provides the SessionManager class for handling
high-level session operations and lifecycle management.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable
from uuid import uuid4

from ..models.session import SessionMetadata, SessionStatus, Checkpoint, CheckpointType
from .repository import SessionRepository
from ...aws.client import AWSClient
from ...core.exceptions import SessionError, ValidationError


class SessionManager:
    """
    High-level session management with business logic.
    
    This class provides the main interface for session operations,
    orchestrating between repositories and implementing business rules.
    """
    
    def __init__(self, aws_client: AWSClient, table_name: str = "bunsui-sessions"):
        """
        Initialize the session manager.
        
        Args:
            aws_client: AWS client instance
            table_name: Name of the DynamoDB table for sessions
        """
        self.aws_client = aws_client
        self.repository = SessionRepository(aws_client, table_name)
        self._status_callbacks: Dict[SessionStatus, List[Callable]] = {}
    
    def create_session(
        self,
        pipeline_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        total_steps: int = 1,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> SessionMetadata:
        """
        Create a new session.
        
        Args:
            pipeline_id: ID of the pipeline to run
            metadata: Optional metadata for the session
            total_steps: Total number of steps in the pipeline
            session_id: Optional specific session ID (generated if not provided)
            
        Returns:
            Created session metadata
            
        Raises:
            SessionError: If session creation fails
            ValidationError: If parameters are invalid
        """
        if not pipeline_id:
            raise ValidationError("Pipeline ID is required")
        
        if total_steps < 1:
            raise ValidationError("Total steps must be at least 1")
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid4())
        
        # Create session metadata
        session = SessionMetadata(
            session_id=session_id,
            pipeline_id=pipeline_id,
            status=SessionStatus.CREATED,
            total_jobs=total_steps,
            completed_jobs=0,
            failed_jobs=0,
            configuration=metadata or {},
            pipeline_name=None,
            started_at=None,
            completed_at=None,
            execution_arn=None,
            execution_name=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            max_retries=3,
            user_id=user_id,
            user_name=user_name,
            environment=None,
            region=None
        )
        
        # Save to repository
        created_session = self.repository.create_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(created_session.status, created_session)
        
        return created_session
    
    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session metadata if found, None otherwise
        """
        return self.repository.get_session(session_id)
    
    def start_session(self, session_id: str) -> SessionMetadata:
        """
        Start a pending session.
        
        Args:
            session_id: Session ID to start
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session cannot be started
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate session can be started
        if session.status not in [SessionStatus.CREATED, SessionStatus.QUEUED]:
            raise SessionError(f"Cannot start session in {session.status.value} state")
        
        # Transition through proper states
        if session.status == SessionStatus.CREATED:
            session.transition_to(SessionStatus.QUEUED)
        
        # Now transition to running
        session.transition_to(SessionStatus.RUNNING)
        
        # Add checkpoint
        session.add_checkpoint(
            checkpoint_type=CheckpointType.MILESTONE,
            job_id="session",
            state_data={"message": "Session started"},
            message="Session started"
        )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(updated_session.status, updated_session)
        
        return updated_session
    
    def update_progress(
        self,
        session_id: str,
        current_step: int,
        step_name: Optional[str] = None,
        step_data: Optional[Dict[str, Any]] = None
    ) -> SessionMetadata:
        """
        Update session progress.
        
        Args:
            session_id: Session ID to update
            current_step: Current step number
            step_name: Name of the current step
            step_data: Optional data for the step
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session update fails
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate progress
        if current_step < 0 or current_step > session.total_jobs:
            raise ValidationError(f"Invalid step number: {current_step}")
        
        # Update progress
        session.update_progress(current_step, session.failed_jobs)
        
        # Add checkpoint if step completed
        if current_step > session.completed_jobs:
            session.add_checkpoint(
                checkpoint_type=CheckpointType.MILESTONE,
                job_id=step_name or f"step_{current_step}",
                state_data=step_data or {},
                message=f"Step {current_step} completed"
            )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        return updated_session
    
    def complete_session(
        self,
        session_id: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> SessionMetadata:
        """
        Complete a session.
        
        Args:
            session_id: Session ID to complete
            success: Whether the session completed successfully
            error_message: Optional error message if failed
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session completion fails
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate session can be completed
        if session.status not in [SessionStatus.RUNNING, SessionStatus.PAUSED]:
            raise SessionError(f"Cannot complete session in {session.status.value} state")
        
        # Update session status
        if success:
            session.transition_to(SessionStatus.COMPLETED)
        else:
            session.set_error(error_message or "Session failed")
        
        # Add final checkpoint
        session.add_checkpoint(
            checkpoint_type=CheckpointType.MILESTONE,
            job_id="session",
            state_data={
                "success": success,
                "error_message": error_message,
                "total_runtime": session.get_duration() or 0
            },
            message="Session completed" if success else "Session failed"
        )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(updated_session.status, updated_session)
        
        return updated_session
    
    def pause_session(self, session_id: str) -> SessionMetadata:
        """
        Pause a running session.
        
        Args:
            session_id: Session ID to pause
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session cannot be paused
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate session can be paused
        if session.status != SessionStatus.RUNNING:
            raise SessionError(f"Cannot pause session in {session.status.value} state")
        
        # Update session status
        session.transition_to(SessionStatus.PAUSED)
        
        # Add checkpoint
        session.add_checkpoint(
            checkpoint_type=CheckpointType.MILESTONE,
            job_id="session",
            state_data={"message": "Session paused"},
            message="Session paused"
        )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(updated_session.status, updated_session)
        
        return updated_session
    
    def resume_session(self, session_id: str) -> SessionMetadata:
        """
        Resume a paused session.
        
        Args:
            session_id: Session ID to resume
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session cannot be resumed
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate session can be resumed
        if session.status != SessionStatus.PAUSED:
            raise SessionError(f"Cannot resume session in {session.status.value} state")
        
        # Update session status
        session.transition_to(SessionStatus.RUNNING)
        
        # Add checkpoint
        session.add_checkpoint(
            checkpoint_type=CheckpointType.MILESTONE,
            job_id="session",
            state_data={"message": "Session resumed"},
            message="Session resumed"
        )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(updated_session.status, updated_session)
        
        return updated_session
    
    def cancel_session(self, session_id: str) -> SessionMetadata:
        """
        Cancel a session.
        
        Args:
            session_id: Session ID to cancel
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session cannot be cancelled
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        # Validate session can be cancelled
        if session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED]:
            raise SessionError(f"Cannot cancel session in {session.status.value} state")
        
        # Update session status
        session.transition_to(SessionStatus.CANCELLED)
        
        # Add checkpoint
        session.add_checkpoint(
            checkpoint_type=CheckpointType.MILESTONE,
            job_id="session",
            state_data={"message": "Session cancelled"},
            message="Session cancelled"
        )
        
        # Save changes
        updated_session = self.repository.update_session(session)
        
        # Trigger status callbacks
        self._trigger_status_callbacks(updated_session.status, updated_session)
        
        return updated_session
    
    def list_sessions(
        self,
        pipeline_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        limit: int = 100
    ) -> List[SessionMetadata]:
        """
        List sessions with optional filtering.
        
        Args:
            pipeline_id: Filter by pipeline ID
            status: Filter by session status
            limit: Maximum number of sessions to return
            
        Returns:
            List of session metadata
        """
        return self.repository.list_sessions(pipeline_id, status, limit)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted, False if not found
            
        Raises:
            SessionError: If session cannot be deleted
        """
        session = self.get_session(session_id)
        if session and session.status == SessionStatus.RUNNING:
            raise SessionError("Cannot delete running session")
        
        return self.repository.delete_session(session_id)
    
    def get_session_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """
        Get all checkpoints for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of checkpoints
        """
        return self.repository.get_session_checkpoints(session_id)
    
    def add_checkpoint(
        self,
        session_id: str,
        checkpoint_type: CheckpointType,
        step_name: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a checkpoint to a session.
        
        Args:
            session_id: Session ID
            checkpoint_type: Type of checkpoint
            step_name: Name of the step
            data: Optional checkpoint data
            metadata: Optional checkpoint metadata
            
        Returns:
            True if checkpoint was added successfully
        """
        checkpoint = Checkpoint(
            checkpoint_id=str(uuid4()),
            checkpoint_type=checkpoint_type,
            job_id=step_name,
            operation_id=None,
            created_at=datetime.now(timezone.utc),
            state_data=data or {},
            message=metadata.get("message") if metadata else None
        )
        
        return self.repository.add_checkpoint(session_id, checkpoint)
    
    def register_status_callback(self, status: SessionStatus, callback: Callable[[SessionMetadata], None]) -> None:
        """
        Register a callback for session status changes.
        
        Args:
            status: Session status to watch
            callback: Callback function to call
        """
        if status not in self._status_callbacks:
            self._status_callbacks[status] = []
        self._status_callbacks[status].append(callback)
    
    def _trigger_status_callbacks(self, status: SessionStatus, session: SessionMetadata) -> None:
        """
        Trigger callbacks for a session status change.
        
        Args:
            status: Session status
            session: Session metadata
        """
        if status in self._status_callbacks:
            for callback in self._status_callbacks[status]:
                try:
                    callback(session)
                except Exception as e:
                    # Log error but don't let callback failures break the flow
                    print(f"Warning: Status callback failed: {e}")
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session statistics
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(f"Session {session_id} not found")
        
        stats = {
            "session_id": session.session_id,
            "pipeline_id": session.pipeline_id,
            "status": session.status.value,
            "progress": {
                "total_jobs": session.total_jobs,
                "completed_jobs": session.completed_jobs,
                "failed_jobs": session.failed_jobs,
                "completion_percentage": session.get_progress_percentage()
            },
            "checkpoints_count": len(session.checkpoints),
            "configuration": session.configuration
        }
        
        # Add timing information if available
        if session.started_at:
            stats["start_time"] = session.started_at.isoformat()
            
            if session.completed_at:
                stats["end_time"] = session.completed_at.isoformat()
                stats["total_runtime_seconds"] = session.get_duration() or 0
            else:
                stats["current_runtime_seconds"] = session.get_duration() or 0
        
        return stats 