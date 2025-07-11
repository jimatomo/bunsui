"""
DynamoDB repository implementation for bunsui.

This module provides repository pattern implementation for DynamoDB operations,
handling data serialization/deserialization and business logic.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from bunsui.aws.dynamodb.client import DynamoDBClient
from bunsui.aws.dynamodb.schemas import TableName, IndexName
from bunsui.core.models.session import Session, SessionStatus


class DynamoDBRepository:
    """Repository pattern implementation for DynamoDB operations."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize DynamoDB repository."""
        self.client = DynamoDBClient(region)
        self.region = region

    def _serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()

    def _deserialize_datetime(self, dt_str: str) -> datetime:
        """Deserialize ISO format string to datetime."""
        return datetime.fromisoformat(dt_str)

    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize item for DynamoDB storage."""
        serialized = {}
        for key, value in item.items():
            if isinstance(value, datetime):
                serialized[key] = {"S": self._serialize_datetime(value)}
            elif isinstance(value, dict):
                serialized[key] = {"M": self._serialize_item(value)}
            elif isinstance(value, list):
                serialized[key] = {
                    "L": [
                        (
                            self._serialize_item(v)
                            if isinstance(v, dict)
                            else {"S": str(v)}
                        )
                        for v in value
                    ]
                }
            elif isinstance(value, bool):
                serialized[key] = {"BOOL": value}
            elif isinstance(value, (int, float)):
                serialized[key] = {"N": str(value)}
            else:
                serialized[key] = {"S": str(value)}
        return serialized

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize item from DynamoDB storage."""
        deserialized = {}
        for key, value in item.items():
            if "S" in value:
                # Try to parse as datetime first
                try:
                    deserialized[key] = self._deserialize_datetime(value["S"])
                except ValueError:
                    deserialized[key] = value["S"]
            elif "M" in value:
                deserialized[key] = self._deserialize_item(value["M"])
            elif "L" in value:
                deserialized[key] = [
                    v.get("S", v.get("N", v.get("BOOL", v))) for v in value["L"]
                ]
            elif "BOOL" in value:
                deserialized[key] = value["BOOL"]
            elif "N" in value:
                try:
                    deserialized[key] = int(value["N"])
                except ValueError:
                    deserialized[key] = float(value["N"])
        return deserialized


class SessionRepository(DynamoDBRepository):
    """Repository for session operations."""

    def create_session(self, session: Session) -> Dict[str, Any]:
        """Create a new session."""
        item = {
            "session_id": session.session_id,
            "pipeline_id": session.pipeline_id,
            "status": session.status.value,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "user_id": session.user_id,
            "configuration": session.configuration,
            "checkpoints": [cp.to_dict() for cp in session.checkpoints],
            "total_jobs": session.total_jobs,
            "completed_jobs": session.completed_jobs,
            "failed_jobs": session.failed_jobs,
            "error_message": session.error_message,
        }

        return self.client.put_item(TableName.SESSIONS, item)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        key = {"session_id": {"S": session_id}}
        response = self.client.get_item(TableName.SESSIONS, key)

        if not response:
            return None

        item = self._deserialize_item(response)
        return Session(**item)

    def update_session_status(
        self, session_id: str, status: SessionStatus
    ) -> Dict[str, Any]:
        """Update session status."""
        key = {"session_id": {"S": session_id}}
        update_expression = "SET #status = :status, #updated_at = :updated_at"
        expression_attribute_names = {"#status": "status", "#updated_at": "updated_at"}
        expression_attribute_values = {
            ":status": {"S": status.value},
            ":updated_at": {"S": self._serialize_datetime(datetime.utcnow())},
        }

        return self.client.update_item(
            TableName.SESSIONS,
            key,
            update_expression,
            expression_attribute_names,
            expression_attribute_values,
        )

    def list_sessions_by_pipeline(
        self, pipeline_id: str, limit: Optional[int] = None
    ) -> List[Session]:
        """List sessions for a pipeline."""
        key_condition_expression = "pipeline_id = :pipeline_id"
        expression_attribute_values = {":pipeline_id": {"S": pipeline_id}}

        response = self.client.query(
            TableName.SESSIONS,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.SESSIONS_BY_PIPELINE,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        sessions = []
        for item in response.get("Items", []):
            deserialized_item = self._deserialize_item(item)
            sessions.append(Session(**deserialized_item))

        return sessions

    def list_sessions_by_status(
        self, status: SessionStatus, limit: Optional[int] = None
    ) -> List[Session]:
        """List sessions by status."""
        key_condition_expression = "#status = :status"
        expression_attribute_names = {"#status": "status"}
        expression_attribute_values = {":status": {"S": status.value}}

        response = self.client.query(
            TableName.SESSIONS,
            key_condition_expression,
            expression_attribute_names=expression_attribute_names,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.SESSIONS_BY_STATUS,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        sessions = []
        for item in response.get("Items", []):
            deserialized_item = self._deserialize_item(item)
            sessions.append(Session(**deserialized_item))

        return sessions

    def list_sessions_by_user(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[Session]:
        """List sessions for a user."""
        key_condition_expression = "user_id = :user_id"
        expression_attribute_values = {":user_id": {"S": user_id}}

        response = self.client.query(
            TableName.SESSIONS,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.SESSIONS_BY_USER,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        sessions = []
        for item in response.get("Items", []):
            deserialized_item = self._deserialize_item(item)
            sessions.append(Session(**deserialized_item))

        return sessions

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a session."""
        key = {"session_id": {"S": session_id}}
        return self.client.delete_item(TableName.SESSIONS, key)


class JobHistoryRepository(DynamoDBRepository):
    """Repository for job history operations."""

    def create_job_history(
        self,
        session_id: str,
        job_id: str,
        pipeline_id: str,
        job_status: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new job history record."""
        job_timestamp = f"{job_id}#{started_at.isoformat()}"

        item = {
            "session_id": session_id,
            "job_timestamp": job_timestamp,
            "job_id": job_id,
            "pipeline_id": pipeline_id,
            "job_status": job_status,
            "started_at": started_at,
            "completed_at": completed_at,
            "error_message": error_message,
            "metadata": metadata or {},
        }

        return self.client.put_item(TableName.JOB_HISTORY, item)

    def get_job_history_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get job history for a session."""
        key_condition_expression = "session_id = :session_id"
        expression_attribute_values = {":session_id": {"S": session_id}}

        response = self.client.query(
            TableName.JOB_HISTORY,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
        )

        items = []
        for item in response.get("Items", []):
            items.append(self._deserialize_item(item))

        return items

    def get_job_history_by_pipeline(
        self, pipeline_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get job history for a pipeline."""
        key_condition_expression = "pipeline_id = :pipeline_id"
        expression_attribute_values = {":pipeline_id": {"S": pipeline_id}}

        response = self.client.query(
            TableName.JOB_HISTORY,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.JOB_HISTORY_BY_PIPELINE,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        items = []
        for item in response.get("Items", []):
            items.append(self._deserialize_item(item))

        return items

    def list_failed_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all failed jobs."""
        key_condition_expression = "job_status = :job_status"
        expression_attribute_values = {":job_status": {"S": "FAILED"}}

        response = self.client.query(
            TableName.JOB_HISTORY,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.JOB_HISTORY_BY_STATUS,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        items = []
        for item in response.get("Items", []):
            items.append(self._deserialize_item(item))

        return items


class PipelineRepository(DynamoDBRepository):
    """Repository for pipeline operations."""

    def create_pipeline(
        self,
        pipeline_id: str,
        version: str,
        user_id: str,
        pipeline_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new pipeline."""
        item = {
            "pipeline_id": pipeline_id,
            "version": version,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "pipeline_data": pipeline_data,
        }

        return self.client.put_item(TableName.PIPELINES, item)

    def get_pipeline(self, pipeline_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Get pipeline by ID and version."""
        key = {"pipeline_id": {"S": pipeline_id}, "version": {"S": version}}

        response = self.client.get_item(TableName.PIPELINES, key)
        if not response:
            return None

        return self._deserialize_item(response)

    def list_pipelines_by_user(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List pipelines for a user."""
        key_condition_expression = "user_id = :user_id"
        expression_attribute_values = {":user_id": {"S": user_id}}

        response = self.client.query(
            TableName.PIPELINES,
            key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name=IndexName.PIPELINES_BY_USER,
            limit=limit,
            scan_index_forward=False,  # Most recent first
        )

        items = []
        for item in response.get("Items", []):
            items.append(self._deserialize_item(item))

        return items

    def delete_pipeline(self, pipeline_id: str, version: str) -> Dict[str, Any]:
        """Delete a pipeline."""
        key = {"pipeline_id": {"S": pipeline_id}, "version": {"S": version}}
        return self.client.delete_item(TableName.PIPELINES, key)
