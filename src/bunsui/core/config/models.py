"""
Configuration models for Bunsui.

This module contains configuration models for AWS integration,
pipeline settings, and general application configuration.
"""

from typing import Optional
from pydantic import BaseModel, Field, validator
from pathlib import Path
import os


class AWSConfig(BaseModel):
    """AWS configuration settings."""
    
    region: str = Field(
        default_factory=lambda: os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
        description="AWS region"
    )
    profile: Optional[str] = Field(
        default_factory=lambda: os.environ.get('AWS_PROFILE'),
        description="AWS profile name"
    )
    access_key_id: Optional[str] = Field(
        default_factory=lambda: os.environ.get('AWS_ACCESS_KEY_ID'),
        description="AWS access key ID"
    )
    secret_access_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get('AWS_SECRET_ACCESS_KEY'),
        description="AWS secret access key"
    )
    session_token: Optional[str] = Field(
        default_factory=lambda: os.environ.get('AWS_SESSION_TOKEN'),
        description="AWS session token"
    )
    
    # Service-specific settings
    dynamodb_table_prefix: str = Field(
        default="bunsui",
        description="Prefix for DynamoDB table names"
    )
    s3_bucket_prefix: str = Field(
        default="bunsui",
        description="Prefix for S3 bucket names"
    )
    stepfunctions_state_machine_prefix: str = Field(
        default="bunsui",
        description="Prefix for Step Functions state machine names"
    )
    
    # Timeout and retry settings
    timeout: int = Field(30, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, description="Maximum retry attempts")
    retry_delay: int = Field(1, ge=0, description="Initial retry delay in seconds")
    
    @validator('region')
    def validate_region(cls, v):
        """Validate AWS region."""
        valid_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 
            'eu-north-1', 'eu-south-1',
            'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
            'ap-south-1', 'ap-southeast-1', 'ap-southeast-2',
            'ca-central-1', 'sa-east-1', 'cn-north-1', 'cn-northwest-1'
        ]
        if v not in valid_regions:
            # Allow custom regions but log warning
            import logging
            logging.warning(f"Using non-standard AWS region: {v}")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_prefix = 'BUNSUI_AWS_'


class PipelineConfig(BaseModel):
    """Pipeline execution configuration."""
    
    default_timeout: int = Field(
        3600,
        ge=60,
        description="Default pipeline timeout in seconds"
    )
    max_concurrent_jobs: int = Field(
        10,
        ge=1,
        description="Maximum concurrent jobs per pipeline"
    )
    enable_checkpoints: bool = Field(
        True,
        description="Enable checkpoint creation during execution"
    )
    checkpoint_interval: int = Field(
        300,
        ge=60,
        description="Checkpoint interval in seconds"
    )
    
    # Error handling
    retry_failed_jobs: bool = Field(
        True,
        description="Automatically retry failed jobs"
    )
    max_job_retries: int = Field(
        3,
        ge=0,
        description="Maximum retries per job"
    )
    exponential_backoff: bool = Field(
        True,
        description="Use exponential backoff for retries"
    )
    
    # Monitoring
    enable_metrics: bool = Field(
        True,
        description="Enable CloudWatch metrics"
    )
    metrics_namespace: str = Field(
        "Bunsui/Pipeline",
        description="CloudWatch metrics namespace"
    )
    
    class Config:
        """Pydantic configuration."""
        env_prefix = 'BUNSUI_PIPELINE_'


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(
        "INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    log_to_file: bool = Field(
        False,
        description="Enable file logging"
    )
    log_file_path: Optional[Path] = Field(
        None,
        description="Log file path"
    )
    log_file_rotation: str = Field(
        "midnight",
        description="Log file rotation (midnight, size)"
    )
    log_file_max_bytes: int = Field(
        10485760,  # 10MB
        description="Maximum log file size in bytes"
    )
    log_file_backup_count: int = Field(
        7,
        description="Number of backup log files to keep"
    )
    
    # CloudWatch Logs integration
    enable_cloudwatch: bool = Field(
        False,
        description="Enable CloudWatch Logs"
    )
    cloudwatch_log_group: str = Field(
        "/aws/bunsui",
        description="CloudWatch Log Group"
    )
    cloudwatch_log_stream_prefix: str = Field(
        "pipeline",
        description="CloudWatch Log Stream prefix"
    )
    
    @validator('level')
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level: {v}")
        return v.upper()
    
    class Config:
        """Pydantic configuration."""
        env_prefix = 'BUNSUI_LOGGING_'


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    encrypt_at_rest: bool = Field(
        True,
        description="Enable encryption at rest for storage"
    )
    encrypt_in_transit: bool = Field(
        True,
        description="Enable encryption in transit"
    )
    kms_key_id: Optional[str] = Field(
        None,
        description="KMS key ID for encryption"
    )
    
    # IAM settings
    assume_role_arn: Optional[str] = Field(
        None,
        description="IAM role ARN to assume"
    )
    external_id: Optional[str] = Field(
        None,
        description="External ID for role assumption"
    )
    
    # API security
    api_key_required: bool = Field(
        False,
        description="Require API key for operations"
    )
    api_key_header: str = Field(
        "X-API-Key",
        description="API key header name"
    )
    
    class Config:
        """Pydantic configuration."""
        env_prefix = 'BUNSUI_SECURITY_'


class BunsuiConfig(BaseModel):
    """Main Bunsui configuration."""
    
    # Sub-configurations
    aws: AWSConfig = Field(
        default_factory=lambda: AWSConfig(),  # type: ignore
        description="AWS configuration"
    )
    pipeline: PipelineConfig = Field(
        default_factory=lambda: PipelineConfig(),  # type: ignore
        description="Pipeline configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=lambda: LoggingConfig(),  # type: ignore
        description="Logging configuration"
    )
    security: SecurityConfig = Field(
        default_factory=lambda: SecurityConfig(),  # type: ignore
        description="Security configuration"
    )
    
    # General settings
    environment: str = Field(
        default_factory=lambda: os.environ.get('BUNSUI_ENV', 'development'),
        description="Environment name (development, staging, production)"
    )
    debug: bool = Field(
        default_factory=lambda: os.environ.get('BUNSUI_DEBUG', 'false').lower() == 'true',
        description="Enable debug mode"
    )
    
    # Storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / '.bunsui' / 'data',
        description="Local data directory"
    )
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / '.bunsui' / 'config',
        description="Configuration directory"
    )
    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / '.bunsui' / 'cache',
        description="Cache directory"
    )
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment."""
        valid_environments = ['development', 'staging', 'production', 'test']
        if v not in valid_environments:
            raise ValueError(f"Invalid environment: {v}")
        return v
    
    def create_directories(self) -> None:
        """Create necessary directories."""
        for dir_path in [self.data_dir, self.config_dir, self.cache_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'BunsuiConfig':
        """Load configuration from file."""
        import yaml
        import json
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif file_path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {file_path.suffix}")
        
        return cls(**data)
    
    def to_file(self, file_path: Path) -> None:
        """Save configuration to file."""
        import yaml
        import json
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.dict(exclude_unset=True)
        
        with open(file_path, 'w') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                yaml.dump(data, f, default_flow_style=False)
            elif file_path.suffix == '.json':
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported configuration file format: {file_path.suffix}")
    
    def merge_with_env(self) -> None:
        """Merge configuration with environment variables."""
        # This is handled automatically by Pydantic with env_prefix
        pass
    
    class Config:
        """Pydantic configuration."""
        env_prefix = 'BUNSUI_'
        env_nested_delimiter = '__' 