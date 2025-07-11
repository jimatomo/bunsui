"""
Tests for session management module.

This module contains tests for session models, repository, and manager.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from src.bunsui.core.models.session import SessionMetadata, SessionStatus, Checkpoint, CheckpointType
from src.bunsui.core.session.manager import SessionManager
from src.bunsui.core.session.repository import SessionRepository
from src.bunsui.core.exceptions import SessionError, ValidationError
from src.bunsui.aws.client import AWSClient


class TestSessionMetadata:
    """Test SessionMetadata model."""
    
    def test_session_creation(self):
        """Test session metadata creation."""
        session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.PENDING,
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        
        assert session.session_id == "test-session"
        assert session.pipeline_id == "test-pipeline"
        assert session.status == SessionStatus.PENDING
        assert session.progress.total_steps == 5
        assert session.checkpoints == []
        assert session.metadata == {}
    
    def test_session_validation(self):
        """Test session validation."""
        with pytest.raises(ValidationError):
            SessionMetadata(
                session_id="",  # Empty session ID should fail
                pipeline_id="test-pipeline",
                status=SessionStatus.PENDING,
                progress=SessionMetadata.Progress(
                    current_step=0,
                    total_steps=5,
                    completed_steps=0,
                    failed_steps=0
                )
            )
    
    def test_session_state_transitions(self):
        """Test session state transitions."""
        session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.PENDING,
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        
        # Test valid transition
        assert session.can_transition_to(SessionStatus.RUNNING)
        
        # Test invalid transition
        assert not session.can_transition_to(SessionStatus.COMPLETED)


class TestSessionRepository:
    """Test SessionRepository class."""
    
    @pytest.fixture
    def mock_aws_client(self):
        """Create mock AWS client."""
        client = Mock(spec=AWSClient)
        mock_resource = Mock()
        mock_table = Mock()
        mock_resource.Table.return_value = mock_table
        client.get_resource.return_value = mock_resource
        return client
    
    @pytest.fixture
    def repository(self, mock_aws_client):
        """Create repository instance."""
        return SessionRepository(mock_aws_client)
    
    def test_repository_initialization(self, mock_aws_client):
        """Test repository initialization."""
        repo = SessionRepository(mock_aws_client)
        assert repo.aws_client == mock_aws_client
        assert repo.table_name == "bunsui-sessions"
        mock_aws_client.get_resource.assert_called_once_with('dynamodb')
    
    def test_create_session(self, repository):
        """Test session creation."""
        session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.PENDING,
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        
        # Mock DynamoDB response
        repository.table.put_item.return_value = {}
        
        result = repository.create_session(session)
        
        assert result.session_id == "test-session"
        assert result.created_at is not None
        assert result.updated_at is not None
        repository.table.put_item.assert_called_once()
    
    def test_get_session(self, repository):
        """Test session retrieval."""
        # Mock DynamoDB response
        repository.table.get_item.return_value = {
            'Item': {
                'session_id': 'test-session',
                'pipeline_id': 'test-pipeline',
                'status': 'PENDING',
                'start_time': None,
                'end_time': None,
                'error_message': None,
                'metadata': {},
                'progress': {
                    'current_step': 0,
                    'total_steps': 5,
                    'completed_steps': 0,
                    'failed_steps': 0
                },
                'checkpoints': [],
                'created_at': '2024-01-01T00:00:00+00:00',
                'updated_at': '2024-01-01T00:00:00+00:00'
            }
        }
        
        result = repository.get_session("test-session")
        
        assert result is not None
        assert result.session_id == "test-session"
        assert result.pipeline_id == "test-pipeline"
        assert result.status == SessionStatus.PENDING
        repository.table.get_item.assert_called_once_with(
            Key={'session_id': 'test-session'}
        )
    
    def test_get_session_not_found(self, repository):
        """Test session retrieval when not found."""
        repository.table.get_item.return_value = {}
        
        result = repository.get_session("non-existent")
        
        assert result is None


class TestSessionManager:
    """Test SessionManager class."""
    
    @pytest.fixture
    def mock_aws_client(self):
        """Create mock AWS client."""
        return Mock(spec=AWSClient)
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return Mock(spec=SessionRepository)
    
    @pytest.fixture
    def manager(self, mock_aws_client, mock_repository):
        """Create session manager instance."""
        with patch('src.bunsui.core.session.manager.SessionRepository') as mock_repo_class:
            mock_repo_class.return_value = mock_repository
            return SessionManager(mock_aws_client)
    
    def test_manager_initialization(self, mock_aws_client):
        """Test manager initialization."""
        with patch('src.bunsui.core.session.manager.SessionRepository') as mock_repo_class:
            manager = SessionManager(mock_aws_client)
            assert manager.aws_client == mock_aws_client
            mock_repo_class.assert_called_once_with(mock_aws_client, "bunsui-sessions")
    
    def test_create_session_success(self, manager, mock_repository):
        """Test successful session creation."""
        # Mock repository response
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.PENDING,
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        mock_repository.create_session.return_value = mock_session
        
        result = manager.create_session(
            pipeline_id="test-pipeline",
            total_steps=5
        )
        
        assert result.pipeline_id == "test-pipeline"
        assert result.status == SessionStatus.PENDING
        assert result.progress.total_steps == 5
        mock_repository.create_session.assert_called_once()
    
    def test_create_session_validation_error(self, manager):
        """Test session creation with validation error."""
        with pytest.raises(ValidationError):
            manager.create_session(pipeline_id="")  # Empty pipeline ID
    
    def test_start_session_success(self, manager, mock_repository):
        """Test successful session start."""
        # Mock existing session
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.PENDING,
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        mock_repository.get_session.return_value = mock_session
        
        # Mock update response
        updated_session = mock_session.copy()
        updated_session.status = SessionStatus.RUNNING
        updated_session.start_time = datetime.now(timezone.utc)
        mock_repository.update_session.return_value = updated_session
        
        result = manager.start_session("test-session")
        
        assert result.status == SessionStatus.RUNNING
        assert result.start_time is not None
        mock_repository.get_session.assert_called_once_with("test-session")
        mock_repository.update_session.assert_called_once()
    
    def test_start_session_not_found(self, manager, mock_repository):
        """Test starting non-existent session."""
        mock_repository.get_session.return_value = None
        
        with pytest.raises(SessionError):
            manager.start_session("non-existent")
    
    def test_start_session_invalid_state(self, manager, mock_repository):
        """Test starting session in invalid state."""
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.RUNNING,  # Already running
            progress=SessionMetadata.Progress(
                current_step=0,
                total_steps=5,
                completed_steps=0,
                failed_steps=0
            )
        )
        mock_repository.get_session.return_value = mock_session
        
        with pytest.raises(SessionError):
            manager.start_session("test-session")
    
    def test_update_progress(self, manager, mock_repository):
        """Test session progress update."""
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.RUNNING,
            progress=SessionMetadata.Progress(
                current_step=2,
                total_steps=5,
                completed_steps=2,
                failed_steps=0
            )
        )
        mock_repository.get_session.return_value = mock_session
        mock_repository.update_session.return_value = mock_session
        
        result = manager.update_progress(
            session_id="test-session",
            current_step=3,
            step_name="test-step"
        )
        
        assert result.progress.current_step == 3
        mock_repository.update_session.assert_called_once()
    
    def test_complete_session_success(self, manager, mock_repository):
        """Test successful session completion."""
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
            progress=SessionMetadata.Progress(
                current_step=5,
                total_steps=5,
                completed_steps=5,
                failed_steps=0
            )
        )
        mock_repository.get_session.return_value = mock_session
        
        completed_session = mock_session.copy()
        completed_session.status = SessionStatus.COMPLETED
        completed_session.end_time = datetime.now(timezone.utc)
        mock_repository.update_session.return_value = completed_session
        
        result = manager.complete_session("test-session", success=True)
        
        assert result.status == SessionStatus.COMPLETED
        assert result.end_time is not None
        mock_repository.update_session.assert_called_once()
    
    def test_complete_session_with_error(self, manager, mock_repository):
        """Test session completion with error."""
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
            progress=SessionMetadata.Progress(
                current_step=3,
                total_steps=5,
                completed_steps=3,
                failed_steps=1
            )
        )
        mock_repository.get_session.return_value = mock_session
        
        failed_session = mock_session.copy()
        failed_session.status = SessionStatus.FAILED
        failed_session.end_time = datetime.now(timezone.utc)
        failed_session.error_message = "Test error"
        mock_repository.update_session.return_value = failed_session
        
        result = manager.complete_session(
            "test-session", 
            success=False, 
            error_message="Test error"
        )
        
        assert result.status == SessionStatus.FAILED
        assert result.error_message == "Test error"
        mock_repository.update_session.assert_called_once()
    
    def test_list_sessions(self, manager, mock_repository):
        """Test session listing."""
        mock_sessions = [
            SessionMetadata(
                session_id="session-1",
                pipeline_id="pipeline-1",
                status=SessionStatus.COMPLETED,
                progress=SessionMetadata.Progress(
                    current_step=5,
                    total_steps=5,
                    completed_steps=5,
                    failed_steps=0
                )
            ),
            SessionMetadata(
                session_id="session-2",
                pipeline_id="pipeline-1",
                status=SessionStatus.RUNNING,
                progress=SessionMetadata.Progress(
                    current_step=2,
                    total_steps=5,
                    completed_steps=2,
                    failed_steps=0
                )
            )
        ]
        mock_repository.list_sessions.return_value = mock_sessions
        
        result = manager.list_sessions(pipeline_id="pipeline-1")
        
        assert len(result) == 2
        assert result[0].session_id == "session-1"
        assert result[1].session_id == "session-2"
        mock_repository.list_sessions.assert_called_once_with("pipeline-1", None, 100)
    
    def test_get_session_statistics(self, manager, mock_repository):
        """Test session statistics retrieval."""
        start_time = datetime.now(timezone.utc)
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.RUNNING,
            start_time=start_time,
            progress=SessionMetadata.Progress(
                current_step=3,
                total_steps=5,
                completed_steps=3,
                failed_steps=0
            ),
            checkpoints=[],
            metadata={"test": "data"}
        )
        mock_repository.get_session.return_value = mock_session
        
        result = manager.get_session_statistics("test-session")
        
        assert result["session_id"] == "test-session"
        assert result["pipeline_id"] == "test-pipeline"
        assert result["status"] == "RUNNING"
        assert result["progress"]["completion_percentage"] == 60.0
        assert result["checkpoints_count"] == 0
        assert result["metadata"] == {"test": "data"}
        assert "start_time" in result
        assert "current_runtime_seconds" in result
    
    def test_status_callbacks(self, manager, mock_repository):
        """Test status change callbacks."""
        callback_called = False
        callback_session = None
        
        def test_callback(session):
            nonlocal callback_called, callback_session
            callback_called = True
            callback_session = session
        
        # Register callback
        manager.register_status_callback(SessionStatus.COMPLETED, test_callback)
        
        # Trigger callback
        mock_session = SessionMetadata(
            session_id="test-session",
            pipeline_id="test-pipeline",
            status=SessionStatus.COMPLETED,
            progress=SessionMetadata.Progress(
                current_step=5,
                total_steps=5,
                completed_steps=5,
                failed_steps=0
            )
        )
        
        manager._trigger_status_callbacks(SessionStatus.COMPLETED, mock_session)
        
        assert callback_called
        assert callback_session.session_id == "test-session"


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    return SessionMetadata(
        session_id="test-session-123",
        pipeline_id="test-pipeline-456",
        status=SessionStatus.PENDING,
        progress=SessionMetadata.Progress(
            current_step=0,
            total_steps=10,
            completed_steps=0,
            failed_steps=0
        ),
        metadata={"test": "data", "version": "1.0"}
    )


@pytest.fixture
def sample_checkpoint():
    """Create a sample checkpoint for testing."""
    return Checkpoint(
        checkpoint_id="checkpoint-123",
        checkpoint_type=CheckpointType.STEP_COMPLETE,
        step_name="process_data",
        timestamp=datetime.now(timezone.utc),
        data={"processed_records": 100},
        metadata={"duration": 5.2}
    )


class TestIntegration:
    """Integration tests for session management."""
    
    def test_session_lifecycle(self, sample_session):
        """Test complete session lifecycle."""
        # This would be an integration test with actual AWS services
        # For now, we'll just test the model interactions
        
        # Initial state
        assert sample_session.status == SessionStatus.PENDING
        assert sample_session.start_time is None
        assert sample_session.end_time is None
        
        # Start session
        sample_session.status = SessionStatus.RUNNING
        sample_session.start_time = datetime.now(timezone.utc)
        
        # Progress updates
        sample_session.progress.current_step = 5
        sample_session.progress.completed_steps = 5
        
        # Complete session
        sample_session.status = SessionStatus.COMPLETED
        sample_session.end_time = datetime.now(timezone.utc)
        
        # Verify final state
        assert sample_session.status == SessionStatus.COMPLETED
        assert sample_session.start_time is not None
        assert sample_session.end_time is not None
        assert sample_session.progress.completed_steps == 5 