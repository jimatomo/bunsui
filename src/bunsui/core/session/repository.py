"""
Session repository for DynamoDB persistence.

This module provides the SessionRepository class for managing
session data persistence in DynamoDB.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from uuid import uuid4

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from ..models.session import SessionMetadata, SessionStatus, Checkpoint, CheckpointType
from ...aws.client import AWSClient
from ...aws.exceptions import AWSError, AWSServiceError
from ...core.exceptions import SessionError

# Type hints for DynamoDB
Table = Any  # type: ignore


class SessionRepository:
    """
    Repository for managing session data in DynamoDB.
    
    This class handles all CRUD operations for session data,
    including checkpoints and metadata management.
    """
    
    def __init__(self, aws_client: AWSClient, table_name: str = "bunsui-sessions"):
        """
        Initialize the session repository.
        
        Args:
            aws_client: AWS client instance for DynamoDB operations
            table_name: Name of the DynamoDB table for sessions
        """
        self.aws_client = aws_client
        self.table_name = table_name
        self.table: Optional[Table] = None
        self._initialize_table()
    
    def _initialize_table(self) -> None:
        """Initialize DynamoDB table reference."""
        try:
            dynamodb = self.aws_client.get_resource('dynamodb')
            self.table = dynamodb.Table(self.table_name) # type: ignore
        except Exception as e:
            raise AWSError(
                message=f"Failed to initialize DynamoDB table: {str(e)}",
                error_code="DYNAMODB_INIT_ERROR",
                service_name="dynamodb",
                operation_name="initialize_table",
                original_error=e
            )
    
    def create_session(self, session: SessionMetadata) -> SessionMetadata:
        """
        Create a new session in the database.
        
        Args:
            session: Session metadata to create
            
        Returns:
            Created session metadata
            
        Raises:
            SessionError: If session creation fails
            ValidationError: If session data is invalid
        """
        try:
            # Convert session to DynamoDB item
            item = self._session_to_item(session)
            
            # Add creation timestamp
            item['created_at'] = datetime.now(timezone.utc).isoformat()
            item['updated_at'] = item['created_at']
            
            # Create session in DynamoDB
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            self.table.put_item(
                Item=item,
                ConditionExpression=Attr('session_id').not_exists()
            )
            
            # Return updated session
            updated_session = session.copy()
            updated_session.created_at = datetime.fromisoformat(item['created_at'])
            updated_session.updated_at = datetime.fromisoformat(item['updated_at'])
            
            return updated_session
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise SessionError(f"Session with ID {session.session_id} already exists")
            raise AWSServiceError(
                message=f"Failed to create session: {str(e)}",
                service_name="dynamodb",
                operation_name="create_session",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to create session: {str(e)}")
    
    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session metadata if found, None otherwise
            
        Raises:
            SessionError: If session retrieval fails
        """
        try:
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            response = self.table.get_item(
                Key={'session_id': session_id}
            )
            
            if 'Item' not in response:
                return None
            
            return self._item_to_session(response['Item'])
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AWSServiceError(
                message=f"Failed to get session: {str(e)}",
                service_name="dynamodb",
                operation_name="get_session",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to get session: {str(e)}")
    
    def update_session(self, session: SessionMetadata) -> SessionMetadata:
        """
        Update an existing session.
        
        Args:
            session: Session metadata to update
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If session update fails
        """
        try:
            # Update timestamp
            session.updated_at = datetime.now(timezone.utc)
            
            # Convert to DynamoDB item
            item = self._session_to_item(session)
            
            # Update session in DynamoDB
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            self.table.put_item(
                Item=item,
                ConditionExpression=Attr('session_id').exists()
            )
            
            return session
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise SessionError(f"Session with ID {session.session_id} does not exist")
            raise AWSServiceError(
                message=f"Failed to update session: {str(e)}",
                service_name="dynamodb",
                operation_name="update_session",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to update session: {str(e)}")
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted, False if not found
            
        Raises:
            SessionError: If session deletion fails
        """
        try:
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            response = self.table.delete_item(
                Key={'session_id': session_id},
                ReturnValues='ALL_OLD'
            )
            
            return 'Attributes' in response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AWSServiceError(
                message=f"Failed to delete session: {str(e)}",
                service_name="dynamodb",
                operation_name="delete_session",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to delete session: {str(e)}")
    
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
            
        Raises:
            SessionError: If session listing fails
        """
        try:
            # Use GSI if filtering by pipeline_id
            if pipeline_id:
                # Build query parameters
                kwargs: Dict[str, Any] = {
                    'Limit': limit,
                    'ScanIndexForward': False,  # Sort by created_at descending
                    'IndexName': 'pipeline_id-created_at-index',
                    'KeyConditionExpression': 'pipeline_id = :pipeline_id',
                    'ExpressionAttributeValues': {
                        ':pipeline_id': pipeline_id
                    }
                }
                
                if status:
                    kwargs['FilterExpression'] = '#status = :status'
                    kwargs['ExpressionAttributeNames'] = {'#status': 'status'}
                    kwargs['ExpressionAttributeValues'][':status'] = status.value
                
                if self.table is None:
                    raise SessionError("DynamoDB table not initialized")
                response = self.table.query(**kwargs)
            else:
                # Use scan for general listing
                scan_kwargs: Dict[str, Any] = {
                    'Limit': limit
                }
                
                if status:
                    scan_kwargs['FilterExpression'] = '#status = :status'
                    scan_kwargs['ExpressionAttributeNames'] = {'#status': 'status'}
                    scan_kwargs['ExpressionAttributeValues'] = {':status': status.value}
                
                if self.table is None:
                    raise SessionError("DynamoDB table not initialized")
                response = self.table.scan(**scan_kwargs)
            
            # Convert items to session metadata
            sessions = []
            for item in response.get('Items', []):
                try:
                    session = self._item_to_session(item)
                    sessions.append(session)
                except Exception as e:
                    # Log error but continue processing other items
                    print(f"Warning: Failed to parse session item: {e}")
                    continue
            
            return sessions
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AWSServiceError(
                message=f"Failed to list sessions: {str(e)}",
                service_name="dynamodb",
                operation_name="list_sessions",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to list sessions: {str(e)}")
    
    def add_checkpoint(self, session_id: str, checkpoint: Checkpoint) -> bool:
        """
        Add a checkpoint to a session.
        
        Args:
            session_id: Session ID to add checkpoint to
            checkpoint: Checkpoint to add
            
        Returns:
            True if checkpoint was added successfully
            
        Raises:
            SessionError: If checkpoint addition fails
        """
        try:
            # Generate checkpoint ID if not provided
            if not checkpoint.checkpoint_id:
                checkpoint.checkpoint_id = str(uuid4())
            
            # Convert checkpoint to DynamoDB format
            checkpoint_item = self._checkpoint_to_item(checkpoint)
            
            # Update session with new checkpoint
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            self.table.update_item(
                Key={'session_id': session_id},
                UpdateExpression='SET checkpoints = list_append(if_not_exists(checkpoints, :empty_list), :checkpoint), updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':checkpoint': [checkpoint_item],
                    ':empty_list': [],
                    ':updated_at': datetime.now(timezone.utc).isoformat()
                },
                ConditionExpression=Attr('session_id').exists()
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise SessionError(f"Session with ID {session_id} does not exist")
            raise AWSServiceError(
                message=f"Failed to add checkpoint: {str(e)}",
                service_name="dynamodb",
                operation_name="add_checkpoint",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to add checkpoint: {str(e)}")
    
    def get_session_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """
        Get all checkpoints for a session.
        
        Args:
            session_id: Session ID to get checkpoints for
            
        Returns:
            List of checkpoints
            
        Raises:
            SessionError: If checkpoint retrieval fails
        """
        try:
            if self.table is None:
                raise SessionError("DynamoDB table not initialized")
            response = self.table.get_item(
                Key={'session_id': session_id},
                ProjectionExpression='checkpoints'
            )
            
            if 'Item' not in response:
                raise SessionError(f"Session with ID {session_id} not found")
            
            checkpoints = []
            for item in response['Item'].get('checkpoints', []):
                checkpoint = self._item_to_checkpoint(item)
                checkpoints.append(checkpoint)
            
            return checkpoints
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AWSServiceError(
                message=f"Failed to get checkpoints: {str(e)}",
                service_name="dynamodb",
                operation_name="get_checkpoints",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise SessionError(f"Failed to get checkpoints: {str(e)}")
    
    def _session_to_item(self, session: SessionMetadata) -> Dict[str, Any]:
        """Convert session metadata to DynamoDB item format."""
        item = {
            'session_id': session.session_id,
            'pipeline_id': session.pipeline_id,
            'pipeline_name': session.pipeline_name,
            'status': session.status.value,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'error_message': session.error_message,
            'error_code': session.error_code,
            'configuration': session.configuration,
            'tags': session.tags,
            'total_jobs': session.total_jobs,
            'completed_jobs': session.completed_jobs,
            'failed_jobs': session.failed_jobs,
            'retry_count': session.retry_count,
            'max_retries': session.max_retries,
            'user_id': session.user_id,
            'user_name': session.user_name,
            'environment': session.environment,
            'region': session.region,
            'execution_arn': session.execution_arn,
            'execution_name': session.execution_name
        }
        
        # Add checkpoints if present
        if session.checkpoints:
            item['checkpoints'] = [
                self._checkpoint_to_item(checkpoint)
                for checkpoint in session.checkpoints
            ]
        
        # Add timestamps if present
        if session.created_at:
            item['created_at'] = session.created_at.isoformat()
        if session.updated_at:
            item['updated_at'] = session.updated_at.isoformat()
        
        return item
    
    def _item_to_session(self, item: Dict[str, Any]) -> SessionMetadata:
        """Convert DynamoDB item to session metadata."""
        # Parse checkpoints
        checkpoints = []
        if 'checkpoints' in item:
            for checkpoint_item in item['checkpoints']:
                checkpoint = self._item_to_checkpoint(checkpoint_item)
                checkpoints.append(checkpoint)
        
        # Create session metadata
        session = SessionMetadata(
            session_id=item['session_id'],
            pipeline_id=item['pipeline_id'],
            pipeline_name=item.get('pipeline_name'),
            status=SessionStatus(item['status']),
            started_at=datetime.fromisoformat(item['started_at']) if item.get('started_at') else None,
            completed_at=datetime.fromisoformat(item['completed_at']) if item.get('completed_at') else None,
            error_message=item.get('error_message'),
            error_code=item.get('error_code'),
            configuration=item.get('configuration', {}),
            tags=item.get('tags', {}),
            total_jobs=item.get('total_jobs', 0),
            completed_jobs=item.get('completed_jobs', 0),
            failed_jobs=item.get('failed_jobs', 0),
            retry_count=item.get('retry_count', 0),
            max_retries=item.get('max_retries', 3),
            checkpoints=checkpoints,
            user_id=item.get('user_id'),
            user_name=item.get('user_name'),
            environment=item.get('environment'),
            region=item.get('region'),
            execution_arn=item.get('execution_arn'),
            execution_name=item.get('execution_name')
        )
        
        # Add timestamps if present
        if 'created_at' in item:
            session.created_at = datetime.fromisoformat(item['created_at'])
        if 'updated_at' in item:
            session.updated_at = datetime.fromisoformat(item['updated_at'])
        
        return session
    
    def _checkpoint_to_item(self, checkpoint: Checkpoint) -> Dict[str, Any]:
        """Convert checkpoint to DynamoDB item format."""
        return {
            'checkpoint_id': checkpoint.checkpoint_id,
            'checkpoint_type': checkpoint.checkpoint_type.value,
            'job_id': checkpoint.job_id,
            'operation_id': checkpoint.operation_id,
            'created_at': checkpoint.created_at.isoformat(),
            'state_data': checkpoint.state_data,
            'message': checkpoint.message
        }
    
    def _item_to_checkpoint(self, item: Dict[str, Any]) -> Checkpoint:
        """Convert DynamoDB item to checkpoint."""
        return Checkpoint(
            checkpoint_id=item['checkpoint_id'],
            checkpoint_type=CheckpointType(item['checkpoint_type']),
            job_id=item['job_id'],
            operation_id=item.get('operation_id'),
            created_at=datetime.fromisoformat(item['created_at']),
            state_data=item.get('state_data', {}),
            message=item.get('message')
        ) 