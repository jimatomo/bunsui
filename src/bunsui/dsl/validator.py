"""
Pipeline definition DSL validator for Bunsui.
"""

from typing import List, Dict, Any
from .parser import Pipeline, Job, Parameter, JobType, ParameterType
import re


class DSLValidator:
    """パイプライン定義DSLのバリデーター"""
    
    def __init__(self):
        self.job_type_validators = {
            JobType.LAMBDA: self._validate_lambda_job,
            JobType.ECS: self._validate_ecs_job,
            JobType.STEP_FUNCTION: self._validate_step_function_job,
            JobType.GLUE: self._validate_glue_job,
            JobType.EMR: self._validate_emr_job,
            JobType.CUSTOM: self._validate_custom_job
        }
    
    def validate_pipeline(self, pipeline: Pipeline) -> List[str]:
        """パイプライン全体を検証"""
        errors = []
        
        # 基本検証
        errors.extend(self._validate_basic_structure(pipeline))
        
        # パラメータ検証
        errors.extend(self._validate_parameters(pipeline.parameters))
        
        # ジョブ検証
        errors.extend(self._validate_jobs(pipeline.jobs))
        
        # 依存関係検証
        errors.extend(self._validate_dependencies(pipeline.jobs))
        
        # 循環依存検証
        if self._has_circular_dependencies(pipeline.jobs):
            errors.append("Circular dependencies detected in pipeline")
        
        return errors
    
    def _validate_basic_structure(self, pipeline: Pipeline) -> List[str]:
        """基本構造を検証"""
        errors = []
        
        if not pipeline.name:
            errors.append("Pipeline name is required")
        elif not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', pipeline.name):
            errors.append("Pipeline name must start with a letter and contain only alphanumeric characters, hyphens, and underscores")
        
        if not pipeline.jobs:
            errors.append("At least one job is required")
        
        if pipeline.version not in ["1.0", "1.1"]:
            errors.append(f"Unsupported pipeline version: {pipeline.version}")
        
        return errors
    
    def _validate_parameters(self, parameters: List[Parameter]) -> List[str]:
        """パラメータを検証"""
        errors = []
        param_names = []
        
        for param in parameters:
            # 名前の重複チェック
            if param.name in param_names:
                errors.append(f"Duplicate parameter name: {param.name}")
            else:
                param_names.append(param.name)
            
            # 名前の形式チェック
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', param.name):
                errors.append(f"Invalid parameter name: {param.name}")
            
            # 型固有の検証
            errors.extend(self._validate_parameter_type(param))
            
            # バリデーションルールの検証
            if param.validation:
                errors.extend(self._validate_parameter_validation(param))
        
        return errors
    
    def _validate_parameter_type(self, param: Parameter) -> List[str]:
        """パラメータの型を検証"""
        errors = []
        
        if param.default is not None:
            # デフォルト値の型チェック
            if param.type == ParameterType.STRING:
                if not isinstance(param.default, str):
                    errors.append(f"Parameter '{param.name}' default value must be a string")
            elif param.type == ParameterType.INTEGER:
                if not isinstance(param.default, int):
                    errors.append(f"Parameter '{param.name}' default value must be an integer")
            elif param.type == ParameterType.FLOAT:
                if not isinstance(param.default, (int, float)):
                    errors.append(f"Parameter '{param.name}' default value must be a number")
            elif param.type == ParameterType.BOOLEAN:
                if not isinstance(param.default, bool):
                    errors.append(f"Parameter '{param.name}' default value must be a boolean")
            elif param.type == ParameterType.ARRAY:
                if not isinstance(param.default, list):
                    errors.append(f"Parameter '{param.name}' default value must be an array")
            elif param.type == ParameterType.OBJECT:
                if not isinstance(param.default, dict):
                    errors.append(f"Parameter '{param.name}' default value must be an object")
        
        return errors
    
    def _validate_parameter_validation(self, param: Parameter) -> List[str]:
        """パラメータのバリデーションルールを検証"""
        errors = []
        validation = param.validation
        
        if not isinstance(validation, dict):
            errors.append(f"Parameter '{param.name}' validation must be an object")
            return errors
        
        # 最小値・最大値チェック
        if 'min' in validation:
            if not isinstance(validation['min'], (int, float)):
                errors.append(f"Parameter '{param.name}' min value must be a number")
        
        if 'max' in validation:
            if not isinstance(validation['max'], (int, float)):
                errors.append(f"Parameter '{param.name}' max value must be a number")
        
        if 'min' in validation and 'max' in validation:
            if validation['min'] > validation['max']:
                errors.append(f"Parameter '{param.name}' min value cannot be greater than max value")
        
        # パターンチェック
        if 'pattern' in validation:
            if not isinstance(validation['pattern'], str):
                errors.append(f"Parameter '{param.name}' pattern must be a string")
            else:
                try:
                    re.compile(validation['pattern'])
                except re.error:
                    errors.append(f"Parameter '{param.name}' pattern is not a valid regex")
        
        # 列挙値チェック
        if 'enum' in validation:
            if not isinstance(validation['enum'], list):
                errors.append(f"Parameter '{param.name}' enum must be an array")
        
        return errors
    
    def _validate_jobs(self, jobs: List[Job]) -> List[str]:
        """ジョブを検証"""
        errors = []
        job_ids = []
        
        for job in jobs:
            # IDの重複チェック
            if job.id in job_ids:
                errors.append(f"Duplicate job ID: {job.id}")
            else:
                job_ids.append(job.id)
            
            # IDの形式チェック
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', job.id):
                errors.append(f"Invalid job ID: {job.id}")
            
            # 名前の形式チェック
            if job.name and not re.match(r'^[a-zA-Z][a-zA-Z0-9_\s-]*$', job.name):
                errors.append(f"Invalid job name: {job.name}")
            
            # タイムアウトの検証
            if job.timeout is not None:
                if not isinstance(job.timeout, int) or job.timeout <= 0:
                    errors.append(f"Job '{job.id}' timeout must be a positive integer")
            
            # リトライの検証
            if not isinstance(job.retries, int) or job.retries < 0:
                errors.append(f"Job '{job.id}' retries must be a non-negative integer")
            
            if not isinstance(job.retry_delay, int) or job.retry_delay < 0:
                errors.append(f"Job '{job.id}' retry_delay must be a non-negative integer")
            
            # ジョブタイプ固有の検証
            validator = self.job_type_validators.get(job.type)
            if validator:
                errors.extend(validator(job))
        
        return errors
    
    def _validate_lambda_job(self, job: Job) -> List[str]:
        """Lambdaジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'function_name' not in params:
            errors.append(f"Lambda job '{job.id}' must specify function_name")
        
        if 'payload' in params and not isinstance(params['payload'], dict):
            errors.append(f"Lambda job '{job.id}' payload must be an object")
        
        return errors
    
    def _validate_ecs_job(self, job: Job) -> List[str]:
        """ECSジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'task_definition' not in params:
            errors.append(f"ECS job '{job.id}' must specify task_definition")
        
        if 'cluster' in params and not isinstance(params['cluster'], str):
            errors.append(f"ECS job '{job.id}' cluster must be a string")
        
        return errors
    
    def _validate_step_function_job(self, job: Job) -> List[str]:
        """Step Functionジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'state_machine_arn' not in params:
            errors.append(f"Step Function job '{job.id}' must specify state_machine_arn")
        
        if 'input' in params and not isinstance(params['input'], dict):
            errors.append(f"Step Function job '{job.id}' input must be an object")
        
        return errors
    
    def _validate_glue_job(self, job: Job) -> List[str]:
        """Glueジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'job_name' not in params:
            errors.append(f"Glue job '{job.id}' must specify job_name")
        
        if 'arguments' in params and not isinstance(params['arguments'], dict):
            errors.append(f"Glue job '{job.id}' arguments must be an object")
        
        return errors
    
    def _validate_emr_job(self, job: Job) -> List[str]:
        """EMRジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'cluster_id' not in params:
            errors.append(f"EMR job '{job.id}' must specify cluster_id")
        
        if 'step_config' in params and not isinstance(params['step_config'], dict):
            errors.append(f"EMR job '{job.id}' step_config must be an object")
        
        return errors
    
    def _validate_custom_job(self, job: Job) -> List[str]:
        """カスタムジョブを検証"""
        errors = []
        params = job.parameters
        
        if 'command' not in params:
            errors.append(f"Custom job '{job.id}' must specify command")
        
        if 'environment' in params and not isinstance(params['environment'], dict):
            errors.append(f"Custom job '{job.id}' environment must be an object")
        
        return errors
    
    def _validate_dependencies(self, jobs: List[Job]) -> List[str]:
        """依存関係を検証"""
        errors = []
        job_ids = [job.id for job in jobs]
        
        for job in jobs:
            for dep_id in job.depends_on:
                if dep_id not in job_ids:
                    errors.append(f"Job '{job.id}' depends on non-existent job '{dep_id}'")
        
        return errors
    
    def _has_circular_dependencies(self, jobs: List[Job]) -> bool:
        """循環依存をチェック"""
        # トポロジカルソートを使用して循環依存を検出
        job_map = {job.id: job for job in jobs}
        visited = set()
        rec_stack = set()
        
        def has_cycle(job_id: str) -> bool:
            if job_id in rec_stack:
                return True
            
            if job_id in visited:
                return False
            
            visited.add(job_id)
            rec_stack.add(job_id)
            
            job = job_map.get(job_id)
            if job:
                for dep_id in job.depends_on:
                    if has_cycle(dep_id):
                        return True
            
            rec_stack.remove(job_id)
            return False
        
        for job in jobs:
            if has_cycle(job.id):
                return True
        
        return False
    
    def validate_parameter_values(self, pipeline: Pipeline, values: Dict[str, Any]) -> List[str]:
        """パラメータ値を検証"""
        errors = []
        
        for param in pipeline.parameters:
            if param.name in values:
                value = values[param.name]
                errors.extend(self._validate_parameter_value(param, value))
            elif param.required:
                errors.append(f"Required parameter '{param.name}' is missing")
        
        return errors
    
    def _validate_parameter_value(self, param: Parameter, value: Any) -> List[str]:
        """個別のパラメータ値を検証"""
        errors = []
        
        # 型チェック
        if param.type == ParameterType.STRING and not isinstance(value, str):
            errors.append(f"Parameter '{param.name}' value must be a string")
        elif param.type == ParameterType.INTEGER and not isinstance(value, int):
            errors.append(f"Parameter '{param.name}' value must be an integer")
        elif param.type == ParameterType.FLOAT and not isinstance(value, (int, float)):
            errors.append(f"Parameter '{param.name}' value must be a number")
        elif param.type == ParameterType.BOOLEAN and not isinstance(value, bool):
            errors.append(f"Parameter '{param.name}' value must be a boolean")
        elif param.type == ParameterType.ARRAY and not isinstance(value, list):
            errors.append(f"Parameter '{param.name}' value must be an array")
        elif param.type == ParameterType.OBJECT and not isinstance(value, dict):
            errors.append(f"Parameter '{param.name}' value must be an object")
        
        # バリデーションルールチェック
        if param.validation:
            errors.extend(self._validate_parameter_value_rules(param, value))
        
        return errors
    
    def _validate_parameter_value_rules(self, param: Parameter, value: Any) -> List[str]:
        """パラメータ値のバリデーションルールをチェック"""
        errors = []
        validation = param.validation
        
        # 最小値・最大値チェック
        if param.type == ParameterType.INTEGER or param.type == ParameterType.FLOAT:
            if validation and 'min' in validation and value < validation['min']:
                errors.append(f"Parameter '{param.name}' value {value} is less than minimum {validation['min']}")
            
            if validation and 'max' in validation and value > validation['max']:
                errors.append(f"Parameter '{param.name}' value {value} is greater than maximum {validation['max']}")
        
        elif param.type == ParameterType.STRING:
            if validation and 'min' in validation and len(value) < validation['min']:
                errors.append(f"Parameter '{param.name}' value length {len(value)} is less than minimum {validation['min']}")
            
            if validation and 'max' in validation and len(value) > validation['max']:
                errors.append(f"Parameter '{param.name}' value length {len(value)} is greater than maximum {validation['max']}")
        
        # パターンチェック
        if validation and 'pattern' in validation and param.type == ParameterType.STRING:
            if not re.match(validation['pattern'], value):
                errors.append(f"Parameter '{param.name}' value does not match pattern {validation['pattern']}")
        
        # 列挙値チェック
        if validation and 'enum' in validation:
            if value not in validation['enum']:
                errors.append(f"Parameter '{param.name}' value {value} is not in allowed values {validation['enum']}")
        
        return errors 