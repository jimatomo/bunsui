"""
Pipeline repository for DynamoDB persistence.

This module provides the PipelineRepository class for managing
pipeline data persistence in DynamoDB.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from uuid import uuid4

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from ..models.pipeline import Pipeline, PipelineStatus
from ...aws.client import AWSClient
from ...aws.exceptions import AWSError, AWSServiceError
from ...core.exceptions import ValidationError

# Type hints for DynamoDB
Table = Any  # type: ignore


class PipelineRepository:
    """
    Repository for managing pipeline data in DynamoDB.
    
    This class handles all CRUD operations for pipeline data,
    including versioning and metadata management.
    """
    
    def __init__(self, aws_client: AWSClient, table_name: str = "bunsui-pipelines"):
        """
        Initialize the pipeline repository.
        
        Args:
            aws_client: AWS client instance for DynamoDB operations
            table_name: Name of the DynamoDB table for pipelines
        """
        self.aws_client = aws_client
        self.table_name = table_name
        self.table: Optional[Table] = None
        self._initialize_table()
    
    def _initialize_table(self) -> None:
        """Initialize DynamoDB table reference."""
        try:
            dynamodb = self.aws_client.get_resource('dynamodb')
            self.table = dynamodb.Table(self.table_name)
        except Exception as e:
            raise AWSError(
                message=f"Failed to initialize DynamoDB table: {str(e)}",
                error_code="DYNAMODB_INIT_ERROR",
                service_name="dynamodb",
                operation_name="initialize_table",
                original_error=e
            )
    
    def create_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """
        Create a new pipeline in the database.
        
        Args:
            pipeline: Pipeline to create
            
        Returns:
            Created pipeline
            
        Raises:
            ValidationError: If pipeline data is invalid
            AWSServiceError: If creation fails
        """
        try:
            # Validate pipeline
            if not pipeline.validate_dependencies():
                raise ValidationError(
                    message="Pipeline has invalid job dependencies",
                    field_name="jobs",
                    field_value=pipeline.jobs
                )
            
            cycles = pipeline.detect_cycles()
            if cycles:
                raise ValidationError(
                    message=f"Pipeline has dependency cycles: {cycles}",
                    field_name="jobs",
                    field_value=pipeline.jobs
                )
            
            # Convert pipeline to DynamoDB item
            item = self._pipeline_to_item(pipeline)
            
            # Add creation timestamp
            item['created_at'] = datetime.now(timezone.utc).isoformat()
            item['updated_at'] = item['created_at']
            
            # Create pipeline in DynamoDB
            if self.table is None:
                raise AWSError(
                    message="DynamoDB table not initialized",
                    error_code="DYNAMODB_NOT_INITIALIZED",
                    service_name="dynamodb",
                    operation_name="create_pipeline"
                )
            
            self.table.put_item(
                Item=item,
                ConditionExpression=Attr('pipeline_id').not_exists()
            )
            
            # Return updated pipeline
            updated_pipeline = pipeline.copy()
            updated_pipeline.created_at = datetime.fromisoformat(item['created_at'])
            updated_pipeline.updated_at = datetime.fromisoformat(item['updated_at'])
            
            return updated_pipeline
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise ValidationError(
                    message=f"Pipeline with ID {pipeline.pipeline_id} already exists",
                    field_name="pipeline_id",
                    field_value=pipeline.pipeline_id
                )
            raise AWSServiceError(
                message=f"Failed to create pipeline: {str(e)}",
                service_name="dynamodb",
                operation_name="create_pipeline",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise AWSError(
                message=f"Failed to create pipeline: {str(e)}",
                error_code="PIPELINE_CREATE_ERROR",
                service_name="dynamodb",
                operation_name="create_pipeline",
                original_error=e
            )
    
    def get_pipeline(self, pipeline_id: str, version: str = None) -> Optional[Pipeline]:
        """
        Get pipeline by ID and version.
        
        Args:
            pipeline_id: Pipeline identifier
            version: Pipeline version (latest if None)
            
        Returns:
            Pipeline instance or None if not found
            
        Raises:
            AWSServiceError: If get operation fails
        """
        try:
            if self.table is None:
                raise AWSError(
                    message="DynamoDB table not initialized",
                    error_code="DYNAMODB_NOT_INITIALIZED",
                    service_name="dynamodb",
                    operation_name="get_pipeline"
                )
            
            if version:
                # Get specific version
                response = self.table.get_item(
                    Key={
                        'pipeline_id': pipeline_id,
                        'version': version
                    }
                )
                
                if 'Item' not in response:
                    return None
                
                return self._item_to_pipeline(response['Item'])
            else:
                # Get latest version
                response = self.table.query(
                    KeyConditionExpression=Key('pipeline_id').eq(pipeline_id),
                    ScanIndexForward=False,  # Sort by version descending
                    Limit=1
                )
                
                if not response['Items']:
                    return None
                
                return self._item_to_pipeline(response['Items'][0])
                
        except ClientError as e:
            raise AWSServiceError(
                message=f"Failed to get pipeline: {str(e)}",
                service_name="dynamodb",
                operation_name="get_pipeline",
                error_code=e.response['Error']['Code'],
                original_error=e
            )
        except Exception as e:
            raise AWSError(
                message=f"Failed to get pipeline: {str(e)}",
                error_code="PIPELINE_GET_ERROR",
                service_name="dynamodb",
                operation_name="get_pipeline",
                original_error=e
            )
    
    def update_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """
        Update an existing pipeline.
        
        Args:
            pipeline: Updated pipeline
            
        Returns:
            Updated pipeline
            
        Raises:
            ValidationError: If pipeline data is invalid
            AWSServiceError: If update fails
        """
        try:
            # Validate pipeline
            if not pipeline.validate_dependencies():
                raise ValidationError(
                    message="Pipeline has invalid job dependencies",
                    field_name="jobs",
                    field_value=pipeline.jobs
                )
            
            cycles = pipeline.detect_cycles()
            if cycles:
                raise ValidationError(
                    message=f"Pipeline has dependency cycles: {cycles}",
                    field_name="jobs",
                    field_value=pipeline.jobs
                )
            
            # Convert pipeline to DynamoDB item
            item = self._pipeline_to_item(pipeline)
            
            # Update timestamp
            item['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Update pipeline in DynamoDB
            if self.table is None:
                raise AWSError("DynamoDB table not initialized")
            
            self.table.put_item(
                Item=item,
                ConditionExpression=Attr('pipeline_id').exists()
            )
            
            # Return updated pipeline
            updated_pipeline = pipeline.copy()
            updated_pipeline.updated_at = datetime.fromisoformat(item['updated_at'])
            
            return updated_pipeline
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise ValidationError(
                    message=f"Pipeline with ID {pipeline.pipeline_id} does not exist",
                    field_name="pipeline_id",
                    field_value=pipeline.pipeline_id
                )
            raise AWSServiceError(
                message=f"Failed to update pipeline: {str(e)}",
                service_name="dynamodb",
                operation_name="update_pipeline",
                error_code=error_code,
                original_error=e
            )
        except Exception as e:
            raise AWSError(f"Failed to update pipeline: {str(e)}")
    
    def delete_pipeline(self, pipeline_id: str, version: str = None) -> bool:
        """
        Delete pipeline by ID and version.
        
        Args:
            pipeline_id: Pipeline identifier
            version: Pipeline version (all versions if None)
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            AWSServiceError: If delete operation fails
        """
        try:
            if self.table is None:
                raise AWSError("DynamoDB table not initialized")
            
            if version:
                # Delete specific version
                response = self.table.delete_item(
                    Key={
                        'pipeline_id': pipeline_id,
                        'version': version
                    },
                    ReturnValues='ALL_OLD'
                )
                
                return 'Attributes' in response
            else:
                # Delete all versions
                # First, get all versions
                versions_response = self.table.query(
                    KeyConditionExpression=Key('pipeline_id').eq(pipeline_id),
                    ProjectionExpression='version'
                )
                
                if not versions_response['Items']:
                    return False
                
                # Delete each version
                for item in versions_response['Items']:
                    self.table.delete_item(
                        Key={
                            'pipeline_id': pipeline_id,
                            'version': item['version']
                        }
                    )
                
                return True
                
        except ClientError as e:
            raise AWSServiceError(
                message=f"Failed to delete pipeline: {str(e)}",
                service_name="dynamodb",
                operation_name="delete_pipeline",
                error_code=e.response['Error']['Code'],
                original_error=e
            )
        except Exception as e:
            raise AWSError(f"Failed to delete pipeline: {str(e)}")
    
    def list_pipelines(
        self,
        status: Optional[PipelineStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Pipeline]:
        """
        List pipelines with optional filtering.
        
        Args:
            status: Filter by pipeline status
            user_id: Filter by user ID
            limit: Maximum number of pipelines to return
            
        Returns:
            List of pipelines
            
        Raises:
            AWSServiceError: If list operation fails
        """
        try:
            if self.table is None:
                raise AWSError("DynamoDB table not initialized")
            
            # Build scan parameters
            kwargs = {
                'Limit': limit,
                'ProjectionExpression': 'pipeline_id, version, #name, description, #status, created_at, updated_at, user_id, user_name, tags',
                'ExpressionAttributeNames': {
                    '#name': 'name',
                    '#status': 'status'
                }
            }
            
            # Add filters
            filter_expressions = []
            if status:
                filter_expressions.append(Attr('status').eq(status.value))
            if user_id:
                filter_expressions.append(Attr('user_id').eq(user_id))
            
            if filter_expressions:
                filter_expr = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expr = filter_expr & expr
                kwargs['FilterExpression'] = filter_expr
            
            # Execute scan
            response = self.table.scan(**kwargs)
            
            # Convert items to pipelines
            pipelines = []
            for item in response['Items']:
                pipeline = self._item_to_pipeline(item)
                pipelines.append(pipeline)
            
            return pipelines
            
        except ClientError as e:
            raise AWSServiceError(
                message=f"Failed to list pipelines: {str(e)}",
                service_name="dynamodb",
                operation_name="list_pipelines",
                error_code=e.response['Error']['Code'],
                original_error=e
            )
        except Exception as e:
            raise AWSError(f"Failed to list pipelines: {str(e)}")
    
    def get_pipeline_versions(self, pipeline_id: str) -> List[str]:
        """
        Get all versions of a pipeline.
        
        Args:
            pipeline_id: Pipeline identifier
            
        Returns:
            List of version strings
            
        Raises:
            AWSServiceError: If query fails
        """
        try:
            if self.table is None:
                raise AWSError("DynamoDB table not initialized")
            
            response = self.table.query(
                KeyConditionExpression=Key('pipeline_id').eq(pipeline_id),
                ProjectionExpression='version',
                ScanIndexForward=False  # Sort by version descending
            )
            
            versions = [item['version'] for item in response['Items']]
            return versions
            
        except ClientError as e:
            raise AWSServiceError(
                message=f"Failed to get pipeline versions: {str(e)}",
                service_name="dynamodb",
                operation_name="get_pipeline_versions",
                error_code=e.response['Error']['Code'],
                original_error=e
            )
        except Exception as e:
            raise AWSError(f"Failed to get pipeline versions: {str(e)}")
    
    def _pipeline_to_item(self, pipeline: Pipeline) -> Dict[str, Any]:
        """Convert pipeline to DynamoDB item format."""
        return {
            'pipeline_id': pipeline.pipeline_id,
            'version': pipeline.version,
            'name': pipeline.name,
            'description': pipeline.description,
            'status': pipeline.status.value,
            'jobs': [job.to_dict() for job in pipeline.jobs],
            'timeout_seconds': pipeline.timeout_seconds,
            'max_concurrent_jobs': pipeline.max_concurrent_jobs,
            'tags': pipeline.tags,
            'metadata': pipeline.metadata,
            'user_id': pipeline.user_id,
            'user_name': pipeline.user_name,
            'created_at': pipeline.created_at.isoformat() if pipeline.created_at else None,
            'updated_at': pipeline.updated_at.isoformat() if pipeline.updated_at else None
        }
    
    def _item_to_pipeline(self, item: Dict[str, Any]) -> Pipeline:
        """Convert DynamoDB item to pipeline."""
        # Create pipeline from dictionary
        pipeline_data = {
            'pipeline_id': item['pipeline_id'],
            'version': item['version'],
            'name': item['name'],
            'description': item.get('description'),
            'status': item['status'],
            'jobs': item.get('jobs', []),
            'timeout_seconds': item.get('timeout_seconds', 3600),
            'max_concurrent_jobs': item.get('max_concurrent_jobs', 10),
            'tags': item.get('tags', {}),
            'metadata': item.get('metadata', {}),
            'user_id': item.get('user_id'),
            'user_name': item.get('user_name'),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at')
        }
        
        return Pipeline.from_dict(pipeline_data) 