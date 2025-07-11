from src.bunsui.dsl.parser import DSLParser, DSLParseError
import pytest

def test_parse_valid_pipeline():
    dsl = '''
version: "1.0"
name: "test-pipeline"
jobs:
  - id: job1
    type: lambda
    parameters:
      function_name: "func"
'''
    parser = DSLParser()
    pipeline = parser.parse_content(dsl)
    assert pipeline.name == "test-pipeline"
    assert len(pipeline.jobs) == 1
    assert pipeline.jobs[0].id == "job1"

def test_parse_invalid_pipeline():
    dsl = 'name: "no-version"'
    parser = DSLParser()
    with pytest.raises(DSLParseError):
        parser.parse_content(dsl) 