"""
ECS client implementation for bunsui.

This module provides a high-level interface for ECS operations,
integrating with the AWS client wrapper for task execution management.
"""

import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from bunsui.aws.client import AWSClient
from bunsui.core.exceptions import ValidationError


class ECSClient:
    """High-level ECS client for bunsui operations."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize ECS client."""
        self.aws_client = AWSClient("ecs", region)
        self.region = region

    def run_task(
        self,
        task_definition: str,
        cluster: str = "default",
        launch_type: str = "FARGATE",
        count: int = 1,
        overrides: Optional[Dict[str, Any]] = None,
        network_configuration: Optional[Dict[str, Any]] = None,
        platform_version: Optional[str] = None,
        placement_constraints: Optional[List[Dict[str, Any]]] = None,
        placement_strategy: Optional[List[Dict[str, Any]]] = None,
        started_by: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        enable_execute_command: bool = False,
        enable_ecs_managed_tags: bool = False,
        propagate_tags: Optional[str] = None,
        group: Optional[str] = None,
        capacity_provider_strategy: Optional[List[Dict[str, Any]]] = None,
        reference_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a task using ECS.
        
        Args:
            task_definition: Task definition ARN or family:revision
            cluster: Cluster name or ARN
            launch_type: FARGATE, EC2, or EXTERNAL
            count: Number of tasks to run
            overrides: Task override configuration
            network_configuration: Network configuration for FARGATE
            platform_version: Platform version for FARGATE
            placement_constraints: Task placement constraints
            placement_strategy: Task placement strategy
            started_by: Optional identifier for task starter
            tags: Task tags
            enable_execute_command: Enable ECS Exec
            enable_ecs_managed_tags: Enable ECS managed tags
            propagate_tags: Propagate tags from task definition or service
            group: Task group name
            capacity_provider_strategy: Capacity provider strategy
            reference_id: Reference ID for idempotency
            
        Returns:
            Task run response
        """
        params: Dict[str, Any] = {
            "taskDefinition": task_definition,
            "cluster": cluster,
            "launchType": launch_type,
            "count": count,
            "enableExecuteCommand": enable_execute_command,
            "enableECSManagedTags": enable_ecs_managed_tags
        }

        if overrides:
            params["overrides"] = overrides
        if network_configuration:
            params["networkConfiguration"] = network_configuration
        if platform_version:
            params["platformVersion"] = platform_version
        if placement_constraints:
            params["placementConstraints"] = placement_constraints
        if placement_strategy:
            params["placementStrategy"] = placement_strategy
        if started_by:
            params["startedBy"] = started_by
        if tags:
            params["tags"] = tags
        if propagate_tags:
            params["propagateTags"] = propagate_tags
        if group:
            params["group"] = group
        if capacity_provider_strategy:
            params["capacityProviderStrategy"] = capacity_provider_strategy
        if reference_id:
            params["referenceId"] = reference_id

        return self.aws_client.call_api("run_task", **params)

    def describe_tasks(
        self,
        tasks: List[str],
        cluster: str = "default",
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Describe ECS tasks."""
        params: Dict[str, Any] = {
            "tasks": tasks,
            "cluster": cluster
        }
        if include:
            params["include"] = include

        return self.aws_client.call_api("describe_tasks", **params)

    def stop_task(
        self,
        task: str,
        cluster: str = "default",
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stop an ECS task."""
        params: Dict[str, Any] = {
            "task": task,
            "cluster": cluster
        }
        if reason:
            params["reason"] = reason

        return self.aws_client.call_api("stop_task", **params)

    def list_tasks(
        self,
        cluster: str = "default",
        container_instance: Optional[str] = None,
        family: Optional[str] = None,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
        started_by: Optional[str] = None,
        service_name: Optional[str] = None,
        desired_status: Optional[str] = None,
        launch_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """List ECS tasks."""
        params: Dict[str, Any] = {"cluster": cluster}

        if container_instance:
            params["containerInstance"] = container_instance
        if family:
            params["family"] = family
        if next_token:
            params["nextToken"] = next_token
        if max_results:
            params["maxResults"] = max_results
        if started_by:
            params["startedBy"] = started_by
        if service_name:
            params["serviceName"] = service_name
        if desired_status:
            params["desiredStatus"] = desired_status
        if launch_type:
            params["launchType"] = launch_type

        return self.aws_client.call_api("list_tasks", **params)

    def describe_task_definition(self, task_definition: str, include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Describe a task definition."""
        params: Dict[str, Any] = {"taskDefinition": task_definition}
        if include:
            params["include"] = include

        return self.aws_client.call_api("describe_task_definition", **params)

    def register_task_definition(
        self,
        family: str,
        container_definitions: List[Dict[str, Any]],
        task_role_arn: Optional[str] = None,
        execution_role_arn: Optional[str] = None,
        network_mode: Optional[str] = None,
        requires_compatibilities: Optional[List[str]] = None,
        cpu: Optional[str] = None,
        memory: Optional[str] = None,
        volumes: Optional[List[Dict[str, Any]]] = None,
        placement_constraints: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        pid_mode: Optional[str] = None,
        ipc_mode: Optional[str] = None,
        proxy_configuration: Optional[Dict[str, Any]] = None,
        inference_accelerators: Optional[List[Dict[str, Any]]] = None,
        ephemeral_storage: Optional[Dict[str, Any]] = None,
        runtime_platform: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Register a new task definition."""
        params: Dict[str, Any] = {
            "family": family,
            "containerDefinitions": container_definitions
        }

        if task_role_arn:
            params["taskRoleArn"] = task_role_arn
        if execution_role_arn:
            params["executionRoleArn"] = execution_role_arn
        if network_mode:
            params["networkMode"] = network_mode
        if requires_compatibilities:
            params["requiresCompatibilities"] = requires_compatibilities
        if cpu:
            params["cpu"] = cpu
        if memory:
            params["memory"] = memory
        if volumes:
            params["volumes"] = volumes
        if placement_constraints:
            params["placementConstraints"] = placement_constraints
        if tags:
            params["tags"] = tags
        if pid_mode:
            params["pidMode"] = pid_mode
        if ipc_mode:
            params["ipcMode"] = ipc_mode
        if proxy_configuration:
            params["proxyConfiguration"] = proxy_configuration
        if inference_accelerators:
            params["inferenceAccelerators"] = inference_accelerators
        if ephemeral_storage:
            params["ephemeralStorage"] = ephemeral_storage
        if runtime_platform:
            params["runtimePlatform"] = runtime_platform

        return self.aws_client.call_api("register_task_definition", **params)

    def deregister_task_definition(self, task_definition: str) -> Dict[str, Any]:
        """Deregister a task definition."""
        return self.aws_client.call_api("deregister_task_definition", taskDefinition=task_definition)

    def list_task_definitions(
        self,
        family_prefix: Optional[str] = None,
        status: Optional[str] = None,
        sort: Optional[str] = None,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """List task definitions."""
        params: Dict[str, Any] = {}

        if family_prefix:
            params["familyPrefix"] = family_prefix
        if status:
            params["status"] = status
        if sort:
            params["sort"] = sort
        if next_token:
            params["nextToken"] = next_token
        if max_results:
            params["maxResults"] = max_results

        return self.aws_client.call_api("list_task_definitions", **params)

    def describe_clusters(self, clusters: Optional[List[str]] = None, include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Describe ECS clusters."""
        params: Dict[str, Any] = {}
        if clusters:
            params["clusters"] = clusters
        if include:
            params["include"] = include

        return self.aws_client.call_api("describe_clusters", **params)

    def create_cluster(
        self,
        cluster_name: str,
        tags: Optional[List[Dict[str, str]]] = None,
        settings: Optional[List[Dict[str, str]]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        capacity_providers: Optional[List[str]] = None,
        default_capacity_provider_strategy: Optional[List[Dict[str, Any]]] = None,
        service_connect_defaults: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create an ECS cluster."""
        params: Dict[str, Any] = {"clusterName": cluster_name}

        if tags:
            params["tags"] = tags
        if settings:
            params["settings"] = settings
        if configuration:
            params["configuration"] = configuration
        if capacity_providers:
            params["capacityProviders"] = capacity_providers
        if default_capacity_provider_strategy:
            params["defaultCapacityProviderStrategy"] = default_capacity_provider_strategy
        if service_connect_defaults:
            params["serviceConnectDefaults"] = service_connect_defaults

        return self.aws_client.call_api("create_cluster", **params)

    def delete_cluster(self, cluster: str) -> Dict[str, Any]:
        """Delete an ECS cluster."""
        return self.aws_client.call_api("delete_cluster", cluster=cluster)

    def tag_resource(self, resource_arn: str, tags: List[Dict[str, str]]) -> Dict[str, Any]:
        """Tag an ECS resource."""
        return self.aws_client.call_api("tag_resource", resourceArn=resource_arn, tags=tags)

    def untag_resource(self, resource_arn: str, tag_keys: List[str]) -> Dict[str, Any]:
        """Remove tags from an ECS resource."""
        return self.aws_client.call_api("untag_resource", resourceArn=resource_arn, tagKeys=tag_keys)

    def list_tags_for_resource(self, resource_arn: str) -> Dict[str, Any]:
        """List tags for an ECS resource."""
        return self.aws_client.call_api("list_tags_for_resource", resourceArn=resource_arn)


class ECSExecutor:
    """High-level ECS execution manager."""

    def __init__(self, client: ECSClient):
        """Initialize ECS executor."""
        self.client = client

    def execute_operation(
        self,
        task_definition_arn: str,
        cluster_name: str,
        input_data: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, str]] = None,
        network_configuration: Optional[Dict[str, Any]] = None,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        Execute an ECS operation with proper error handling and monitoring.
        
        Args:
            task_definition_arn: ECS task definition ARN
            cluster_name: ECS cluster name
            input_data: Input data for the task
            parameters: Operation parameters
            environment: Environment variables
            network_configuration: Network configuration for FARGATE
            timeout: Task timeout in seconds
            
        Returns:
            Execution result
        """
        try:
            # Prepare container overrides
            container_overrides = []
            
            # Get task definition to find container name
            task_def_response = self.client.describe_task_definition(task_definition_arn)
            task_definition = task_def_response["taskDefinition"]
            
            for container_def in task_definition["containerDefinitions"]:
                container_name = container_def["name"]
                
                # Prepare environment variables
                env_vars = []
                if environment:
                    for key, value in environment.items():
                        env_vars.append({"name": key, "value": value})
                
                # Add input data as environment variable
                env_vars.append({
                    "name": "BUNSUI_INPUT",
                    "value": json.dumps(input_data)
                })
                
                if parameters:
                    env_vars.append({
                        "name": "BUNSUI_PARAMETERS",
                        "value": json.dumps(parameters)
                    })
                
                container_override = {
                    "name": container_name,
                    "environment": env_vars
                }
                
                container_overrides.append(container_override)
            
            # Prepare task overrides
            overrides = {
                "containerOverrides": container_overrides
            }
            
            # Set network configuration for FARGATE
            if not network_configuration:
                network_configuration = {
                    "awsvpcConfiguration": {
                        "assignPublicIp": "ENABLED",
                        "subnets": parameters.get("subnets", []) if parameters else [],
                        "securityGroups": parameters.get("security_groups", []) if parameters else []
                    }
                }
            
            # Run task
            start_time = datetime.utcnow()
            run_response = self.client.run_task(
                task_definition=task_definition_arn,
                cluster=cluster_name,
                launch_type="FARGATE",
                count=1,
                overrides=overrides,
                network_configuration=network_configuration,
                started_by="bunsui-pipeline"
            )
            
            if run_response.get("failures"):
                return {
                    "status": "error",
                    "error_message": f"Failed to start task: {run_response['failures']}",
                    "error_type": "TaskStartError",
                    "execution_time": 0,
                    "output": {}
                }
            
            task_arn = run_response["tasks"][0]["taskArn"]
            
            # Wait for task completion
            result = self._wait_for_task_completion(
                task_arn, cluster_name, timeout, start_time
            )
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e),
                "error_type": "ExecutionError",
                "execution_time": 0,
                "output": {}
            }

    def _wait_for_task_completion(
        self,
        task_arn: str,
        cluster_name: str,
        timeout: int,
        start_time: datetime
    ) -> Dict[str, Any]:
        """
        Wait for ECS task to complete.
        
        Args:
            task_arn: Task ARN
            cluster_name: Cluster name
            timeout: Timeout in seconds
            start_time: Task start time
            
        Returns:
            Task execution result
        """
        check_interval = 10  # Check every 10 seconds
        
        while True:
            current_time = datetime.utcnow()
            elapsed_time = (current_time - start_time).total_seconds()
            
            if elapsed_time > timeout:
                # Stop task due to timeout
                self.client.stop_task(
                    task=task_arn,
                    cluster=cluster_name,
                    reason="Timeout exceeded"
                )
                return {
                    "status": "error",
                    "error_message": "Task execution timeout",
                    "error_type": "TimeoutError",
                    "execution_time": elapsed_time,
                    "output": {}
                }
            
            # Describe task
            task_response = self.client.describe_tasks([task_arn], cluster_name)
            
            if not task_response.get("tasks"):
                return {
                    "status": "error",
                    "error_message": "Task not found",
                    "error_type": "TaskNotFound",
                    "execution_time": elapsed_time,
                    "output": {}
                }
            
            task = task_response["tasks"][0]
            last_status = task["lastStatus"]
            
            if last_status == "STOPPED":
                # Task completed
                stop_code = task.get("stopCode", "Unknown")
                containers = task.get("containers", [])
                
                # Check container exit codes
                all_success = True
                container_results = []
                
                for container in containers:
                    exit_code = container.get("exitCode")
                    if exit_code != 0:
                        all_success = False
                    
                    container_results.append({
                        "name": container["name"],
                        "exitCode": exit_code,
                        "reason": container.get("reason", "")
                    })
                
                result = {
                    "status": "success" if all_success and stop_code == "TaskCompletedNormally" else "error",
                    "execution_time": elapsed_time,
                    "stop_code": stop_code,
                    "containers": container_results,
                    "output": {
                        "task_arn": task_arn,
                        "stopped_reason": task.get("stoppedReason", ""),
                        "cpu_utilized": self._extract_cpu_memory_stats(task),
                        "memory_utilized": self._extract_cpu_memory_stats(task, metric="memory")
                    }
                }
                
                if not all_success:
                    result["error_message"] = f"Task failed with stop code: {stop_code}"
                    result["error_type"] = "TaskFailed"
                
                return result
            
            elif last_status in ["RUNNING", "PENDING"]:
                # Task still running, continue waiting
                time.sleep(check_interval)
                continue
            
            else:
                # Unexpected status
                return {
                    "status": "error",
                    "error_message": f"Unexpected task status: {last_status}",
                    "error_type": "UnexpectedStatus",
                    "execution_time": elapsed_time,
                    "output": {}
                }

    def _extract_cpu_memory_stats(self, task: Dict[str, Any], metric: str = "cpu") -> Optional[float]:
        """
        Extract CPU or memory usage statistics from task.
        
        Args:
            task: Task description
            metric: "cpu" or "memory"
            
        Returns:
            Usage statistic or None
        """
        # Note: This is a simplified implementation
        # In practice, you would need CloudWatch integration
        # to get detailed CPU/memory metrics
        
        containers = task.get("containers", [])
        for container in containers:
            # This would typically require CloudWatch metrics
            # For now, return None as a placeholder
            pass
        
        return None

    def get_task_logs(
        self,
        task_arn: str,
        cluster_name: str,
        container_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get logs for an ECS task.
        
        Args:
            task_arn: Task ARN
            cluster_name: Cluster name
            container_name: Specific container name (optional)
            
        Returns:
            Task logs
        """
        try:
            # Get task details
            task_response = self.client.describe_tasks([task_arn], cluster_name)
            
            if not task_response.get("tasks"):
                return {"error": "Task not found", "logs": []}
            
            task = task_response["tasks"][0]
            containers = task.get("containers", [])
            
            logs = []
            for container in containers:
                if container_name and container["name"] != container_name:
                    continue
                
                # Note: To get actual logs, you would need CloudWatch Logs integration
                # This is a placeholder implementation
                logs.append({
                    "container": container["name"],
                    "logs": "CloudWatch Logs integration needed for actual log retrieval",
                    "status": container.get("lastStatus", "Unknown")
                })
            
            return {"logs": logs, "task_arn": task_arn}
            
        except Exception as e:
            return {"error": str(e), "logs": []} 