"""
Pipeline model for bunsui.

This module contains the Pipeline, Job, and Operation models that define
the data pipeline structure and execution flow.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator

from ..exceptions import ValidationError


class OperationType(str, Enum):
    """Operation type enumeration."""

    LAMBDA = "lambda"
    ECS = "ecs"
    GLUE = "glue"
    EMR = "emr"
    SAGEMAKER = "sagemaker"
    CUSTOM = "custom"


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class PipelineStatus(str, Enum):
    """Pipeline status enumeration."""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass
class OperationConfig:
    """Operation configuration."""

    operation_type: OperationType
    resource_arn: Optional[str] = None
    timeout_seconds: int = 300
    retry_count: int = 3
    retry_delay_seconds: int = 60
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)


class Operation(ABC):
    """Abstract operation class."""

    def __init__(
        self,
        operation_id: str,
        name: str,
        config: OperationConfig,
        description: Optional[str] = None,
    ):
        """Initialize operation."""
        self.operation_id = operation_id
        self.name = name
        self.config = config
        self.description = description
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the operation."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate operation configuration."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary."""
        return {
            "operation_id": self.operation_id,
            "name": self.name,
            "description": self.description,
            "config": {
                "operation_type": self.config.operation_type.value,
                "resource_arn": self.config.resource_arn,
                "timeout_seconds": self.config.timeout_seconds,
                "retry_count": self.config.retry_count,
                "retry_delay_seconds": self.config.retry_delay_seconds,
                "parameters": self.config.parameters,
                "environment_variables": self.config.environment_variables,
                "tags": self.config.tags,
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Operation":
        """Create operation from dictionary."""
        config_data = data["config"]
        config = OperationConfig(
            operation_type=OperationType(config_data["operation_type"]),
            resource_arn=config_data.get("resource_arn"),
            timeout_seconds=config_data.get("timeout_seconds", 300),
            retry_count=config_data.get("retry_count", 3),
            retry_delay_seconds=config_data.get("retry_delay_seconds", 60),
            parameters=config_data.get("parameters", {}),
            environment_variables=config_data.get("environment_variables", {}),
            tags=config_data.get("tags", {}),
        )

        operation = cls(
            operation_id=data["operation_id"],
            name=data["name"],
            config=config,
            description=data.get("description"),
        )

        if "created_at" in data:
            operation.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            operation.updated_at = datetime.fromisoformat(data["updated_at"])

        return operation


class LambdaOperation(Operation):
    """Lambda function operation."""

    def __init__(
        self,
        operation_id: str,
        name: str,
        function_arn: str,
        timeout_seconds: int = 300,
        retry_count: int = 3,
        retry_delay_seconds: int = 60,
        parameters: Optional[Dict[str, Any]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ):
        """Initialize Lambda operation."""
        config = OperationConfig(
            operation_type=OperationType.LAMBDA,
            resource_arn=function_arn,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            parameters=parameters or {},
            environment_variables=environment_variables or {},
        )
        super().__init__(operation_id, name, config, description)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LambdaOperation":
        """Create Lambda operation from dictionary."""
        config_data = data["config"]
        
        operation = cls(
            operation_id=data["operation_id"],
            name=data["name"],
            function_arn=config_data.get("resource_arn", ""),
            timeout_seconds=config_data.get("timeout_seconds", 300),
            retry_count=config_data.get("retry_count", 3),
            retry_delay_seconds=config_data.get("retry_delay_seconds", 60),
            parameters=config_data.get("parameters", {}),
            environment_variables=config_data.get("environment_variables", {}),
            description=data.get("description"),
        )

        if "created_at" in data:
            operation.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            operation.updated_at = datetime.fromisoformat(data["updated_at"])

        return operation

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Lambda function."""
        # This would integrate with AWS Lambda client
        # For now, return mock response
        return {
            "status": "success",
            "output": input_data,
            "execution_time": 1.5,
            "memory_used": 128,
        }

    def validate(self) -> bool:
        """Validate Lambda operation."""
        return (
            self.config.resource_arn is not None
            and self.config.resource_arn.startswith("arn:aws:lambda:")
            and self.config.timeout_seconds > 0
            and self.config.retry_count >= 0
        )


class ECSOperation(Operation):
    """ECS task operation."""

    def __init__(
        self,
        operation_id: str,
        name: str,
        task_definition_arn: str,
        cluster_name: str,
        timeout_seconds: int = 3600,
        retry_count: int = 3,
        retry_delay_seconds: int = 60,
        parameters: Optional[Dict[str, Any]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ):
        """Initialize ECS operation."""
        config = OperationConfig(
            operation_type=OperationType.ECS,
            resource_arn=task_definition_arn,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            parameters=parameters or {},
            environment_variables=environment_variables or {},
        )
        super().__init__(operation_id, name, config, description)
        self.cluster_name = cluster_name

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ECSOperation":
        """Create ECS operation from dictionary."""
        config_data = data["config"]
        
        operation = cls(
            operation_id=data["operation_id"],
            name=data["name"],
            task_definition_arn=config_data.get("resource_arn", ""),
            cluster_name=config_data.get("parameters", {}).get("cluster", "default"),
            timeout_seconds=config_data.get("timeout_seconds", 3600),
            retry_count=config_data.get("retry_count", 3),
            retry_delay_seconds=config_data.get("retry_delay_seconds", 60),
            parameters=config_data.get("parameters", {}),
            environment_variables=config_data.get("environment_variables", {}),
            description=data.get("description"),
        )

        if "created_at" in data:
            operation.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            operation.updated_at = datetime.fromisoformat(data["updated_at"])

        return operation

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ECS task."""
        # This would integrate with AWS ECS client
        # For now, return mock response
        return {
            "status": "success",
            "output": input_data,
            "execution_time": 30.0,
            "cpu_used": 256,
            "memory_used": 512,
        }

    def validate(self) -> bool:
        """Validate ECS operation."""
        return (
            self.config.resource_arn is not None
            and self.config.resource_arn.startswith("arn:aws:ecs:")
            and self.cluster_name is not None
            and self.config.timeout_seconds > 0
            and self.config.retry_count >= 0
        )


class Job(BaseModel):
    """Job model representing a Step Functions state machine."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Job name")
    description: Optional[str] = Field(None, description="Job description")

    # Operations
    operations: List[Operation] = Field(default_factory=list)

    # Dependencies
    dependencies: List[str] = Field(
        default_factory=list, description="Job IDs this job depends on"
    )

    # Status and lifecycle
    status: JobStatus = Field(default=JobStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)

    # Execution details
    execution_arn: Optional[str] = Field(
        None, description="Step Functions execution ARN"
    )
    state_machine_arn: Optional[str] = Field(
        None, description="Step Functions state machine ARN"
    )

    # Configuration
    timeout_seconds: int = Field(3600, ge=0)
    retry_count: int = Field(3, ge=0)
    retry_delay_seconds: int = Field(60, ge=0)

    # Error handling
    error_message: Optional[str] = Field(None)
    error_code: Optional[str] = Field(None)

    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("status")
    def validate_status(cls, v):
        """Validate job status."""
        if isinstance(v, str):
            try:
                return JobStatus(v)
            except ValueError:
                raise ValidationError(
                    message=f"Invalid job status: {v}",
                    field_name="status",
                    field_value=v,
                )
        return v

    @validator("updated_at", always=True)
    def set_updated_at(cls, v, values):
        """Always update the updated_at timestamp."""
        return datetime.utcnow()

    def add_operation(self, operation: Operation) -> None:
        """Add an operation to the job."""
        self.operations.append(operation)
        self.updated_at = datetime.utcnow()

    def remove_operation(self, operation_id: str) -> bool:
        """Remove an operation from the job."""
        for i, operation in enumerate(self.operations):
            if operation.operation_id == operation_id:
                self.operations.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """Get operation by ID."""
        for operation in self.operations:
            if operation.operation_id == operation_id:
                return operation
        return None

    def add_dependency(self, job_id: str) -> None:
        """Add a job dependency."""
        if job_id not in self.dependencies:
            self.dependencies.append(job_id)
            self.updated_at = datetime.utcnow()

    def remove_dependency(self, job_id: str) -> bool:
        """Remove a job dependency."""
        if job_id in self.dependencies:
            self.dependencies.remove(job_id)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def has_dependency(self, job_id: str) -> bool:
        """Check if job has a dependency."""
        return job_id in self.dependencies

    def get_dependent_jobs(self, all_jobs: List["Job"]) -> List["Job"]:
        """Get jobs that depend on this job."""
        dependent_jobs = []
        for job in all_jobs:
            if self.job_id in job.dependencies:
                dependent_jobs.append(job)
        return dependent_jobs

    def can_start(self, completed_jobs: Set[str]) -> bool:
        """Check if job can start (all dependencies completed)."""
        return all(dep in completed_jobs for dep in self.dependencies)

    def set_error(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Set error information."""
        self.error_message = error_message
        self.error_code = error_code
        self.status = JobStatus.FAILED
        self.updated_at = datetime.utcnow()

    def clear_error(self) -> None:
        """Clear error information."""
        self.error_message = None
        self.error_code = None
        self.updated_at = datetime.utcnow()

    def is_terminal_state(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMEOUT,
        }

    def is_running_state(self) -> bool:
        """Check if job is in a running state."""
        return self.status in {JobStatus.RUNNING}

    def can_transition_to(self, new_status: JobStatus) -> bool:
        """Check if job can transition to new status."""
        valid_transitions = {
            JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.CANCELLED},
            JobStatus.RUNNING: {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.TIMEOUT,
            },
            JobStatus.COMPLETED: set(),
            JobStatus.FAILED: {JobStatus.RUNNING},  # Retry
            JobStatus.CANCELLED: set(),
            JobStatus.TIMEOUT: {JobStatus.RUNNING},  # Retry
        }
        return new_status in valid_transitions.get(self.status, set())

    def transition_to(
        self, new_status: JobStatus, message: Optional[str] = None
    ) -> None:
        """Transition job to new status."""
        if not self.can_transition_to(new_status):
            raise ValidationError(
                message=f"Invalid status transition from {self.status} to {new_status}",
                field_name="status",
                field_value=new_status,
            )

        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if new_status == JobStatus.RUNNING and not self.started_at:
            self.started_at = datetime.utcnow()
        elif new_status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMEOUT,
        }:
            self.completed_at = datetime.utcnow()

        if message:
            self.metadata["status_change_message"] = message

    def get_duration(self) -> Optional[float]:
        """Get job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "description": self.description,
            "operations": [op.to_dict() for op in self.operations],
            "dependencies": self.dependencies,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "execution_arn": self.execution_arn,
            "state_machine_arn": self.state_machine_arn,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary."""
        # Convert operations back to Operation objects
        operations = []
        for op_data in data.get("operations", []):
            if op_data["config"]["operation_type"] == OperationType.LAMBDA.value:
                operations.append(LambdaOperation.from_dict(op_data))
            elif op_data["config"]["operation_type"] == OperationType.ECS.value:
                operations.append(ECSOperation.from_dict(op_data))
            # Add other operation types as needed

        job = cls(
            job_id=data["job_id"],
            name=data["name"],
            description=data.get("description"),
            operations=operations,
            dependencies=data.get("dependencies", []),
            status=JobStatus(data["status"]),
            started_at=None,
            completed_at=None,
            execution_arn=data.get("execution_arn"),
            state_machine_arn=data.get("state_machine_arn"),
            timeout_seconds=data.get("timeout_seconds", 3600),
            retry_count=data.get("retry_count", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 60),
            error_message=data.get("error_message"),
            error_code=data.get("error_code"),
            tags=data.get("tags", {}),
            metadata=data.get("metadata", {}),
        )

        # Set timestamps
        if "created_at" in data:
            job.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            job.updated_at = datetime.fromisoformat(data["updated_at"])
        if "started_at" in data and data["started_at"]:
            job.started_at = datetime.fromisoformat(data["started_at"])
        if "completed_at" in data and data["completed_at"]:
            job.completed_at = datetime.fromisoformat(data["completed_at"])

        return job

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        arbitrary_types_allowed = True


class Pipeline(BaseModel):
    """Pipeline model representing a data pipeline."""

    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Pipeline name")
    description: Optional[str] = Field(None, description="Pipeline description")
    version: str = Field("1.0.0", description="Pipeline version")

    # Jobs
    jobs: List[Job] = Field(default_factory=list)

    # Status and lifecycle
    status: PipelineStatus = Field(default=PipelineStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Configuration
    timeout_seconds: int = Field(3600, ge=0)
    max_concurrent_jobs: int = Field(10, ge=1)

    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # User context
    user_id: Optional[str] = Field(None)
    user_name: Optional[str] = Field(None)

    @validator("status")
    def validate_status(cls, v):
        """Validate pipeline status."""
        if isinstance(v, str):
            try:
                return PipelineStatus(v)
            except ValueError:
                raise ValidationError(
                    message=f"Invalid pipeline status: {v}",
                    field_name="status",
                    field_value=v,
                )
        return v

    @validator("updated_at", always=True)
    def set_updated_at(cls, v, values):
        """Always update the updated_at timestamp."""
        return datetime.utcnow()

    def add_job(self, job: Job) -> None:
        """Add a job to the pipeline."""
        self.jobs.append(job)
        self.updated_at = datetime.utcnow()

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the pipeline."""
        for i, job in enumerate(self.jobs):
            if job.job_id == job_id:
                self.jobs.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        return None

    def get_job_by_name(self, name: str) -> Optional[Job]:
        """Get job by name."""
        for job in self.jobs:
            if job.name == name:
                return job
        return None

    def validate_dependencies(self) -> bool:
        """Validate job dependencies."""
        job_ids = {job.job_id for job in self.jobs}
        for job in self.jobs:
            for dep_id in job.dependencies:
                if dep_id not in job_ids:
                    return False
        return True

    def detect_cycles(self) -> List[List[str]]:
        """Detect dependency cycles in the pipeline."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(job_id: str, path: List[str]) -> None:
            if job_id in rec_stack:
                # Found a cycle
                cycle_start = path.index(job_id)
                cycles.append(path[cycle_start:] + [job_id])
                return

            if job_id in visited:
                return

            visited.add(job_id)
            rec_stack.add(job_id)

            job = self.get_job(job_id)
            if job:
                for dep_id in job.dependencies:
                    dfs(dep_id, path + [job_id])

            rec_stack.remove(job_id)

        for job in self.jobs:
            if job.job_id not in visited:
                dfs(job.job_id, [])

        return cycles

    def get_execution_order(self) -> List[str]:
        """Get job execution order based on dependencies."""
        if not self.validate_dependencies():
            raise ValidationError(
                message="Invalid dependencies detected",
                field_name="jobs",
                field_value="dependencies",
            )

        cycles = self.detect_cycles()
        if cycles:
            raise ValidationError(
                message=f"Circular dependencies detected: {cycles}",
                field_name="jobs",
                field_value="dependencies",
            )

        # Topological sort
        in_degree = {job.job_id: 0 for job in self.jobs}
        for job in self.jobs:
            for dep_id in job.dependencies:
                in_degree[dep_id] += 1

        queue = [job_id for job_id, degree in in_degree.items() if degree == 0]
        execution_order = []

        while queue:
            job_id = queue.pop(0)
            execution_order.append(job_id)

            job = self.get_job(job_id)
            if job:
                for dep_id in job.dependencies:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        queue.append(dep_id)

        return execution_order

    def get_ready_jobs(self, completed_jobs: Set[str]) -> List[Job]:
        """Get jobs that are ready to execute."""
        ready_jobs = []
        for job in self.jobs:
            if job.status == JobStatus.PENDING and job.can_start(completed_jobs):
                ready_jobs.append(job)
        return ready_jobs

    def get_job_stats(self) -> Dict[str, Any]:
        """Get pipeline job statistics."""
        total_jobs = len(self.jobs)
        completed_jobs = sum(
            1 for job in self.jobs if job.status == JobStatus.COMPLETED
        )
        failed_jobs = sum(1 for job in self.jobs if job.status == JobStatus.FAILED)
        running_jobs = sum(1 for job in self.jobs if job.status == JobStatus.RUNNING)
        pending_jobs = sum(1 for job in self.jobs if job.status == JobStatus.PENDING)

        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "running_jobs": running_jobs,
            "pending_jobs": pending_jobs,
            "completion_percentage": (
                (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert pipeline to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "jobs": [job.to_dict() for job in self.jobs],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "tags": self.tags,
            "metadata": self.metadata,
            "user_id": self.user_id,
            "user_name": self.user_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pipeline":
        """Create pipeline from dictionary."""
        jobs = [Job.from_dict(job_data) for job_data in data.get("jobs", [])]

        pipeline = cls(
            pipeline_id=data["pipeline_id"],
            name=data["name"],
            description=data.get("description"),
            version=data.get("version", "1.0.0"),
            jobs=jobs,
            status=PipelineStatus(data["status"]),
            timeout_seconds=data.get("timeout_seconds", 3600),
            max_concurrent_jobs=data.get("max_concurrent_jobs", 10),
            tags=data.get("tags", {}),
            metadata=data.get("metadata", {}),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
        )

        # Set timestamps
        if "created_at" in data:
            pipeline.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            pipeline.updated_at = datetime.fromisoformat(data["updated_at"])

        return pipeline

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        arbitrary_types_allowed = True
