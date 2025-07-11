import subprocess
import pytest

def test_cli_pipeline_list():
    result = subprocess.run(["bunsui", "pipeline", "list", "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "pipelines" in result.stdout 