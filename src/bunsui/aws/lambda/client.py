"""
Lambda client implementation for bunsui.

This module provides a high-level interface for Lambda operations,
integrating with the AWS client wrapper for function execution management.
"""

import json
import base64
from typing import Dict, Any, Optional, Union
from datetime import datetime

from bunsui.aws.client import AWSClient
from bunsui.core.exceptions import ValidationError


class LambdaClient:
    """High-level Lambda client for bunsui operations."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize Lambda client."""
        self.aws_client = AWSClient("lambda", region)
        self.region = region

    def invoke_function(
        self,
        function_name: str,
        payload: Optional[Union[str, Dict[str, Any]]] = None,
        invocation_type: str = "RequestResponse",
        log_type: str = "None",
        client_context: Optional[str] = None,
        qualifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Invoke a Lambda function.
        
        Args:
            function_name: Function name or ARN
            payload: Function payload
            invocation_type: RequestResponse, Event, or DryRun
            log_type: None or Tail
            client_context: Client context (base64 encoded)
            qualifier: Function version or alias
            
        Returns:
            Invocation response
        """
        params: Dict[str, Any] = {
            "FunctionName": function_name,
            "InvocationType": invocation_type,
            "LogType": log_type
        }

        if payload is not None:
            if isinstance(payload, dict):
                params["Payload"] = json.dumps(payload)
            else:
                params["Payload"] = payload

        if client_context:
            params["ClientContext"] = client_context

        if qualifier:
            params["Qualifier"] = qualifier

        response = self.aws_client.call_api("invoke", **params)
        
        # Process response
        result = {
            "StatusCode": response.get("StatusCode"),
            "ExecutedVersion": response.get("ExecutedVersion"),
            "FunctionError": response.get("FunctionError"),
            "LogResult": response.get("LogResult")
        }

        # Decode payload if present
        if "Payload" in response:
            payload_data = response["Payload"].read()
            try:
                result["Payload"] = json.loads(payload_data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                result["Payload"] = payload_data.decode("utf-8", errors="ignore")

        # Decode logs if present
        if result.get("LogResult"):
            try:
                result["LogResult"] = base64.b64decode(result["LogResult"]).decode("utf-8")
            except Exception:
                pass

        return result

    def invoke_async(
        self,
        function_name: str,
        payload: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a Lambda function asynchronously.
        
        Args:
            function_name: Function name or ARN
            payload: Function payload
            
        Returns:
            Invocation response
        """
        return self.invoke_function(
            function_name=function_name,
            payload=payload,
            invocation_type="Event"
        )

    def get_function(self, function_name: str, qualifier: Optional[str] = None) -> Dict[str, Any]:
        """Get function configuration."""
        params: Dict[str, Any] = {"FunctionName": function_name}
        if qualifier:
            params["Qualifier"] = qualifier

        return self.aws_client.call_api("get_function", **params)

    def list_functions(
        self,
        master_region: Optional[str] = None,
        function_version: str = "ALL",
        marker: Optional[str] = None,
        max_items: Optional[int] = None
    ) -> Dict[str, Any]:
        """List Lambda functions."""
        params: Dict[str, Any] = {"FunctionVersion": function_version}

        if master_region:
            params["MasterRegion"] = master_region
        if marker:
            params["Marker"] = marker
        if max_items:
            params["MaxItems"] = max_items

        return self.aws_client.call_api("list_functions", **params)

    def get_function_configuration(
        self,
        function_name: str,
        qualifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get function configuration only."""
        params: Dict[str, Any] = {"FunctionName": function_name}
        if qualifier:
            params["Qualifier"] = qualifier

        return self.aws_client.call_api("get_function_configuration", **params)

    def update_function_code(
        self,
        function_name: str,
        zip_file: Optional[bytes] = None,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
        s3_object_version: Optional[str] = None,
        image_uri: Optional[str] = None,
        publish: bool = False,
        dry_run: bool = False,
        revision_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update function code."""
        params: Dict[str, Any] = {
            "FunctionName": function_name,
            "Publish": publish,
            "DryRun": dry_run
        }

        if zip_file:
            params["ZipFile"] = zip_file
        elif s3_bucket and s3_key:
            params["S3Bucket"] = s3_bucket
            params["S3Key"] = s3_key
            if s3_object_version:
                params["S3ObjectVersion"] = s3_object_version
        elif image_uri:
            params["ImageUri"] = image_uri
        else:
            raise ValidationError("Must provide either zip_file, S3 location, or image_uri")

        if revision_id:
            params["RevisionId"] = revision_id

        return self.aws_client.call_api("update_function_code", **params)

    def update_function_configuration(
        self,
        function_name: str,
        runtime: Optional[str] = None,
        role: Optional[str] = None,
        handler: Optional[str] = None,
        description: Optional[str] = None,
        timeout: Optional[int] = None,
        memory_size: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        kms_key_arn: Optional[str] = None,
        tracing_config: Optional[Dict[str, str]] = None,
        revision_id: Optional[str] = None,
        layers: Optional[list] = None,
        file_system_configs: Optional[list] = None,
        image_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update function configuration."""
        params: Dict[str, Any] = {"FunctionName": function_name}

        if runtime:
            params["Runtime"] = runtime
        if role:
            params["Role"] = role
        if handler:
            params["Handler"] = handler
        if description:
            params["Description"] = description
        if timeout:
            params["Timeout"] = timeout
        if memory_size:
            params["MemorySize"] = memory_size
        if environment:
            params["Environment"] = {"Variables": environment}
        if kms_key_arn:
            params["KMSKeyArn"] = kms_key_arn
        if tracing_config:
            params["TracingConfig"] = tracing_config
        if revision_id:
            params["RevisionId"] = revision_id
        if layers:
            params["Layers"] = layers
        if file_system_configs:
            params["FileSystemConfigs"] = file_system_configs
        if image_config:
            params["ImageConfig"] = image_config

        return self.aws_client.call_api("update_function_configuration", **params)

    def create_function(
        self,
        function_name: str,
        runtime: str,
        role: str,
        handler: str,
        code: Dict[str, Any],
        description: Optional[str] = None,
        timeout: int = 3,
        memory_size: int = 128,
        publish: bool = False,
        vpc_config: Optional[Dict[str, Any]] = None,
        package_type: str = "Zip",
        dead_letter_config: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None,
        kms_key_arn: Optional[str] = None,
        tracing_config: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
        layers: Optional[list] = None,
        file_system_configs: Optional[list] = None,
        image_config: Optional[Dict[str, Any]] = None,
        code_signing_config_arn: Optional[str] = None,
        architectures: Optional[list] = None
    ) -> Dict[str, Any]:
        """Create a new Lambda function."""
        params: Dict[str, Any] = {
            "FunctionName": function_name,
            "Runtime": runtime,
            "Role": role,
            "Handler": handler,
            "Code": code,
            "Timeout": timeout,
            "MemorySize": memory_size,
            "Publish": publish,
            "PackageType": package_type
        }

        if description:
            params["Description"] = description
        if vpc_config:
            params["VpcConfig"] = vpc_config
        if dead_letter_config:
            params["DeadLetterConfig"] = dead_letter_config
        if environment:
            params["Environment"] = {"Variables": environment}
        if kms_key_arn:
            params["KMSKeyArn"] = kms_key_arn
        if tracing_config:
            params["TracingConfig"] = tracing_config
        if tags:
            params["Tags"] = tags
        if layers:
            params["Layers"] = layers
        if file_system_configs:
            params["FileSystemConfigs"] = file_system_configs
        if image_config:
            params["ImageConfig"] = image_config
        if code_signing_config_arn:
            params["CodeSigningConfigArn"] = code_signing_config_arn
        if architectures:
            params["Architectures"] = architectures

        return self.aws_client.call_api("create_function", **params)

    def delete_function(
        self,
        function_name: str,
        qualifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a Lambda function."""
        params: Dict[str, Any] = {"FunctionName": function_name}
        if qualifier:
            params["Qualifier"] = qualifier

        return self.aws_client.call_api("delete_function", **params)

    def add_permission(
        self,
        function_name: str,
        statement_id: str,
        action: str,
        principal: str,
        source_arn: Optional[str] = None,
        source_account: Optional[str] = None,
        event_source_token: Optional[str] = None,
        qualifier: Optional[str] = None,
        revision_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add permission to a Lambda function."""
        params: Dict[str, Any] = {
            "FunctionName": function_name,
            "StatementId": statement_id,
            "Action": action,
            "Principal": principal
        }

        if source_arn:
            params["SourceArn"] = source_arn
        if source_account:
            params["SourceAccount"] = source_account
        if event_source_token:
            params["EventSourceToken"] = event_source_token
        if qualifier:
            params["Qualifier"] = qualifier
        if revision_id:
            params["RevisionId"] = revision_id

        return self.aws_client.call_api("add_permission", **params)

    def remove_permission(
        self,
        function_name: str,
        statement_id: str,
        qualifier: Optional[str] = None,
        revision_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove permission from a Lambda function."""
        params: Dict[str, Any] = {
            "FunctionName": function_name,
            "StatementId": statement_id
        }

        if qualifier:
            params["Qualifier"] = qualifier
        if revision_id:
            params["RevisionId"] = revision_id

        return self.aws_client.call_api("remove_permission", **params)

    def get_policy(
        self,
        function_name: str,
        qualifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get function policy."""
        params: Dict[str, Any] = {"FunctionName": function_name}
        if qualifier:
            params["Qualifier"] = qualifier

        return self.aws_client.call_api("get_policy", **params)

    def tag_resource(self, resource_arn: str, tags: Dict[str, str]) -> Dict[str, Any]:
        """Tag a Lambda resource."""
        return self.aws_client.call_api("tag_resource", Resource=resource_arn, Tags=tags)

    def untag_resource(self, resource_arn: str, tag_keys: list) -> Dict[str, Any]:
        """Remove tags from a Lambda resource."""
        return self.aws_client.call_api("untag_resource", Resource=resource_arn, TagKeys=tag_keys)

    def list_tags(self, resource_arn: str) -> Dict[str, Any]:
        """List tags for a Lambda resource."""
        return self.aws_client.call_api("list_tags", Resource=resource_arn)


class LambdaExecutor:
    """High-level Lambda execution manager."""

    def __init__(self, client: LambdaClient):
        """Initialize Lambda executor."""
        self.client = client

    def execute_operation(
        self,
        function_arn: str,
        input_data: Dict[str, Any],
        timeout: int = 900,
        parameters: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Lambda operation with proper error handling and logging.
        
        Args:
            function_arn: Lambda function ARN
            input_data: Input data for the function
            timeout: Function timeout in seconds
            parameters: Operation parameters
            environment: Environment variables
            
        Returns:
            Execution result
        """
        try:
            # Prepare payload
            payload = {
                "input": input_data,
                "parameters": parameters or {},
                "environment": environment or {},
                "timestamp": datetime.utcnow().isoformat(),
                "timeout": timeout
            }

            # Invoke function
            start_time = datetime.utcnow()
            response = self.client.invoke_function(
                function_name=function_arn,
                payload=payload,
                log_type="Tail"
            )
            end_time = datetime.utcnow()

            # Process response
            execution_time = (end_time - start_time).total_seconds()
            
            result = {
                "status": "success" if response["StatusCode"] == 200 else "error",
                "execution_time": execution_time,
                "status_code": response["StatusCode"],
                "executed_version": response.get("ExecutedVersion"),
                "function_error": response.get("FunctionError"),
                "output": response.get("Payload", {}),
                "logs": response.get("LogResult", "")
            }

            # Handle function errors
            if response.get("FunctionError"):
                result["status"] = "error"
                result["error_type"] = response["FunctionError"]
                if isinstance(result["output"], dict) and "errorMessage" in result["output"]:
                    result["error_message"] = result["output"]["errorMessage"]

            return result

        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e),
                "error_type": "InvocationError",
                "execution_time": 0,
                "output": {}
            } 