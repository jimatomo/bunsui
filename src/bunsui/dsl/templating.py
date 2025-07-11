"""
Pipeline definition DSL templating for Bunsui.
"""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .parser import DSLParser, Pipeline


class DSLTemplateEngine:
    """パイプライン定義DSLのテンプレートエンジン"""
    
    def __init__(self, template_dirs: Optional[List[str]] = None):
        self.template_dirs = template_dirs or []
        self.env = Environment(
            loader=FileSystemLoader(self.template_dirs),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.parser = DSLParser()
    
    def render_template(self, template_content: str, context: Dict[str, Any]) -> str:
        """テンプレートをレンダリング"""
        try:
            template = self.env.from_string(template_content)
            return template.render(**context)
        except Exception as e:
            raise DSLTemplateError(f"Template rendering error: {e}")
    
    def render_template_file(self, template_path: str, context: Dict[str, Any]) -> str:
        """テンプレートファイルをレンダリング"""
        try:
            template = self.env.get_template(template_path)
            return template.render(**context)
        except Exception as e:
            raise DSLTemplateError(f"Template file rendering error: {e}")
    
    def parse_and_render(self, template_content: str, context: Dict[str, Any]) -> Pipeline:
        """テンプレートをレンダリングしてパイプラインを解析"""
        rendered_content = self.render_template(template_content, context)
        return self.parser.parse_content(rendered_content)
    
    def parse_and_render_file(self, template_path: str, context: Dict[str, Any]) -> Pipeline:
        """テンプレートファイルをレンダリングしてパイプラインを解析"""
        rendered_content = self.render_template_file(template_path, context)
        return self.parser.parse_content(rendered_content)


class DSLTemplateManager:
    """パイプライン定義DSLのテンプレートマネージャー"""
    
    def __init__(self, template_base_dir: str = "templates"):
        self.template_base_dir = Path(template_base_dir)
        self.template_engine = DSLTemplateEngine([str(self.template_base_dir)])
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """テンプレートを読み込み"""
        if not self.template_base_dir.exists():
            return
        
        for template_file in self.template_base_dir.rglob("*.yaml"):
            template_name = template_file.stem
            with open(template_file, 'r', encoding='utf-8') as f:
                self.templates[template_name] = f.read()
    
    def get_template(self, template_name: str) -> Optional[str]:
        """テンプレートを取得"""
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[str]:
        """テンプレート一覧を取得"""
        return list(self.templates.keys())
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> Pipeline:
        """テンプレートをレンダリング"""
        template_content = self.get_template(template_name)
        if not template_content:
            raise DSLTemplateError(f"Template '{template_name}' not found")
        
        return self.template_engine.parse_and_render(template_content, context)
    
    def create_template(self, template_name: str, content: str):
        """テンプレートを作成"""
        template_path = self.template_base_dir / f"{template_name}.yaml"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.templates[template_name] = content
    
    def delete_template(self, template_name: str):
        """テンプレートを削除"""
        template_path = self.template_base_dir / f"{template_name}.yaml"
        if template_path.exists():
            template_path.unlink()
        
        self.templates.pop(template_name, None)


class DSLTemplateBuilder:
    """パイプライン定義DSLのテンプレートビルダー"""
    
    def __init__(self):
        self.template_vars = {}
        self.jobs = []
        self.parameters = []
        self.metadata = {}
    
    def set_name(self, name: str) -> 'DSLTemplateBuilder':
        """パイプライン名を設定"""
        self.template_vars['name'] = name
        return self
    
    def set_description(self, description: str) -> 'DSLTemplateBuilder':
        """パイプライン説明を設定"""
        self.template_vars['description'] = description
        return self
    
    def add_parameter(self, name: str, param_type: str = "string", required: bool = False, 
                     default: Any = None, description: Optional[str] = None) -> 'DSLTemplateBuilder':
        """パラメータを追加"""
        param = {
            'name': name,
            'type': param_type,
            'required': required
        }
        
        if default is not None:
            param['default'] = default
        
        if description:
            param['description'] = description
        
        self.parameters.append(param)
        return self
    
    def add_lambda_job(self, job_id: str, function_name: str, payload: Optional[Dict[str, Any]] = None,
                       depends_on: Optional[List[str]] = None, timeout: Optional[int] = None) -> 'DSLTemplateBuilder':
        """Lambdaジョブを追加"""
        job = {
            'id': job_id,
            'type': 'lambda',
            'parameters': {
                'function_name': function_name
            }
        }
        if payload is not None:
            job['parameters']['payload'] = payload
        if depends_on is not None:
            job['depends_on'] = depends_on
        if timeout is not None:
            job['timeout'] = timeout
        self.jobs.append(job)
        return self
    
    def add_ecs_job(self, job_id: str, task_definition: str, cluster: Optional[str] = None,
                    depends_on: Optional[List[str]] = None, timeout: Optional[int] = None) -> 'DSLTemplateBuilder':
        """ECSジョブを追加"""
        job = {
            'id': job_id,
            'type': 'ecs',
            'parameters': {
                'task_definition': task_definition
            }
        }
        if cluster is not None:
            job['parameters']['cluster'] = cluster
        if depends_on is not None:
            job['depends_on'] = depends_on
        if timeout is not None:
            job['timeout'] = timeout
        self.jobs.append(job)
        return self
    
    def add_step_function_job(self, job_id: str, state_machine_arn: str, input: Optional[Dict[str, Any]] = None,
                             depends_on: Optional[List[str]] = None, timeout: Optional[int] = None) -> 'DSLTemplateBuilder':
        """Step Functionジョブを追加"""
        job = {
            'id': job_id,
            'type': 'step_function',
            'parameters': {
                'state_machine_arn': state_machine_arn
            }
        }
        if input is not None:
            job['parameters']['input'] = input
        if depends_on is not None:
            job['depends_on'] = depends_on
        if timeout is not None:
            job['timeout'] = timeout
        self.jobs.append(job)
        return self
    
    def add_glue_job(self, job_id: str, job_name: str, arguments: Optional[Dict[str, Any]] = None,
                     depends_on: Optional[List[str]] = None, timeout: Optional[int] = None) -> 'DSLTemplateBuilder':
        """Glueジョブを追加"""
        job = {
            'id': job_id,
            'type': 'glue',
            'parameters': {
                'job_name': job_name
            }
        }
        if arguments is not None:
            job['parameters']['arguments'] = arguments
        if depends_on is not None:
            job['depends_on'] = depends_on
        if timeout is not None:
            job['timeout'] = timeout
        self.jobs.append(job)
        return self
    
    def add_custom_job(self, job_id: str, command: str, environment: Optional[Dict[str, str]] = None,
                       depends_on: Optional[List[str]] = None, timeout: Optional[int] = None) -> 'DSLTemplateBuilder':
        """カスタムジョブを追加"""
        job = {
            'id': job_id,
            'type': 'custom',
            'parameters': {
                'command': command
            }
        }
        if environment is not None:
            job['parameters']['environment'] = environment
        if depends_on is not None:
            job['depends_on'] = depends_on
        if timeout is not None:
            job['timeout'] = timeout
        self.jobs.append(job)
        return self
    
    def set_metadata(self, key: str, value: Any) -> 'DSLTemplateBuilder':
        """メタデータを設定"""
        self.metadata[key] = value
        return self
    
    def build(self) -> str:
        """テンプレートをビルド"""
        pipeline = {
            'version': '1.0',
            'name': self.template_vars.get('name', 'Generated Pipeline'),
            'jobs': self.jobs
        }
        
        if 'description' in self.template_vars:
            pipeline['description'] = self.template_vars['description']
        
        if self.parameters:
            pipeline['parameters'] = self.parameters
        
        if self.metadata:
            pipeline['metadata'] = self.metadata
        
        return yaml.dump(pipeline, default_flow_style=False, sort_keys=False)
    
    def build_and_parse(self) -> Pipeline:
        """テンプレートをビルドしてパイプラインを解析"""
        content = self.build()
        parser = DSLParser()
        return parser.parse_content(content)


class DSLTemplateExamples:
    """パイプライン定義DSLのテンプレート例"""
    
    @staticmethod
    def etl_pipeline() -> str:
        """ETLパイプラインのテンプレート例"""
        return """
version: "1.0"
name: "ETL Pipeline"
description: "Daily ETL process for data processing"

parameters:
  - name: source_bucket
    type: string
    required: true
    description: "Source S3 bucket name"
  - name: target_table
    type: string
    default: "analytics.daily_summary"
    description: "Target table name"
  - name: processing_date
    type: string
    required: true
    description: "Processing date (YYYY-MM-DD)"

jobs:
  - id: extract_data
    name: "Extract Data"
    type: lambda
    parameters:
      function_name: "extract-function"
      payload:
        bucket: "{{ source_bucket }}"
        date: "{{ processing_date }}"
    
  - id: transform_data
    name: "Transform Data"
    type: glue
    parameters:
      job_name: "transform-job"
      arguments:
        --source_path: "s3://{{ source_bucket }}/raw/{{ processing_date }}"
        --target_path: "s3://{{ source_bucket }}/processed/{{ processing_date }}"
    depends_on: [extract_data]
    
  - id: load_data
    name: "Load Data"
    type: lambda
    parameters:
      function_name: "load-function"
      payload:
        table: "{{ target_table }}"
        data_path: "s3://{{ source_bucket }}/processed/{{ processing_date }}"
    depends_on: [transform_data]

metadata:
  owner: "data-team"
  environment: "production"
  schedule: "daily"
"""
    
    @staticmethod
    def ml_pipeline() -> str:
        """MLパイプラインのテンプレート例"""
        return """
version: "1.0"
name: "ML Training Pipeline"
description: "Machine learning model training pipeline"

parameters:
  - name: model_name
    type: string
    required: true
    description: "Model name"
  - name: training_data_path
    type: string
    required: true
    description: "Training data S3 path"
  - name: hyperparameters
    type: object
    default: {}
    description: "Model hyperparameters"

jobs:
  - id: prepare_data
    name: "Prepare Training Data"
    type: lambda
    parameters:
      function_name: "data-preparation"
      payload:
        data_path: "{{ training_data_path }}"
        output_path: "s3://ml-bucket/prepared/{{ model_name }}"
    
  - id: train_model
    name: "Train Model"
    type: ecs
    parameters:
      task_definition: "ml-training-task"
      cluster: "ml-cluster"
      environment:
        MODEL_NAME: "{{ model_name }}"
        DATA_PATH: "s3://ml-bucket/prepared/{{ model_name }}"
        HYPERPARAMETERS: "{{ hyperparameters | tojson }}"
    depends_on: [prepare_data]
    timeout: 3600
    
  - id: evaluate_model
    name: "Evaluate Model"
    type: lambda
    parameters:
      function_name: "model-evaluation"
      payload:
        model_name: "{{ model_name }}"
    depends_on: [train_model]
    
  - id: deploy_model
    name: "Deploy Model"
    type: lambda
    parameters:
      function_name: "model-deployment"
      payload:
        model_name: "{{ model_name }}"
    depends_on: [evaluate_model]

metadata:
  owner: "ml-team"
  environment: "staging"
  model_type: "classification"
"""
    
    @staticmethod
    def batch_processing() -> str:
        """バッチ処理パイプラインのテンプレート例"""
        return """
version: "1.0"
name: "Batch Processing Pipeline"
description: "Large-scale batch data processing"

parameters:
  - name: input_path
    type: string
    required: true
    description: "Input data path"
  - name: output_path
    type: string
    required: true
    description: "Output data path"
  - name: batch_size
    type: integer
    default: 1000
    description: "Batch size for processing"

jobs:
  - id: validate_input
    name: "Validate Input"
    type: lambda
    parameters:
      function_name: "input-validation"
      payload:
        input_path: "{{ input_path }}"
    
  - id: process_batches
    name: "Process Batches"
    type: step_function
    parameters:
      state_machine_arn: "arn:aws:states:region:account:stateMachine:batch-processing"
      input:
        input_path: "{{ input_path }}"
        output_path: "{{ output_path }}"
        batch_size: "{{ batch_size }}"
    depends_on: [validate_input]
    timeout: 7200
    
  - id: aggregate_results
    name: "Aggregate Results"
    type: lambda
    parameters:
      function_name: "result-aggregation"
      payload:
        output_path: "{{ output_path }}"
    depends_on: [process_batches]

metadata:
  owner: "data-engineering"
  environment: "production"
  processing_type: "batch"
"""


class DSLTemplateError(Exception):
    """DSLテンプレートエラー"""
    pass 