"""
DynamoDB client implementation for bunsui.

This module provides a high-level interface for DynamoDB operations,
integrating with the AWS client wrapper and schema definitions.
"""

from typing import Dict, Any, List, Optional
import time

from bunsui.aws.client import AWSClient
from bunsui.aws.dynamodb.schemas import TableName, get_table_schema
from bunsui.core.exceptions import ValidationError


class DynamoDBClient:
    """High-level DynamoDB client for bunsui operations."""

    def __init__(self, region: str = "us-east-1", table_prefix: str = "bunsui"):
        """Initialize DynamoDB client."""
        self.aws_client = AWSClient("dynamodb", region)
        self.region = region
        self.table_prefix = table_prefix

    def create_table(self, table_name: TableName) -> Dict[str, Any]:
        """Create a DynamoDB table based on schema definition."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        create_params = {
            "TableName": schema.table_name,
            "AttributeDefinitions": [
                {
                    "AttributeName": attr.attribute_name,
                    "AttributeType": attr.attribute_type,
                }
                for attr in schema.attribute_definitions
            ],
            "KeySchema": [
                {"AttributeName": key.attribute_name, "KeyType": key.key_type}
                for key in schema.key_schema
            ],
            "BillingMode": schema.billing_mode,
        }

        if schema.global_secondary_indexes:
            create_params["GlobalSecondaryIndexes"] = [
                {
                    "IndexName": gsi.index_name,
                    "KeySchema": [
                        {"AttributeName": key.attribute_name, "KeyType": key.key_type}
                        for key in gsi.key_schema
                    ],
                    "Projection": gsi.projection,
                }
                for gsi in schema.global_secondary_indexes
            ]

        if schema.stream_specification:
            create_params["StreamSpecification"] = schema.stream_specification

        if schema.tags:
            create_params["Tags"] = [
                {"Key": k, "Value": v} for k, v in schema.tags.items()
            ]

        return self.aws_client.call_api("create_table", **create_params)

    def delete_table(self, table_name: TableName) -> Dict[str, Any]:
        """Delete a DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        return self.aws_client.call_api("delete_table", TableName=schema.table_name)

    def describe_table(self, table_name: TableName) -> Dict[str, Any]:
        """Describe a DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        return self.aws_client.call_api("describe_table", TableName=schema.table_name)

    def put_item(self, table_name: TableName, item: Dict[str, Any]) -> Dict[str, Any]:
        """Put an item into DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        return self.aws_client.call_api(
            "put_item", TableName=schema.table_name, Item=item
        )

    def get_item(
        self, table_name: TableName, key: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get an item from DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        response = self.aws_client.call_api(
            "get_item", TableName=schema.table_name, Key=key
        )
        return response.get("Item")

    def update_item(
        self,
        table_name: TableName,
        key: Dict[str, Any],
        update_expression: str,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update an item in DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        params = {
            "TableName": schema.table_name,
            "Key": key,
            "UpdateExpression": update_expression,
        }

        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names
        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values

        return self.aws_client.call_api("update_item", **params)

    def delete_item(self, table_name: TableName, key: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an item from DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        return self.aws_client.call_api(
            "delete_item", TableName=schema.table_name, Key=key
        )

    def query(
        self,
        table_name: TableName,
        key_condition_expression: str,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        index_name: Optional[str] = None,
        filter_expression: Optional[str] = None,
        limit: Optional[int] = None,
        scan_index_forward: bool = True,
    ) -> Dict[str, Any]:
        """Query items from DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        params: Dict[str, Any] = {
            "TableName": schema.table_name,
            "KeyConditionExpression": key_condition_expression,
            "ScanIndexForward": scan_index_forward,
        }

        if index_name:
            params["IndexName"] = index_name
        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names
        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values
        if filter_expression:
            params["FilterExpression"] = filter_expression
        if limit:
            params["Limit"] = limit

        return self.aws_client.call_api("query", **params)

    def scan(
        self,
        table_name: TableName,
        filter_expression: Optional[str] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scan items from DynamoDB table."""
        schema = get_table_schema(table_name, self.table_prefix)
        if not schema:
            raise ValidationError(f"Unknown table: {table_name}")

        params: Dict[str, Any] = {"TableName": schema.table_name}

        if filter_expression:
            params["FilterExpression"] = filter_expression
        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names
        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values
        if limit:
            params["Limit"] = limit

        return self.aws_client.call_api("scan", **params)

    def batch_write_items(
        self, requests: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Batch write items to multiple tables."""
        return self.aws_client.call_api("batch_write_item", RequestItems=requests)

    def batch_get_items(self, requests: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Batch get items from multiple tables."""
        return self.aws_client.call_api("batch_get_item", RequestItems=requests)

    def list_tables(
        self, exclusive_start_table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """List DynamoDB tables."""
        params = {}
        if exclusive_start_table_name:
            params["ExclusiveStartTableName"] = exclusive_start_table_name

        return self.aws_client.call_api("list_tables", **params)

    def get_table_status(self, table_name: TableName) -> Optional[str]:
        """Get table status."""
        try:
            response = self.describe_table(table_name)
            return response["Table"]["TableStatus"]
        except Exception:
            return None

    def wait_for_table_active(self, table_name: TableName, timeout: int = 300) -> bool:
        """Wait for table to become active."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_table_status(table_name)
            if status == "ACTIVE":
                return True
            elif status == "CREATING":
                time.sleep(5)
            else:
                return False

        return False

    def table_exists(self, table_name: TableName) -> bool:
        """Check if table exists."""
        return self.get_table_status(table_name) is not None
