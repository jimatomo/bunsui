"""
Amazon States Language (ASL) generator for bunsui pipelines.

This module provides the ASLGenerator class for converting
Pipeline definitions to Step Functions state machine definitions.
"""

import json
from typing import Dict, Any, List, Set, Optional
from uuid import uuid4

from bunsui.core.models.pipeline import Pipeline, Job, Operation, OperationType


class ASLGenerator:
    """Generator for Amazon States Language state machine definitions."""

    def __init__(self):
        """Initialize ASL generator."""
        self.operation_timeout = 3600  # Default operation timeout
        self.retry_attempts = 3  # Default retry attempts

    def generate_state_machine(self, pipeline: Pipeline, role_arn: str) -> Dict[str, Any]:
        """
        Generate Step Functions state machine definition from pipeline.
        
        Args:
            pipeline: Pipeline object to convert
            role_arn: IAM role ARN for state machine execution
            
        Returns:
            Step Functions state machine definition
        """
        # Validate pipeline
        if not pipeline.validate_dependencies():
            raise ValueError("Pipeline has invalid dependencies")
        
        cycles = pipeline.detect_cycles()
        if cycles:
            raise ValueError(f"Pipeline has dependency cycles: {cycles}")
        
        # Generate states based on job execution order
        execution_order = pipeline.get_execution_order()
        states = self._generate_states(pipeline, execution_order)
        
        # Create state machine definition
        definition = {
            "Comment": f"State machine for pipeline: {pipeline.name}",
            "StartAt": self._get_start_state(execution_order),
            "States": states,
            "TimeoutSeconds": pipeline.timeout_seconds
        }
        
        return {
            "name": f"bunsui-{pipeline.pipeline_id}-{pipeline.version}",
            "definition": definition,
            "roleArn": role_arn,
            "description": f"Pipeline: {pipeline.name} (v{pipeline.version})",
            "tags": {
                "BunsuiPipeline": pipeline.pipeline_id,
                "BunsuiVersion": pipeline.version,
                "BunsuiEnvironment": "production"
            }
        }

    def _generate_states(self, pipeline: Pipeline, execution_order: List[str]) -> Dict[str, Any]:
        """Generate states for the state machine."""
        states = {}
        
        # Create job lookup
        job_lookup = {job.job_id: job for job in pipeline.jobs}
        
        for i, job_id in enumerate(execution_order):
            job = job_lookup[job_id]
            
            # Generate states for this job
            job_states = self._generate_job_states(job)
            states.update(job_states)
            
            # Determine next state
            if i < len(execution_order) - 1:
                next_job_id = execution_order[i + 1]
                next_state = f"Job_{next_job_id}_Start"
            else:
                next_state = "PipelineSuccess"
            
            # Connect job end to next state
            job_end_state = f"Job_{job_id}_End"
            if job_end_state in states:
                states[job_end_state]["Next"] = next_state
        
        # Add final success and failure states
        states["PipelineSuccess"] = {
            "Type": "Succeed",
            "Comment": "Pipeline completed successfully"
        }
        
        states["PipelineFailure"] = {
            "Type": "Fail",
            "Comment": "Pipeline failed",
            "Cause": "One or more jobs failed"
        }
        
        return states

    def _generate_job_states(self, job: Job) -> Dict[str, Any]:
        """Generate states for a single job."""
        states = {}
        
        # Job start state
        job_start_state = f"Job_{job.job_id}_Start"
        states[job_start_state] = {
            "Type": "Pass",
            "Comment": f"Starting job: {job.name}",
            "Parameters": {
                "job_id": job.job_id,
                "job_name": job.name,
                "pipeline_id.$": "$.pipeline_id",
                "session_id.$": "$.session_id",
                "started_at.$": "$$.State.EnteredTime"
            },
            "ResultPath": "$.current_job",
            "Next": f"Job_{job.job_id}_Operations"
        }
        
        # Generate operation states
        if len(job.operations) == 1:
            # Single operation
            operation = job.operations[0]
            op_states = self._generate_operation_states(job, operation)
            states.update(op_states)
            
            states[f"Job_{job.job_id}_Operations"] = {
                "Type": "Pass",
                "Next": f"Operation_{operation.operation_id}"
            }
        else:
            # Multiple operations - use parallel execution
            branches = []
            for operation in job.operations:
                op_states = self._generate_operation_states(job, operation)
                states.update(op_states)
                
                branch = {
                    "StartAt": f"Operation_{operation.operation_id}",
                    "States": {
                        state_name: state_def for state_name, state_def in op_states.items()
                        if state_name.startswith(f"Operation_{operation.operation_id}")
                    }
                }
                branches.append(branch)
            
            states[f"Job_{job.job_id}_Operations"] = {
                "Type": "Parallel",
                "Comment": f"Execute operations for job: {job.name}",
                "Branches": branches,
                "Next": f"Job_{job.job_id}_End",
                "Catch": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "Next": "PipelineFailure",
                        "ResultPath": "$.error"
                    }
                ]
            }
        
        # Job end state
        states[f"Job_{job.job_id}_End"] = {
            "Type": "Pass",
            "Comment": f"Completed job: {job.name}",
            "Parameters": {
                "job_id": job.job_id,
                "status": "completed",
                "completed_at.$": "$$.State.EnteredTime"
            },
            "ResultPath": "$.job_result"
        }
        
        return states

    def _generate_operation_states(self, job: Job, operation: Operation) -> Dict[str, Any]:
        """Generate states for a single operation."""
        states = {}
        
        operation_state_name = f"Operation_{operation.operation_id}"
        
        if operation.config.operation_type == OperationType.LAMBDA:
            states[operation_state_name] = self._generate_lambda_state(job, operation)
        elif operation.config.operation_type == OperationType.ECS:
            states[operation_state_name] = self._generate_ecs_state(job, operation)
        else:
            # Default task state
            states[operation_state_name] = self._generate_generic_task_state(job, operation)
        
        # Add retry and error handling
        states[operation_state_name]["Retry"] = [
            {
                "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"],
                "IntervalSeconds": operation.config.retry_delay_seconds,
                "MaxAttempts": operation.config.retry_count,
                "BackoffRate": 2.0
            }
        ]
        
        states[operation_state_name]["Catch"] = [
            {
                "ErrorEquals": ["States.ALL"],
                "Next": "PipelineFailure",
                "ResultPath": "$.error"
            }
        ]
        
        return states

    def _generate_lambda_state(self, job: Job, operation: Operation) -> Dict[str, Any]:
        """Generate Lambda task state."""
        return {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Comment": f"Execute Lambda operation: {operation.name}",
            "Parameters": {
                "FunctionName": operation.config.resource_arn,
                "Payload": {
                    "job_id": job.job_id,
                    "operation_id": operation.operation_id,
                    "pipeline_id.$": "$.pipeline_id",
                    "session_id.$": "$.session_id",
                    "input.$": "$",
                    "parameters": operation.config.parameters,
                    "environment": operation.config.environment_variables
                }
            },
            "ResultPath": f"$.operation_results.{operation.operation_id}",
            "TimeoutSeconds": operation.config.timeout_seconds,
            "Next": f"Job_{job.job_id}_End"
        }

    def _generate_ecs_state(self, job: Job, operation: Operation) -> Dict[str, Any]:
        """Generate ECS task state."""
        return {
            "Type": "Task",
            "Resource": "arn:aws:states:::ecs:runTask.sync",
            "Comment": f"Execute ECS operation: {operation.name}",
            "Parameters": {
                "TaskDefinition": operation.config.resource_arn,
                "Cluster": operation.config.parameters.get("cluster", "default"),
                "LaunchType": "FARGATE",
                "NetworkConfiguration": {
                    "AwsvpcConfiguration": {
                        "AssignPublicIp": "ENABLED",
                        "Subnets": operation.config.parameters.get("subnets", []),
                        "SecurityGroups": operation.config.parameters.get("security_groups", [])
                    }
                },
                "Overrides": {
                    "ContainerOverrides": [
                        {
                            "Name": operation.config.parameters.get("container_name", "default"),
                            "Environment": [
                                {"Name": k, "Value": v}
                                for k, v in operation.config.environment_variables.items()
                            ]
                        }
                    ]
                }
            },
            "ResultPath": f"$.operation_results.{operation.operation_id}",
            "TimeoutSeconds": operation.config.timeout_seconds,
            "Next": f"Job_{job.job_id}_End"
        }

    def _generate_generic_task_state(self, job: Job, operation: Operation) -> Dict[str, Any]:
        """Generate generic task state for unknown operation types."""
        return {
            "Type": "Pass",
            "Comment": f"Placeholder for operation: {operation.name} (type: {operation.config.operation_type})",
            "Parameters": {
                "operation_id": operation.operation_id,
                "operation_type": operation.config.operation_type.value,
                "status": "skipped",
                "message": "Operation type not implemented"
            },
            "ResultPath": f"$.operation_results.{operation.operation_id}",
            "Next": f"Job_{job.job_id}_End"
        }

    def _get_start_state(self, execution_order: List[str]) -> str:
        """Get the name of the starting state."""
        if execution_order:
            return f"Job_{execution_order[0]}_Start"
        return "PipelineSuccess"

    def generate_execution_input(self, pipeline: Pipeline, session_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate input data for state machine execution.
        
        Args:
            pipeline: Pipeline object
            session_id: Session identifier
            parameters: Additional parameters
            
        Returns:
            Input data for Step Functions execution
        """
        if parameters is None:
            parameters = {}
            
        return {
            "pipeline_id": pipeline.pipeline_id,
            "pipeline_name": pipeline.name,
            "pipeline_version": pipeline.version,
            "session_id": session_id,
            "parameters": parameters,
            "started_at": "${currentTime}",
            "operation_results": {},
            "job_results": {}
        }

    def validate_state_machine_definition(self, definition: Dict[str, Any]) -> bool:
        """
        Validate state machine definition.
        
        Args:
            definition: State machine definition
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic validation
            required_fields = ["Comment", "StartAt", "States"]
            for field in required_fields:
                if field not in definition:
                    return False
            
            # Validate StartAt state exists
            start_state = definition["StartAt"]
            if start_state not in definition["States"]:
                return False
            
            # Validate state transitions
            states = definition["States"]
            for state_name, state_def in states.items():
                if "Next" in state_def:
                    next_state = state_def["Next"]
                    if next_state not in states:
                        return False
            
            return True
        except Exception:
            return False

    def optimize_state_machine(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize state machine definition for better performance.
        
        Args:
            definition: Original state machine definition
            
        Returns:
            Optimized state machine definition
        """
        # Remove unnecessary Pass states
        optimized_states = {}
        
        for state_name, state_def in definition["States"].items():
            if state_def.get("Type") == "Pass" and "Parameters" not in state_def:
                # Skip simple pass states that don't modify data
                continue
            optimized_states[state_name] = state_def
        
        # Update Next pointers to skip removed states
        # This is a simplified optimization - full implementation would be more complex
        
        return {
            **definition,
            "States": optimized_states
        } 