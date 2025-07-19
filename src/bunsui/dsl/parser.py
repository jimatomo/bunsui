"""
Pipeline definition DSL parser for Bunsui.
"""

import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


class JobType(Enum):
    """Job type enumeration."""
    LAMBDA = "lambda"
    ECS = "ecs"
    STEP_FUNCTION = "step_function"
    GLUE = "glue"
    EMR = "emr"
    CUSTOM = "custom"


class ParameterType(Enum):
    """Parameter type enumeration."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class Parameter:
    """Parameter definition."""
    name: str
    type: ParameterType
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None


@dataclass
class Job:
    """Job definition."""
    id: str
    name: str
    type: JobType
    parameters: Dict[str, Any]
    depends_on: List[str]
    timeout: Optional[int] = None
    retries: int = 0
    retry_delay: int = 60
    condition: Optional[str] = None


@dataclass
class Pipeline:
    """Pipeline definition."""
    version: str
    name: str
    parameters: List[Parameter]
    jobs: List[Job]
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DSLParser:
    """パイプライン定義DSLのパーサー"""
    
    def __init__(self):
        self.supported_versions = ["1.0"]
        self.variable_pattern = re.compile(r'\$\{([^}]+)\}')
    
    def parse_file(self, file_path: str) -> Pipeline:
        """ファイルからパイプライン定義を解析"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self.parse_content(content)
        except Exception as e:
            raise DSLParseError(f"Failed to parse file {file_path}: {e}")
    
    def parse_content(self, content: str) -> Pipeline:
        """コンテンツからパイプライン定義を解析"""
        try:
            # YAMLとして解析
            data = yaml.safe_load(content)
            
            if not isinstance(data, dict):
                raise DSLParseError("Invalid DSL format: root must be an object")
            
            return self._parse_pipeline(data)
        except yaml.YAMLError as e:
            raise DSLParseError(f"YAML parsing error: {e}")
        except Exception as e:
            raise DSLParseError(f"DSL parsing error: {e}")
    
    def _parse_pipeline(self, data: Dict[str, Any]) -> Pipeline:
        """パイプライン定義を解析"""
        # バージョンチェック
        version = data.get('version')
        if not version:
            raise DSLParseError("Missing required field: version")
        
        if version not in self.supported_versions:
            raise DSLParseError(f"Unsupported version: {version}")
        
        # 基本フィールド
        name = data.get('name')
        if not name:
            raise DSLParseError("Missing required field: name")
        
        description = data.get('description')
        
        # パラメータを解析
        parameters = self._parse_parameters(data.get('parameters', []))
        
        # ジョブを解析
        jobs = self._parse_jobs(data.get('jobs', []))
        
        # メタデータ
        metadata = data.get('metadata', {})
        
        return Pipeline(
            version=version,
            name=name,
            description=description,
            parameters=parameters,
            jobs=jobs,
            metadata=metadata,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    def _parse_parameters(self, params_data: List[Dict[str, Any]]) -> List[Parameter]:
        """パラメータを解析"""
        parameters = []
        
        for param_data in params_data:
            if not isinstance(param_data, dict):
                continue
            
            name = param_data.get('name')
            if not name:
                continue
            
            type_str = param_data.get('type', 'string')
            try:
                param_type = ParameterType(type_str)
            except ValueError:
                raise DSLParseError(f"Invalid parameter type: {type_str}")
            
            parameter = Parameter(
                name=name,
                type=param_type,
                required=param_data.get('required', False),
                default=param_data.get('default'),
                description=param_data.get('description'),
                validation=param_data.get('validation')
            )
            
            parameters.append(parameter)
        
        return parameters
    
    def _parse_jobs(self, jobs_data: List[Dict[str, Any]]) -> List[Job]:
        """ジョブを解析"""
        jobs = []
        
        for job_data in jobs_data:
            if not isinstance(job_data, dict):
                continue
            
            job_id = job_data.get('id')
            if not job_id:
                continue
            
            name = job_data.get('name', job_id)
            
            type_str = job_data.get('type')
            if not type_str:
                raise DSLParseError(f"Missing job type for job: {job_id}")
            
            try:
                job_type = JobType(type_str)
            except ValueError:
                raise DSLParseError(f"Invalid job type: {type_str}")
            
            parameters = job_data.get('parameters', {})
            depends_on = job_data.get('depends_on', [])
            
            if not isinstance(depends_on, list):
                depends_on = [depends_on] if depends_on else []
            
            job = Job(
                id=job_id,
                name=name,
                type=job_type,
                parameters=parameters,
                depends_on=depends_on,
                timeout=job_data.get('timeout'),
                retries=job_data.get('retries', 0),
                retry_delay=job_data.get('retry_delay', 60),
                condition=job_data.get('condition')
            )
            
            jobs.append(job)
        
        return jobs
    
    def expand_variables(self, pipeline: Pipeline, context: Dict[str, Any]) -> Pipeline:
        """変数を展開"""
        # パラメータの値をコンテキストに追加
        for param in pipeline.parameters:
            if param.name in context:
                continue
            if param.default is not None:
                context[param.name] = param.default
        
        # ジョブのパラメータで変数を展開
        for job in pipeline.jobs:
            job.parameters = self._expand_dict_variables(job.parameters, context)
        
        return pipeline
    
    def _expand_dict_variables(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """辞書内の変数を展開"""
        if not isinstance(data, dict):
            return data
        
        expanded = {}
        for key, value in data.items():
            if isinstance(value, str):
                expanded[key] = self._expand_string_variables(value, context)
            elif isinstance(value, dict):
                expanded[key] = self._expand_dict_variables(value, context)
            elif isinstance(value, list):
                expanded[key] = [
                    self._expand_dict_variables(item, context) if isinstance(item, dict)
                    else self._expand_string_variables(item, context) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                expanded[key] = value
        
        return expanded
    
    def _expand_string_variables(self, text: str, context: Dict[str, Any]) -> str:
        """文字列内の変数を展開"""
        if not isinstance(text, str):
            return text
        
        def replace_variable(match):
            var_name = match.group(1)
            if var_name in context:
                return str(context[var_name])
            else:
                return match.group(0)  # 変数が見つからない場合はそのまま
        
        return self.variable_pattern.sub(replace_variable, text)
    
    def validate_pipeline(self, pipeline: Pipeline) -> List[str]:
        """パイプラインを検証"""
        errors = []
        
        # 基本検証
        if not pipeline.name:
            errors.append("Pipeline name is required")
        
        if not pipeline.jobs:
            errors.append("At least one job is required")
        
        # ジョブIDの重複チェック
        job_ids = [job.id for job in pipeline.jobs]
        if len(job_ids) != len(set(job_ids)):
            errors.append("Duplicate job IDs found")
        
        # 依存関係の検証
        for job in pipeline.jobs:
            for dep_id in job.depends_on:
                if dep_id not in job_ids:
                    errors.append(f"Job '{job.id}' depends on non-existent job '{dep_id}'")
        
        # 循環依存の検証
        if self._has_circular_dependencies(pipeline.jobs):
            errors.append("Circular dependencies detected")
        
        # パラメータの検証
        for param in pipeline.parameters:
            if param.validation:
                errors.extend(self._validate_parameter(param))
        
        return errors
    
    def _has_circular_dependencies(self, jobs: List[Job]) -> bool:
        """循環依存をチェック"""
        # 簡易的な循環依存チェック
        # より詳細な実装では、トポロジカルソートを使用
        for job in jobs:
            visited = set()
            if self._has_cycle(job.id, jobs, visited, set()):
                return True
        return False
    
    def _has_cycle(self, job_id: str, jobs: List[Job], visited: set, rec_stack: set) -> bool:
        """特定のジョブから循環をチェック"""
        if job_id in rec_stack:
            return True
        
        if job_id in visited:
            return False
        
        visited.add(job_id)
        rec_stack.add(job_id)
        
        # ジョブを検索
        job = next((j for j in jobs if j.id == job_id), None)
        if job:
            for dep_id in job.depends_on:
                if self._has_cycle(dep_id, jobs, visited, rec_stack):
                    return True
        
        rec_stack.remove(job_id)
        return False
    
    def _validate_parameter(self, param: Parameter) -> List[str]:
        """パラメータを検証"""
        errors = []
        
        if param.validation:
            validation = param.validation
            
            # 最小値・最大値チェック
            if 'min' in validation and param.default is not None:
                if param.type == ParameterType.INTEGER:
                    if param.default < validation['min']:
                        errors.append(f"Parameter '{param.name}' default value is less than minimum")
                elif param.type == ParameterType.STRING:
                    if len(str(param.default)) < validation['min']:
                        errors.append(f"Parameter '{param.name}' default value length is less than minimum")
            
            if 'max' in validation and param.default is not None:
                if param.type == ParameterType.INTEGER:
                    if param.default > validation['max']:
                        errors.append(f"Parameter '{param.name}' default value is greater than maximum")
                elif param.type == ParameterType.STRING:
                    if len(str(param.default)) > validation['max']:
                        errors.append(f"Parameter '{param.name}' default value length is greater than maximum")
            
            # パターンチェック
            if 'pattern' in validation and param.default is not None:
                if not re.match(validation['pattern'], str(param.default)):
                    errors.append(f"Parameter '{param.name}' default value does not match pattern")
        
        return errors


class DSLParseError(Exception):
    """DSL解析エラー"""
    pass 