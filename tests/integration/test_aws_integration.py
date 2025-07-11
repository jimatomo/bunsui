import boto3
import pytest
import os

@pytest.fixture(scope="module")
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name="ap-northeast-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )

def test_s3_bucket_create_and_list(s3_client):
    bucket = "bunsui-integration-test"
    s3_client.create_bucket(Bucket=bucket)
    buckets = s3_client.list_buckets()["Buckets"]
    assert any(b["Name"] == bucket for b in buckets) 