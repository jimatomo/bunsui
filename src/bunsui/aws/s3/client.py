"""
S3 client implementation for bunsui.

This module provides a high-level interface for S3 operations,
integrating with the AWS client wrapper for log storage, report storage,
and configuration file management.
"""

from typing import Dict, Any, List, Optional, BinaryIO, Union
from datetime import datetime
import json
from pathlib import Path

from bunsui.aws.client import AWSClient
from bunsui.core.exceptions import ValidationError


class S3Client:
    """High-level S3 client for bunsui operations."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize S3 client."""
        self.aws_client = AWSClient("s3", region)
        self.region = region

    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> Dict[str, Any]:
        """Create an S3 bucket."""
        params: Dict[str, Any] = {"Bucket": bucket_name}
        
        # リージョンの決定
        target_region = region or self.region
        
        # us-east-1以外のリージョンの場合はLocationConstraintを設定
        if target_region != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": target_region}

        return self.aws_client.call_api("create_bucket", **params)

    def delete_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Delete an S3 bucket."""
        return self.aws_client.call_api("delete_bucket", Bucket=bucket_name)

    def list_buckets(self) -> Dict[str, Any]:
        """List S3 buckets."""
        return self.aws_client.call_api("list_buckets")

    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists."""
        try:
            self.aws_client.call_api("head_bucket", Bucket=bucket_name)
            return True
        except Exception:
            return False

    def put_object(
        self,
        bucket_name: str,
        key: str,
        data: Union[str, bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Put an object into S3 bucket."""
        params: Dict[str, Any] = {"Bucket": bucket_name, "Key": key}

        if isinstance(data, str):
            params["Body"] = data.encode("utf-8")
        elif isinstance(data, bytes):
            params["Body"] = data
        elif hasattr(data, "read"):
            params["Body"] = data
        else:
            raise ValidationError(f"Unsupported data type: {type(data)}")

        if content_type:
            params["ContentType"] = content_type
        if metadata:
            params["Metadata"] = metadata

        return self.aws_client.call_api("put_object", **params)

    def get_object(self, bucket_name: str, key: str) -> Optional[Dict[str, Any]]:
        """Get an object from S3 bucket."""
        try:
            return self.aws_client.call_api("get_object", Bucket=bucket_name, Key=key)
        except Exception:
            return None

    def delete_object(self, bucket_name: str, key: str) -> Dict[str, Any]:
        """Delete an object from S3 bucket."""
        return self.aws_client.call_api("delete_object", Bucket=bucket_name, Key=key)

    def list_objects(
        self,
        bucket_name: str,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        max_keys: Optional[int] = None
    ) -> Dict[str, Any]:
        """List objects in S3 bucket."""
        params: Dict[str, Any] = {"Bucket": bucket_name}
        if prefix:
            params["Prefix"] = prefix
        if delimiter:
            params["Delimiter"] = delimiter
        if max_keys:
            params["MaxKeys"] = max_keys

        return self.aws_client.call_api("list_objects_v2", **params)

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str
    ) -> Dict[str, Any]:
        """Copy an object within S3."""
        copy_source = {"Bucket": source_bucket, "Key": source_key}
        return self.aws_client.call_api(
            "copy_object",
            CopySource=copy_source,
            Bucket=destination_bucket,
            Key=destination_key
        )

    def generate_presigned_url(
        self,
        bucket_name: str,
        key: str,
        expiration: int = 3600,
        operation: str = "get_object"
    ) -> str:
        """Generate a presigned URL for S3 object."""
        return self.aws_client.call_api(
            "generate_presigned_url",
            ClientMethod=operation,
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=expiration
        )

    def upload_file(
        self,
        file_path: Union[str, Path],
        bucket_name: str,
        key: str,
        extra_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload a file to S3."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            return self.put_object(bucket_name, key, f)

    def download_file(
        self,
        bucket_name: str,
        key: str,
        file_path: Union[str, Path]
    ) -> bool:
        """Download a file from S3."""
        response = self.get_object(bucket_name, key)
        if not response:
            return False

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(response["Body"].read())
        return True


class S3StorageManager:
    """S3 storage manager for bunsui data organization."""

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        """Initialize S3 storage manager."""
        self.client = S3Client(region)
        self.bucket_name = bucket_name
        self.region = region

    def _get_log_path(self, session_id: str, job_id: str, operation_id: str) -> str:
        """Generate log file path."""
        now = datetime.utcnow()
        return f"logs/{now.year}/{now.month:02d}/{now.day:02d}/{session_id}/{job_id}/{operation_id}.jsonl"

    def _get_report_path(self, session_id: str) -> str:
        """Generate report file path."""
        now = datetime.utcnow()
        return f"reports/{now.year}/{now.month:02d}/{now.day:02d}/{session_id}.html"

    def _get_config_path(self, pipeline_id: str, version: str) -> str:
        """Generate config file path."""
        return f"configs/pipelines/{pipeline_id}/{version}.json"

    def store_log_entry(
        self,
        session_id: str,
        job_id: str,
        operation_id: str,
        log_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store a log entry in S3."""
        log_path = self._get_log_path(session_id, job_id, operation_id)
        log_line = json.dumps(log_entry) + "\n"

        return self.client.put_object(
            self.bucket_name,
            log_path,
            log_line,
            content_type="application/json"
        )

    def store_report(
        self,
        session_id: str,
        report_content: str,
        content_type: str = "text/html"
    ) -> Dict[str, Any]:
        """Store a report in S3."""
        report_path = self._get_report_path(session_id)

        return self.client.put_object(
            self.bucket_name,
            report_path,
            report_content,
            content_type=content_type
        )

    def store_pipeline_config(
        self,
        pipeline_id: str,
        version: str,
        config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store pipeline configuration in S3."""
        config_path = self._get_config_path(pipeline_id, version)
        config_json = json.dumps(config_data, indent=2)

        return self.client.put_object(
            self.bucket_name,
            config_path,
            config_json,
            content_type="application/json"
        )

    def get_pipeline_config(
        self,
        pipeline_id: str,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """Get pipeline configuration from S3."""
        config_path = self._get_config_path(pipeline_id, version)
        response = self.client.get_object(self.bucket_name, config_path)

        if not response:
            return None

        config_content = response["Body"].read().decode("utf-8")
        return json.loads(config_content)

    def list_session_logs(
        self,
        session_id: str,
        job_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List log files for a session."""
        prefix = f"logs/*/*/*/{session_id}/"
        if job_id:
            prefix += f"{job_id}/"

        response = self.client.list_objects(self.bucket_name, prefix=prefix)
        return response.get("Contents", [])

    def list_session_reports(self, session_id: str) -> List[Dict[str, Any]]:
        """List report files for a session."""
        prefix = f"reports/*/*/*/{session_id}.html"
        response = self.client.list_objects(self.bucket_name, prefix=prefix)
        return response.get("Contents", [])

    def list_pipeline_configs(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """List configuration files for a pipeline."""
        prefix = f"configs/pipelines/{pipeline_id}/"
        response = self.client.list_objects(self.bucket_name, prefix=prefix)
        return response.get("Contents", [])

    def delete_session_data(self, session_id: str) -> List[Dict[str, Any]]:
        """Delete all data for a session."""
        deleted_objects = []

        # Delete logs
        log_objects = self.list_session_logs(session_id)
        for obj in log_objects:
            self.client.delete_object(self.bucket_name, obj["Key"])
            deleted_objects.append(obj)

        # Delete reports
        report_objects = self.list_session_reports(session_id)
        for obj in report_objects:
            self.client.delete_object(self.bucket_name, obj["Key"])
            deleted_objects.append(obj)

        return deleted_objects

    def get_log_url(self, session_id: str, job_id: str, operation_id: str, expiration: int = 3600) -> str:
        """Generate presigned URL for log file."""
        log_path = self._get_log_path(session_id, job_id, operation_id)
        return self.client.generate_presigned_url(
            self.bucket_name,
            log_path,
            expiration=expiration
        )

    def get_report_url(self, session_id: str, expiration: int = 3600) -> str:
        """Generate presigned URL for report file."""
        report_path = self._get_report_path(session_id)
        return self.client.generate_presigned_url(
            self.bucket_name,
            report_path,
            expiration=expiration
        )
