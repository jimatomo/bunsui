import pytest

@pytest.fixture(scope="session")
def test_config():
    return {
        "aws_region": "ap-northeast-1",
        "test_bucket": "bunsui-test-bucket"
    } 