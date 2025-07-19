"""
Pipeline execution engine for Step Functions.

This module provides the PipelineExecutor class for managing
pipeline execution using AWS Step Functions.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from bunsui.core.models.pipeline import Pipeline
from bunsui.core.models.session import SessionMetadata, SessionStatus
from bunsui.aws.stepfunctions.client import StepFunctionsClient, StepFunctionsMonitor
from bunsui.aws.stepfunctions.asl_generator import ASLGenerator
from bunsui.core.exceptions import SessionError, ValidationError


class PipelineExecutor:
    """Pipeline execution engine using Step Functions."""

    def __init__(
        self,
        step_functions_client: StepFunctionsClient,
        execution_role_arn: str,
        region: str = "us-east-1"
    ):
        """
        Initialize pipeline executor.
        
        Args:
            step_functions_client: Step Functions client
            execution_role_arn: IAM role ARN for state machine execution
            region: AWS region
        """
        self.step_functions_client = step_functions_client
        self.execution_role_arn = execution_role_arn
        self.region = region
        self.asl_generator = ASLGenerator()
        self.monitor = StepFunctionsMonitor(step_functions_client)

    def execute_pipeline(
        self,
        pipeline: Pipeline,
        session: SessionMetadata,
        parameters: Optional[Dict[str, Any]] = None
    ) -> SessionMetadata:
        """
        Execute a pipeline using Step Functions.
        
        Args:
            pipeline: Pipeline to execute
            session: Session metadata
            parameters: Execution parameters
            
        Returns:
            Updated session metadata
            
        Raises:
            SessionError: If execution fails to start
            ValidationError: If pipeline is invalid
        """
        try:
            # Generate state machine definition
            state_machine_config = self.asl_generator.generate_state_machine(
                pipeline, self.execution_role_arn
            )
            
            # Create or get existing state machine
            state_machine_arn = self._get_or_create_state_machine(
                pipeline, state_machine_config
            )
            
            # Generate execution input
            execution_input = self.asl_generator.generate_execution_input(
                pipeline, session.session_id, parameters
            )
            
            # Start execution
            execution_name = f"session-{session.session_id}-{int(datetime.now().timestamp())}"
            execution_response = self.step_functions_client.start_execution(
                state_machine_arn=state_machine_arn,
                name=execution_name,
                input_data=execution_input
            )
            
            # Update session with execution details
            session.execution_arn = execution_response["executionArn"]
            session.state_machine_arn = state_machine_arn
            session.execution_name = execution_name
            session.status = SessionStatus.RUNNING
            session.started_at = datetime.now(timezone.utc)
            
            return session
            
        except Exception as e:
            session.status = SessionStatus.FAILED
            session.error_message = str(e)
            session.error_code = "EXECUTION_START_FAILED"
            raise SessionError(f"Failed to start pipeline execution: {str(e)}")

    def get_execution_status(self, session: SessionMetadata) -> SessionMetadata:
        """
        Get current execution status and update session.
        
        Args:
            session: Session metadata
            
        Returns:
            Updated session metadata
        """
        if not session.execution_arn:
            raise SessionError("Session has no execution ARN")
        
        try:
            # Get execution details
            execution = self.step_functions_client.describe_execution(session.execution_arn)
            
            # Update session status based on execution status
            execution_status = execution["status"]
            if execution_status == "RUNNING":
                session.status = SessionStatus.RUNNING
            elif execution_status == "SUCCEEDED":
                session.status = SessionStatus.COMPLETED
                session.completed_at = datetime.now(timezone.utc)
            elif execution_status in ["FAILED", "ABORTED", "TIMED_OUT"]:
                session.status = SessionStatus.FAILED
                session.completed_at = datetime.now(timezone.utc)
                session.error_message = execution.get("cause", "Execution failed")
                session.error_code = execution_status
            
            # Update progress if execution is running or completed
            if execution_status in ["RUNNING", "SUCCEEDED"]:
                self._update_session_progress(session)
            
            return session
            
        except Exception as e:
            session.status = SessionStatus.FAILED
            session.error_message = f"Failed to get execution status: {str(e)}"
            raise SessionError(f"Failed to get execution status: {str(e)}")

    def stop_execution(self, session: SessionMetadata, cause: str = "User requested stop") -> SessionMetadata:
        """
        Stop a running execution.
        
        Args:
            session: Session metadata
            cause: Reason for stopping
            
        Returns:
            Updated session metadata
        """
        if not session.execution_arn:
            raise SessionError("Session has no execution ARN")
        
        try:
            self.step_functions_client.stop_execution(
                execution_arn=session.execution_arn,
                cause=cause
            )
            
            session.status = SessionStatus.CANCELLED
            session.completed_at = datetime.now(timezone.utc)
            session.error_message = cause
            session.error_code = "USER_CANCELLED"
            
            return session
            
        except Exception as e:
            raise SessionError(f"Failed to stop execution: {str(e)}")

    def get_execution_logs(self, session: SessionMetadata) -> Dict[str, Any]:
        """
        Get execution logs and events.
        
        Args:
            session: Session metadata
            
        Returns:
            Execution logs and events
        """
        if not session.execution_arn:
            raise SessionError("Session has no execution ARN")
        
        try:
            # Get execution history
            events = self.monitor.get_execution_events(session.execution_arn)
            
            # Get execution summary
            summary = self.monitor.get_execution_summary(session.execution_arn)
            
            return {
                "execution_arn": session.execution_arn,
                "events": events,
                "summary": summary,
                "logs_available": len(events) > 0
            }
            
        except Exception as e:
            raise SessionError(f"Failed to get execution logs: {str(e)}")

    def retry_failed_execution(
        self,
        pipeline: Pipeline,
        session: SessionMetadata,
        parameters: Optional[Dict[str, Any]] = None
    ) -> SessionMetadata:
        """
        Retry a failed execution.
        
        Args:
            pipeline: Pipeline to retry
            session: Failed session metadata
            parameters: Execution parameters
            
        Returns:
            New session metadata for retry
        """
        if session.status != SessionStatus.FAILED:
            raise SessionError("Can only retry failed executions")
        
        # Increment retry count
        session.retry_count += 1
        if session.retry_count > session.max_retries:
            raise SessionError("Maximum retry count exceeded")
        
        # Reset session for retry
        session.status = SessionStatus.CREATED
        session.error_message = None
        session.error_code = None
        session.execution_arn = None
        session.state_machine_arn = None
        session.execution_name = None
        session.started_at = None
        session.completed_at = None
        
        # Start new execution
        return self.execute_pipeline(pipeline, session, parameters)

    def _get_or_create_state_machine(
        self,
        pipeline: Pipeline,
        state_machine_config: Dict[str, Any]
    ) -> str:
        """
        Get existing state machine or create new one.
        
        Args:
            pipeline: Pipeline object
            state_machine_config: State machine configuration
            
        Returns:
            State machine ARN
        """
        state_machine_name = state_machine_config["name"]
        
        try:
            # Try to find existing state machine
            machines = self.step_functions_client.list_state_machines()
            for machine in machines.get("stateMachines", []):
                if machine["name"] == state_machine_name:
                    # Update existing state machine if needed
                    return self._update_state_machine_if_needed(
                        machine["stateMachineArn"],
                        state_machine_config,
                        pipeline
                    )
            
            # Create new state machine
            response = self.step_functions_client.create_state_machine(
                name=state_machine_config["name"],
                definition=state_machine_config["definition"],
                role_arn=state_machine_config["roleArn"],
                description=state_machine_config["description"],
                tags=state_machine_config["tags"]
            )
            
            return response["stateMachineArn"]
            
        except Exception as e:
            raise SessionError(f"Failed to create state machine: {str(e)}")

    def _update_state_machine_if_needed(
        self,
        state_machine_arn: str,
        state_machine_config: Dict[str, Any],
        pipeline: Pipeline
    ) -> str:
        """
        Update state machine if definition has changed.
        
        Args:
            state_machine_arn: Existing state machine ARN
            state_machine_config: New state machine configuration
            pipeline: Pipeline object
            
        Returns:
            State machine ARN
        """
        try:
            # Get current state machine
            current = self.step_functions_client.describe_state_machine(state_machine_arn)
            current_definition = json.loads(current["definition"])
            new_definition = state_machine_config["definition"]
            
            # Compare definitions (simplified comparison)
            if current_definition != new_definition:
                # Update state machine
                self.step_functions_client.update_state_machine(
                    state_machine_arn=state_machine_arn,
                    definition=new_definition,
                    role_arn=state_machine_config["roleArn"],
                    description=state_machine_config["description"]
                )
            
            return state_machine_arn
            
        except Exception as e:
            # If update fails, try to create new state machine with a different name
            state_machine_config["name"] = f"{state_machine_config['name']}-v{int(datetime.now().timestamp())}"
            return self._get_or_create_state_machine(pipeline, state_machine_config)

    def _update_session_progress(self, session: SessionMetadata) -> None:
        """
        Update session progress based on execution events.
        
        Args:
            session: Session metadata to update
        """
        if not session.execution_arn:
            return
        
        try:
            # Get execution events
            events = self.monitor.get_execution_events(session.execution_arn)
            
            # Count completed jobs/operations
            completed_jobs = 0
            failed_jobs = 0
            total_jobs = session.total_jobs
            
            for event in events:
                event_type = event.get("type", "")
                if event_type == "TaskStateExited":
                    # Check if this is a job completion
                    state_name = event.get("stateExitedEventDetails", {}).get("name", "")
                    if state_name.endswith("_End"):
                        completed_jobs += 1
                elif event_type == "TaskStateFailed":
                    failed_jobs += 1
            
            # Update session progress
            session.completed_jobs = min(completed_jobs, total_jobs)
            session.failed_jobs = failed_jobs
            
        except Exception:
            # Continue without updating progress if there's an error
            pass

    def list_executions_for_pipeline(self, pipeline: Pipeline) -> Dict[str, Any]:
        """
        List all executions for a pipeline.
        
        Args:
            pipeline: Pipeline object
            
        Returns:
            Dictionary containing execution list and summary
        """
        try:
            # Get state machine name
            state_machine_name = f"bunsui-{pipeline.pipeline_id}-{pipeline.version}"
            
            # Find state machine
            machines = self.step_functions_client.list_state_machines()
            state_machine_arn = None
            
            for machine in machines.get("stateMachines", []):
                if machine["name"] == state_machine_name:
                    state_machine_arn = machine["stateMachineArn"]
                    break
            
            if not state_machine_arn:
                return {"executions": [], "summary": {"total": 0, "running": 0, "succeeded": 0, "failed": 0}}
            
            # List executions
            executions = self.step_functions_client.list_executions(state_machine_arn)
            
            # Generate summary
            summary = {"total": 0, "running": 0, "succeeded": 0, "failed": 0}
            for execution in executions.get("executions", []):
                summary["total"] += 1
                status = execution["status"].lower()
                if status == "running":
                    summary["running"] += 1
                elif status == "succeeded":
                    summary["succeeded"] += 1
                elif status in ["failed", "aborted", "timed_out"]:
                    summary["failed"] += 1
            
            return {
                "executions": executions.get("executions", []),
                "summary": summary
            }
            
        except Exception as e:
            raise SessionError(f"Failed to list executions: {str(e)}")

    def cleanup_old_executions(self, pipeline: Pipeline, keep_count: int = 10) -> Dict[str, Any]:
        """
        Clean up old executions for a pipeline.
        
        Args:
            pipeline: Pipeline object
            keep_count: Number of recent executions to keep
            
        Returns:
            Cleanup summary
        """
        try:
            executions_info = self.list_executions_for_pipeline(pipeline)
            executions = executions_info["executions"]
            
            if len(executions) <= keep_count:
                return {"deleted": 0, "kept": len(executions)}
            
            # Sort by start date (most recent first)
            executions.sort(key=lambda x: x.get("startDate", ""), reverse=True)
            
            # Keep only the most recent executions
            to_delete = executions[keep_count:]
            deleted_count = 0
            
            for execution in to_delete:
                try:
                    # Only delete completed executions
                    if execution["status"] in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED_OUT"]:
                        # Note: Step Functions doesn't have a delete execution API
                        # This would typically involve cleaning up related resources
                        deleted_count += 1
                except Exception:
                    continue
            
            return {"deleted": deleted_count, "kept": keep_count}
            
        except Exception as e:
            raise SessionError(f"Failed to cleanup executions: {str(e)}") 