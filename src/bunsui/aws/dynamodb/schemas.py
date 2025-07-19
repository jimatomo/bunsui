"""
DynamoDB table schemas and index definitions for bunsui.

This module defines the DynamoDB table structures, Global Secondary Indexes
(GSI), and data access patterns for the bunsui pipeline management system.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class TableName(str, Enum):
    """DynamoDB table names."""

    SESSIONS = "sessions"
    JOB_HISTORY = "job-history"
    PIPELINES = "pipelines"
    
    @classmethod
    def get_full_name(cls, table_name: 'TableName', prefix: str = "bunsui") -> str:
        """Get full table name with prefix."""
        return f"{prefix}-{table_name.value}"


class IndexName(str, Enum):
    """Global Secondary Index names."""

    # Sessions table indexes
    SESSIONS_BY_PIPELINE = "sessions-by-pipeline-index"
    SESSIONS_BY_STATUS = "sessions-by-status-index"
    SESSIONS_BY_USER = "sessions-by-user-index"

    # Job History table indexes
    JOB_HISTORY_BY_PIPELINE = "job-history-by-pipeline-index"
    JOB_HISTORY_BY_STATUS = "job-history-by-status-index"

    # Pipeline table indexes
    PIPELINES_BY_USER = "pipelines-by-user-index"


@dataclass
class AttributeDefinition:
    """DynamoDB attribute definition."""

    attribute_name: str
    attribute_type: str  # S, N, B


@dataclass
class KeySchema:
    """DynamoDB key schema definition."""

    attribute_name: str
    key_type: str  # HASH, RANGE


@dataclass
class GlobalSecondaryIndex:
    """DynamoDB Global Secondary Index definition."""

    index_name: str
    key_schema: List[KeySchema]
    projection: Dict[str, Any]
    provisioned_throughput: Optional[Dict[str, int]] = None


@dataclass
class TableSchema:
    """DynamoDB table schema definition."""

    table_name: str
    attribute_definitions: List[AttributeDefinition]
    key_schema: List[KeySchema]
    global_secondary_indexes: List[GlobalSecondaryIndex]
    provisioned_throughput: Optional[Dict[str, int]] = None
    billing_mode: str = "PAY_PER_REQUEST"
    stream_specification: Optional[Dict[str, Any]] = None
    tags: Optional[Dict[str, str]] = None


# Sessions Table Schema
SESSIONS_TABLE_SCHEMA = TableSchema(
    table_name=TableName.SESSIONS,
    attribute_definitions=[
        AttributeDefinition("session_id", "S"),
        AttributeDefinition("created_at", "S"),
        AttributeDefinition("pipeline_id", "S"),
        AttributeDefinition("status", "S"),
        AttributeDefinition("user_id", "S"),
    ],
    key_schema=[
        KeySchema("session_id", "HASH"),
        KeySchema("created_at", "RANGE"),
    ],
    global_secondary_indexes=[
        GlobalSecondaryIndex(
            index_name=IndexName.SESSIONS_BY_PIPELINE,
            key_schema=[
                KeySchema("pipeline_id", "HASH"),
                KeySchema("created_at", "RANGE"),
            ],
            projection={"ProjectionType": "ALL"},
        ),
        GlobalSecondaryIndex(
            index_name=IndexName.SESSIONS_BY_STATUS,
            key_schema=[
                KeySchema("status", "HASH"),
                KeySchema("created_at", "RANGE"),
            ],
            projection={"ProjectionType": "ALL"},
        ),
        GlobalSecondaryIndex(
            index_name=IndexName.SESSIONS_BY_USER,
            key_schema=[
                KeySchema("user_id", "HASH"),
                KeySchema("created_at", "RANGE"),
            ],
            projection={"ProjectionType": "ALL"},
        ),
    ],
    stream_specification={
        "StreamEnabled":
            True,
        "StreamViewType":
            "NEW_AND_OLD_IMAGES",
    },
    tags={
        "Application": "bunsui",
        "Component": "sessions",
        "Environment": "production",
    },
)

# Job History Table Schema
JOB_HISTORY_TABLE_SCHEMA = TableSchema(
    table_name=TableName.JOB_HISTORY,
    attribute_definitions=[
        AttributeDefinition("session_id", "S"),
        AttributeDefinition("job_timestamp", "S"),  # job_id#timestamp
        AttributeDefinition("pipeline_id", "S"),
        AttributeDefinition("job_status", "S"),
    ],
    key_schema=[
        KeySchema("session_id", "HASH"),
        KeySchema("job_timestamp", "RANGE"),
    ],
    global_secondary_indexes=[
        GlobalSecondaryIndex(
            index_name=IndexName.JOB_HISTORY_BY_PIPELINE,
            key_schema=[
                KeySchema("pipeline_id", "HASH"),
                KeySchema("job_timestamp", "RANGE"),
            ],
            projection={"ProjectionType": "ALL"},
        ),
        GlobalSecondaryIndex(
            index_name=IndexName.JOB_HISTORY_BY_STATUS,
            key_schema=[
                KeySchema("job_status", "HASH"),
                KeySchema("job_timestamp", "RANGE"),
            ],
            projection={
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "session_id",
                    "job_id",
                    "pipeline_id",
                    "started_at",
                    "completed_at",
                    "error_message",
                ],
            },
        ),
    ],
    stream_specification={
        "StreamEnabled": True,
        "StreamViewType": "NEW_AND_OLD_IMAGES",
    },
    tags={
        "Application": "bunsui",
        "Component": "job-history",
        "Environment": "production",
    },
)

# Pipeline Metadata Table Schema
PIPELINES_TABLE_SCHEMA = TableSchema(
    table_name=TableName.PIPELINES,
    attribute_definitions=[
        AttributeDefinition("pipeline_id", "S"),
        AttributeDefinition("version", "S"),
        AttributeDefinition("user_id", "S"),
        AttributeDefinition("created_at", "S"),
    ],
    key_schema=[
        KeySchema("pipeline_id", "HASH"),
        KeySchema("version", "RANGE"),
    ],
    global_secondary_indexes=[
        GlobalSecondaryIndex(
            index_name=IndexName.PIPELINES_BY_USER,
            key_schema=[
                KeySchema("user_id", "HASH"),
                KeySchema("created_at", "RANGE"),
            ],
            projection={"ProjectionType": "ALL"},
        ),
    ],
    tags={
        "Application": "bunsui",
        "Component": "pipelines",
        "Environment": "production",
    },
)


class AccessPatterns:
    """
    Documented data access patterns for DynamoDB queries.

    This class documents the primary access patterns and their corresponding
    table/index usage for efficient query design.
    """

    # Sessions Table Access Patterns
    SESSION_PATTERNS = {
        "get_session_by_id": {
            "description": "Get specific session by ID",
            "table": TableName.SESSIONS,
            "key": "session_id",
            "operation": "GetItem",
        },
        "list_sessions_by_pipeline": {
            "description": "List all sessions for a pipeline ordered by creation time",
            "table": TableName.SESSIONS,
            "index": IndexName.SESSIONS_BY_PIPELINE,
            "key": "pipeline_id",
            "sort_key": "created_at",
            "operation": "Query",
        },
        "list_sessions_by_status": {
            "description": "List sessions by status ordered by creation time",
            "table": TableName.SESSIONS,
            "index": IndexName.SESSIONS_BY_STATUS,
            "key": "status",
            "sort_key": "created_at",
            "operation": "Query",
        },
        "list_sessions_by_user": {
            "description": "List sessions for a user ordered by creation time",
            "table": TableName.SESSIONS,
            "index": IndexName.SESSIONS_BY_USER,
            "key": "user_id",
            "sort_key": "created_at",
            "operation": "Query",
        },
    }

    # Job History Access Patterns
    JOB_HISTORY_PATTERNS = {
        "get_job_history_for_session": {
            "description": "Get all job execution history for a session",
            "table": TableName.JOB_HISTORY,
            "key": "session_id",
            "operation": "Query",
        },
        "get_job_history_by_pipeline": {
            "description": (
                "Get job history across all sessions for a pipeline"
            ),
            "table": TableName.JOB_HISTORY,
            "index": IndexName.JOB_HISTORY_BY_PIPELINE,
            "key": "pipeline_id",
            "sort_key": "job_timestamp",
            "operation": "Query",
        },
        "list_failed_jobs": {
            "description": "List all failed jobs across all sessions",
            "table": TableName.JOB_HISTORY,
            "index": IndexName.JOB_HISTORY_BY_STATUS,
            "key": "job_status",
            "filter": "FAILED",
            "operation": "Query",
        },
    }

    # Pipeline Access Patterns
    PIPELINE_PATTERNS = {
        "get_pipeline_by_id": {
            "description": (
                "Get specific pipeline by ID and version"
            ),
            "table": TableName.PIPELINES,
            "key": "pipeline_id",
            "sort_key": "version",
            "operation": "GetItem",
        },
        "list_pipelines_by_user": {
            "description": (
                "List all pipelines for a user ordered by creation time"
            ),
            "table": TableName.PIPELINES,
            "index": IndexName.PIPELINES_BY_USER,
            "key": "user_id",
            "sort_key": "created_at",
            "operation": "Query",
        },
    }


def get_table_schemas() -> List[TableSchema]:
    """Get all table schemas."""
    return [
        SESSIONS_TABLE_SCHEMA,
        JOB_HISTORY_TABLE_SCHEMA,
        PIPELINES_TABLE_SCHEMA,
    ]


def get_table_schema(table_name: TableName, prefix: str = "bunsui") -> Optional[TableSchema]:
    """Get schema for a specific table."""
    schemas = {
        TableName.SESSIONS: SESSIONS_TABLE_SCHEMA,
        TableName.JOB_HISTORY: JOB_HISTORY_TABLE_SCHEMA,
        TableName.PIPELINES: PIPELINES_TABLE_SCHEMA,
    }
    base_schema = schemas.get(table_name)
    if base_schema:
        # Create a copy with the correct table name
        import copy
        schema_copy = copy.deepcopy(base_schema)
        schema_copy.table_name = TableName.get_full_name(table_name, prefix)
        return schema_copy
    return None


def validate_access_pattern(table_name: TableName, pattern_name: str) -> bool:
    """Validate if an access pattern is supported."""
    pattern_maps = {
        TableName.SESSIONS: AccessPatterns.SESSION_PATTERNS,
        TableName.JOB_HISTORY: AccessPatterns.JOB_HISTORY_PATTERNS,
        TableName.PIPELINES: AccessPatterns.PIPELINE_PATTERNS,
    }

    patterns = pattern_maps.get(table_name, {})
    return pattern_name in patterns


def get_access_pattern(table_name: TableName, pattern_name: str) -> Optional[Dict[str, Any]]:
    """Get access pattern configuration."""
    pattern_maps = {
        TableName.SESSIONS: AccessPatterns.SESSION_PATTERNS,
        TableName.JOB_HISTORY: AccessPatterns.JOB_HISTORY_PATTERNS,
        TableName.PIPELINES: AccessPatterns.PIPELINE_PATTERNS,
    }

    patterns = pattern_maps.get(table_name, {})
    return patterns.get(
        pattern_name
    )
