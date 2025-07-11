"""
Pipeline definition DSL schema for Bunsui.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class SchemaType(Enum):
    """Schema type enumeration."""
    OBJECT = "object"
    ARRAY = "array"
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


@dataclass
class SchemaProperty:
    """Schema property definition."""
    type: SchemaType
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    items: Optional['SchemaProperty'] = None
    properties: Optional[Dict[str, 'SchemaProperty']] = None


class DSLSchema:
    """パイプライン定義DSLのスキーマ"""
    
    def __init__(self):
        self.pipeline_schema = self._create_pipeline_schema()
        self.job_schema = self._create_job_schema()
        self.parameter_schema = self._create_parameter_schema()
    
    def _create_pipeline_schema(self) -> SchemaProperty:
        """パイプラインスキーマを作成"""
        return SchemaProperty(
            type=SchemaType.OBJECT,
            description="Pipeline definition",
            properties={
                "version": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Pipeline version",
                    enum=["1.0", "1.1"],
                    required=True
                ),
                "name": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Pipeline name",
                    pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
                    required=True
                ),
                "description": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Pipeline description"
                ),
                "parameters": SchemaProperty(
                    type=SchemaType.ARRAY,
                    description="Pipeline parameters",
                    items=self.parameter_schema
                ),
                "jobs": SchemaProperty(
                    type=SchemaType.ARRAY,
                    description="Pipeline jobs",
                    items=self.job_schema,
                    required=True
                ),
                "metadata": SchemaProperty(
                    type=SchemaType.OBJECT,
                    description="Pipeline metadata"
                )
            }
        )
    
    def _create_job_schema(self) -> SchemaProperty:
        """ジョブスキーマを作成"""
        return SchemaProperty(
            type=SchemaType.OBJECT,
            description="Job definition",
            properties={
                "id": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Job ID",
                    pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
                    required=True
                ),
                "name": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Job name",
                    pattern=r"^[a-zA-Z][a-zA-Z0-9_\s-]*$"
                ),
                "type": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Job type",
                    enum=["lambda", "ecs", "step_function", "glue", "emr", "custom"],
                    required=True
                ),
                "parameters": SchemaProperty(
                    type=SchemaType.OBJECT,
                    description="Job parameters"
                ),
                "depends_on": SchemaProperty(
                    type=SchemaType.ARRAY,
                    description="Job dependencies",
                    items=SchemaProperty(type=SchemaType.STRING)
                ),
                "timeout": SchemaProperty(
                    type=SchemaType.INTEGER,
                    description="Job timeout in seconds",
                    min_value=1
                ),
                "retries": SchemaProperty(
                    type=SchemaType.INTEGER,
                    description="Number of retries",
                    min_value=0,
                    default=0
                ),
                "retry_delay": SchemaProperty(
                    type=SchemaType.INTEGER,
                    description="Retry delay in seconds",
                    min_value=0,
                    default=60
                ),
                "condition": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Job execution condition"
                )
            }
        )
    
    def _create_parameter_schema(self) -> SchemaProperty:
        """パラメータスキーマを作成"""
        return SchemaProperty(
            type=SchemaType.OBJECT,
            description="Parameter definition",
            properties={
                "name": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Parameter name",
                    pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
                    required=True
                ),
                "type": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Parameter type",
                    enum=["string", "integer", "float", "boolean", "array", "object"],
                    default="string"
                ),
                "required": SchemaProperty(
                    type=SchemaType.BOOLEAN,
                    description="Whether parameter is required",
                    default=False
                ),
                "default": SchemaProperty(
                    type=SchemaType.OBJECT,
                    description="Default value"
                ),
                "description": SchemaProperty(
                    type=SchemaType.STRING,
                    description="Parameter description"
                ),
                "validation": SchemaProperty(
                    type=SchemaType.OBJECT,
                    description="Validation rules",
                    properties={
                        "min": SchemaProperty(
                            type=SchemaType.NUMBER,
                            description="Minimum value/length"
                        ),
                        "max": SchemaProperty(
                            type=SchemaType.NUMBER,
                            description="Maximum value/length"
                        ),
                        "pattern": SchemaProperty(
                            type=SchemaType.STRING,
                            description="Regex pattern"
                        ),
                        "enum": SchemaProperty(
                            type=SchemaType.ARRAY,
                            description="Allowed values"
                        )
                    }
                )
            }
        )
    
    def validate_against_schema(self, data: Dict[str, Any], schema: SchemaProperty) -> List[str]:
        """データをスキーマに対して検証"""
        errors = []
        
        if schema.type == SchemaType.OBJECT:
            errors.extend(self._validate_object(data, schema))
        elif schema.type == SchemaType.ARRAY:
            errors.extend(self._validate_array(data, schema))
        elif schema.type == SchemaType.STRING:
            errors.extend(self._validate_string(data, schema))
        elif schema.type == SchemaType.INTEGER:
            errors.extend(self._validate_integer(data, schema))
        elif schema.type == SchemaType.NUMBER:
            errors.extend(self._validate_number(data, schema))
        elif schema.type == SchemaType.BOOLEAN:
            errors.extend(self._validate_boolean(data, schema))
        
        return errors
    
    def _validate_object(self, data: Any, schema: SchemaProperty) -> List[str]:
        """オブジェクトを検証"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append(f"Expected object, got {type(data).__name__}")
            return errors
        
        if schema.properties:
            # 必須フィールドのチェック
            for prop_name, prop_schema in schema.properties.items():
                if prop_schema.required and prop_name not in data:
                    errors.append(f"Required property '{prop_name}' is missing")
            
            # 各プロパティの検証
            for prop_name, prop_value in data.items():
                if prop_name in schema.properties:
                    prop_schema = schema.properties[prop_name]
                    prop_errors = self.validate_against_schema(prop_value, prop_schema)
                    for error in prop_errors:
                        errors.append(f"Property '{prop_name}': {error}")
                else:
                    errors.append(f"Unknown property '{prop_name}'")
        
        return errors
    
    def _validate_array(self, data: Any, schema: SchemaProperty) -> List[str]:
        """配列を検証"""
        errors = []
        
        if not isinstance(data, list):
            errors.append(f"Expected array, got {type(data).__name__}")
            return errors
        
        if schema.items:
            for i, item in enumerate(data):
                item_errors = self.validate_against_schema(item, schema.items)
                for error in item_errors:
                    errors.append(f"Array item {i}: {error}")
        
        return errors
    
    def _validate_string(self, data: Any, schema: SchemaProperty) -> List[str]:
        """文字列を検証"""
        errors = []
        
        if not isinstance(data, str):
            errors.append(f"Expected string, got {type(data).__name__}")
            return errors
        
        # パターンチェック
        if schema.pattern:
            import re
            if not re.match(schema.pattern, data):
                errors.append(f"String does not match pattern '{schema.pattern}'")
        
        # 列挙値チェック
        if schema.enum and data not in schema.enum:
            errors.append(f"String value '{data}' is not in allowed values {schema.enum}")
        
        # 長さチェック
        if schema.min_length is not None and len(data) < schema.min_length:
            errors.append(f"String length {len(data)} is less than minimum {schema.min_length}")
        
        if schema.max_length is not None and len(data) > schema.max_length:
            errors.append(f"String length {len(data)} is greater than maximum {schema.max_length}")
        
        return errors
    
    def _validate_integer(self, data: Any, schema: SchemaProperty) -> List[str]:
        """整数を検証"""
        errors = []
        
        if not isinstance(data, int):
            errors.append(f"Expected integer, got {type(data).__name__}")
            return errors
        
        # 値の範囲チェック
        if schema.min_value is not None and data < schema.min_value:
            errors.append(f"Integer value {data} is less than minimum {schema.min_value}")
        
        if schema.max_value is not None and data > schema.max_value:
            errors.append(f"Integer value {data} is greater than maximum {schema.max_value}")
        
        return errors
    
    def _validate_number(self, data: Any, schema: SchemaProperty) -> List[str]:
        """数値を検証"""
        errors = []
        
        if not isinstance(data, (int, float)):
            errors.append(f"Expected number, got {type(data).__name__}")
            return errors
        
        # 値の範囲チェック
        if schema.min_value is not None and data < schema.min_value:
            errors.append(f"Number value {data} is less than minimum {schema.min_value}")
        
        if schema.max_value is not None and data > schema.max_value:
            errors.append(f"Number value {data} is greater than maximum {schema.max_value}")
        
        return errors
    
    def _validate_boolean(self, data: Any, schema: SchemaProperty) -> List[str]:
        """真偽値を検証"""
        errors = []
        
        if not isinstance(data, bool):
            errors.append(f"Expected boolean, got {type(data).__name__}")
            return errors
        
        return errors
    
    def get_schema_for_version(self, version: str) -> SchemaProperty:
        """バージョンに対応するスキーマを取得"""
        if version not in ["1.0", "1.1"]:
            raise ValueError(f"Unsupported version: {version}")
        
        return self.pipeline_schema
    
    def generate_schema_documentation(self) -> str:
        """スキーマドキュメントを生成"""
        doc = "# Pipeline DSL Schema\n\n"
        doc += "## Pipeline Definition\n\n"
        doc += self._generate_property_documentation(self.pipeline_schema, 0)
        return doc
    
    def _generate_property_documentation(self, schema: SchemaProperty, level: int) -> str:
        """プロパティドキュメントを生成"""
        indent = "  " * level
        doc = ""
        
        if schema.description:
            doc += f"{indent}**Description**: {schema.description}\n"
        
        doc += f"{indent}**Type**: {schema.type.value}\n"
        
        if schema.required:
            doc += f"{indent}**Required**: Yes\n"
        
        if schema.default is not None:
            doc += f"{indent}**Default**: {schema.default}\n"
        
        if schema.enum:
            doc += f"{indent}**Allowed Values**: {', '.join(map(str, schema.enum))}\n"
        
        if schema.min_value is not None:
            doc += f"{indent}**Minimum**: {schema.min_value}\n"
        
        if schema.max_value is not None:
            doc += f"{indent}**Maximum**: {schema.max_value}\n"
        
        if schema.min_length is not None:
            doc += f"{indent}**Min Length**: {schema.min_length}\n"
        
        if schema.max_length is not None:
            doc += f"{indent}**Max Length**: {schema.max_length}\n"
        
        if schema.pattern:
            doc += f"{indent}**Pattern**: `{schema.pattern}`\n"
        
        if schema.properties:
            doc += f"\n{indent}**Properties**:\n"
            for prop_name, prop_schema in schema.properties.items():
                doc += f"\n{indent}### {prop_name}\n"
                doc += self._generate_property_documentation(prop_schema, level + 1)
        
        if schema.items:
            doc += f"\n{indent}**Items**:\n"
            doc += self._generate_property_documentation(schema.items, level + 1)
        
        return doc 