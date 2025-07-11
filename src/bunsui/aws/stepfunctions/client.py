"""
Step Functions client implementation for bunsui.

This module provides a high-level interface for Step Functions operations,
integrating with the AWS client wrapper for state machine execution management.
"""

from typing import Dict, Any, List, Optional, Union
import json

from bunsui.aws.client import AWSClient


class StepFunctionsClient:
    """High-level Step Functions client for bunsui operations."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize Step Functions client."""
        self.aws_client = AWSClient("stepfunctions", region)
        self.region = region

    def create_state_machine(
        self,
        name: str,
        definition: Dict[str, Any],
        role_arn: str,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a Step Functions state machine."""
        params: Dict[str, Any] = {
            "name": name,
            "definition": json.dumps(definition),
            "roleArn": role_arn,
        }

        if description:
            params["description"] = description
        if tags:
            params["tags"] = [{"key": k, "value": v} for k, v in tags.items()]

        return self.aws_client.call_api("create_state_machine", **params)

    def delete_state_machine(self, state_machine_arn: str) -> Dict[str, Any]:
        """Delete a Step Functions state machine."""
        return self.aws_client.call_api("delete_state_machine", stateMachineArn=state_machine_arn)

    def describe_state_machine(self, state_machine_arn: str) -> Dict[str, Any]:
        """Describe a Step Functions state machine."""
        return self.aws_client.call_api("describe_state_machine", stateMachineArn=state_machine_arn)

    def list_state_machines(self, max_results: Optional[int] = None) -> Dict[str, Any]:
        """List Step Functions state machines."""
        params: Dict[str, Any] = {}
        if max_results:
            params["maxResults"] = max_results

        return self.aws_client.call_api("list_state_machines", **params)

    def start_execution(
        self,
        state_machine_arn: str,
        name: Optional[str] = None,
        input_data: Optional[Union[str, Dict[str, Any]]] = None,
        trace_header: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start a Step Functions execution."""
        params: Dict[str, Any] = {"stateMachineArn": state_machine_arn}

        if name:
            params["name"] = name
        if input_data:
            if isinstance(input_data, dict):
                params["input"] = json.dumps(input_data)
            else:
                params["input"] = input_data
        if trace_header:
            params["traceHeader"] = trace_header

        return self.aws_client.call_api("start_execution", **params)

    def stop_execution(
        self,
        execution_arn: str,
        cause: Optional[str] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stop a Step Functions execution."""
        params: Dict[str, Any] = {"executionArn": execution_arn}

        if cause:
            params["cause"] = cause
        if error:
            params["error"] = error

        return self.aws_client.call_api("stop_execution", **params)

    def describe_execution(self, execution_arn: str) -> Dict[str, Any]:
        """Describe a Step Functions execution."""
        return self.aws_client.call_api("describe_execution", executionArn=execution_arn)

    def list_executions(
        self,
        state_machine_arn: str,
        status_filter: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """List Step Functions executions."""
        params: Dict[str, Any] = {"stateMachineArn": state_machine_arn}

        if status_filter:
            params["statusFilter"] = status_filter
        if max_results:
            params["maxResults"] = max_results

        return self.aws_client.call_api("list_executions", **params)

    def get_execution_history(
        self,
        execution_arn: str,
        max_results: Optional[int] = None,
        reverse_order: bool = False
    ) -> Dict[str, Any]:
        """Get execution history."""
        params: Dict[str, Any] = {"executionArn": execution_arn, "reverseOrder": reverse_order}

        if max_results:
            params["maxResults"] = max_results

        return self.aws_client.call_api("get_execution_history", **params)

    def update_state_machine(
        self,
        state_machine_arn: str,
        definition: Optional[Dict[str, Any]] = None,
        role_arn: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a Step Functions state machine."""
        params: Dict[str, Any] = {"stateMachineArn": state_machine_arn}

        if definition:
            params["definition"] = json.dumps(definition)
        if role_arn:
            params["roleArn"] = role_arn
        if description:
            params["description"] = description

        return self.aws_client.call_api("update_state_machine", **params)

    def tag_resource(self, resource_arn: str, tags: Dict[str, str]) -> Dict[str, Any]:
        """Tag a Step Functions resource."""
        tag_list = [{"key": k, "value": v} for k, v in tags.items()]
        return self.aws_client.call_api("tag_resource", resourceArn=resource_arn, tags=tag_list)

    def untag_resource(self, resource_arn: str, tag_keys: List[str]) -> Dict[str, Any]:
        """Remove tags from a Step Functions resource."""
        return self.aws_client.call_api("untag_resource", resourceArn=resource_arn, tagKeys=tag_keys)

    def list_tags_for_resource(self, resource_arn: str) -> Dict[str, Any]:
        """List tags for a Step Functions resource."""
        return self.aws_client.call_api("list_tags_for_resource", resourceArn=resource_arn)


class StepFunctionsMonitor:
    """Step Functions execution monitor."""

    def __init__(self, client: StepFunctionsClient):
        """Initialize Step Functions monitor."""
        self.client = client

    def get_execution_status(self, execution_arn: str) -> Optional[str]:
        """Get execution status."""
        try:
            response = self.client.describe_execution(execution_arn)
            return response["status"]
        except Exception:
            return None

    def wait_for_execution_completion(
        self,
        execution_arn: str,
        timeout: int = 3600,
        check_interval: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Wait for execution to complete."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_execution_status(execution_arn)
            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED_OUT"]:
                return self.client.describe_execution(execution_arn)
            elif status in ["RUNNING", "STARTING"]:
                time.sleep(check_interval)
            else:
                return None

        return None

    def get_execution_output(self, execution_arn: str) -> Optional[Dict[str, Any]]:
        """Get execution output."""
        try:
            response = self.client.describe_execution(execution_arn)
            if "output" in response:
                return json.loads(response["output"])
            return None
        except Exception:
            return None

    def get_execution_error(self, execution_arn: str) -> Optional[Dict[str, Any]]:
        """Get execution error details."""
        try:
            response = self.client.describe_execution(execution_arn)
            if "cause" in response:
                return {
                    "cause": response["cause"],
                    "error": response.get("error"),
                    "status": response["status"]
                }
            return None
        except Exception:
            return None

    def get_execution_duration(self, execution_arn: str) -> Optional[float]:
        """Get execution duration in seconds."""
        try:
            response = self.client.describe_execution(execution_arn)
            if "startDate" in response and "stopDate" in response:
                start_time = response["startDate"]
                stop_time = response["stopDate"]
                return (stop_time - start_time).total_seconds()
            return None
        except Exception:
            return None

    def list_running_executions(self, state_machine_arn: str) -> List[Dict[str, Any]]:
        """List running executions for a state machine."""
        try:
            response = self.client.list_executions(
                state_machine_arn,
                status_filter="RUNNING"
            )
            return response.get("executions", [])
        except Exception:
            return []

    def list_failed_executions(self, state_machine_arn: str) -> List[Dict[str, Any]]:
        """List failed executions for a state machine."""
        try:
            response = self.client.list_executions(
                state_machine_arn,
                status_filter="FAILED"
            )
            return response.get("executions", [])
        except Exception:
            return []

    def get_execution_events(
        self,
        execution_arn: str,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get execution events."""
        try:
            response = self.client.get_execution_history(
                execution_arn,
                max_results=max_results
            )
            return response.get("events", [])
        except Exception:
            return []

    def get_execution_summary(self, execution_arn: str) -> Optional[Dict[str, Any]]:
        """Get execution summary."""
        try:
            response = self.client.describe_execution(execution_arn)
            return {
                "execution_arn": execution_arn,
                "status": response["status"],
                "start_date": response.get("startDate"),
                "stop_date": response.get("stopDate"),
                "duration": self.get_execution_duration(execution_arn),
                "output": self.get_execution_output(execution_arn),
                "error": self.get_execution_error(execution_arn)
            }
        except Exception:
            return None
