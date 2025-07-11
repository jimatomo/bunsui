"""
Configuration manager for Bunsui.

This module provides the ConfigManager class for managing
application configuration from multiple sources.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
import json
from contextlib import contextmanager

from .models import BunsuiConfig, AWSConfig, PipelineConfig, LoggingConfig, SecurityConfig
from ..exceptions import ConfigurationError


class ConfigManager:
    """
    Manages Bunsui configuration from multiple sources.
    
    Configuration sources (in order of precedence):
    1. Environment variables
    2. Configuration files (JSON/YAML)
    3. Default values
    """
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Optional configuration file path
        """
        self._config: Optional[BunsuiConfig] = None
        self._config_file = config_file
        self._aws_clients: Dict[str, Any] = {}
        
    @property
    def config(self) -> BunsuiConfig:
        """Get current configuration."""
        if self._config is None:
            self.load_config()
        assert self._config is not None  # Type narrowing
        return self._config
    
    def load_config(self, config_file: Optional[Path] = None) -> BunsuiConfig:
        """
        Load configuration from file and environment.
        
        Args:
            config_file: Optional configuration file path
            
        Returns:
            Loaded configuration
        """
        config_file = config_file or self._config_file
        
        if config_file and config_file.exists():
            # Load from file
            self._config = BunsuiConfig.from_file(config_file)
        else:
            # Create default configuration
            self._config = BunsuiConfig()
        
        # Environment variables automatically override via Pydantic
        
        # Create necessary directories
        self._config.create_directories()
        
        return self._config
    
    def save_config(self, config_file: Optional[Path] = None) -> None:
        """
        Save current configuration to file.
        
        Args:
            config_file: Optional configuration file path
        """
        if self._config is None:
            raise ConfigurationError("No configuration loaded")
        
        config_file = config_file or self._config_file
        if not config_file:
            # Default location
            config_file = self._config.config_dir / 'config.yaml'
        
        self._config.to_file(config_file)
        self._config_file = config_file
    
    def get_aws_config(self) -> AWSConfig:
        """Get AWS configuration."""
        return self.config.aws
    
    def get_pipeline_config(self) -> PipelineConfig:
        """Get pipeline configuration."""
        return self.config.pipeline
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self.config.logging
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        return self.config.security
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        if self._config is None:
            self.load_config()
        
        # Deep update configuration
        for key, value in updates.items():
            if hasattr(self._config, key):
                if isinstance(value, dict) and hasattr(getattr(self._config, key), '__dict__'):
                    # Update nested configuration
                    nested_obj = getattr(self._config, key)
                    for nested_key, nested_value in value.items():
                        if hasattr(nested_obj, nested_key):
                            setattr(nested_obj, nested_key, nested_value)
                else:
                    setattr(self._config, key, value)
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        
        Args:
            key_path: Dot-separated configuration path (e.g., 'aws.region')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        if self._config is None:
            self.load_config()
        
        current = self._config
        for key in key_path.split('.'):
            if hasattr(current, key):
                current = getattr(current, key)
            else:
                return default
        
        return current
    
    def set_value(self, key_path: str, value: Any) -> None:
        """
        Set configuration value by dot-separated path.
        
        Args:
            key_path: Dot-separated configuration path (e.g., 'aws.region')
            value: Value to set
        """
        if self._config is None:
            self.load_config()
        
        keys = key_path.split('.')
        current = self._config
        
        # Navigate to parent
        for key in keys[:-1]:
            if hasattr(current, key):
                current = getattr(current, key)
            else:
                raise ConfigurationError(f"Invalid configuration path: {key_path}")
        
        # Set value
        if hasattr(current, keys[-1]):
            setattr(current, keys[-1], value)
        else:
            raise ConfigurationError(f"Invalid configuration key: {keys[-1]}")
    
    def delete_value(self, key_path: str) -> None:
        """
        Delete configuration value by dot-separated path.
        
        Args:
            key_path: Dot-separated configuration path (e.g., 'aws.profile')
        """
        if self._config is None:
            self.load_config()
        
        keys = key_path.split('.')
        current = self._config
        
        # Navigate to parent
        for key in keys[:-1]:
            if hasattr(current, key):
                current = getattr(current, key)
            else:
                raise ConfigurationError(f"Invalid configuration path: {key_path}")
        
        # Set to None or default
        if hasattr(current, keys[-1]):
            if hasattr(current, 'model_fields'):
                field_info = getattr(current, 'model_fields', {}).get(keys[-1])
                if field_info and hasattr(field_info, 'default') and field_info.default is not None:
                    setattr(current, keys[-1], field_info.default)
                else:
                    setattr(current, keys[-1], None)
            else:
                setattr(current, keys[-1], None)
        else:
            raise ConfigurationError(f"Invalid configuration key: {keys[-1]}")
    
    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self._config = BunsuiConfig()
        self._config.create_directories()
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate current configuration.
        
        Returns:
            Validation results
        """
        if self._config is None:
            self.load_config()
        
        assert self._config is not None  # Type narrowing
        
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check AWS configuration
        if not self._config.aws.region:
            results['errors'].append("AWS region not configured")
            results['valid'] = False
        
        # Check if credentials are available
        if not any([
            self._config.aws.profile,
            self._config.aws.access_key_id,
            os.environ.get('AWS_PROFILE'),
            os.environ.get('AWS_ACCESS_KEY_ID')
        ]):
            results['warnings'].append("No AWS credentials configured")
        
        # Check pipeline configuration
        if self._config.pipeline.default_timeout < 60:
            results['warnings'].append("Pipeline timeout is very low")
        
        # Check logging configuration
        if self._config.logging.enable_cloudwatch and not self._config.aws.region:
            results['errors'].append("CloudWatch logging enabled but AWS region not configured")
            results['valid'] = False
        
        return results
    
    def export_config(self, format: str = 'yaml') -> str:
        """
        Export configuration as string.
        
        Args:
            format: Export format ('yaml' or 'json')
            
        Returns:
            Configuration string
        """
        if self._config is None:
            self.load_config()
        
        assert self._config is not None  # Type narrowing
        
        data = self._config.dict(exclude_unset=True)
        
        if format == 'yaml':
            return yaml.dump(data, default_flow_style=False)
        elif format == 'json':
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_config(self, config_str: str, format: str = 'yaml') -> None:
        """
        Import configuration from string.
        
        Args:
            config_str: Configuration string
            format: Import format ('yaml' or 'json')
        """
        if format == 'yaml':
            data = yaml.safe_load(config_str)
        elif format == 'json':
            data = json.loads(config_str)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self._config = BunsuiConfig(**data)
        self._config.create_directories()
    
    @contextmanager
    def temporary_config(self, updates: Dict[str, Any]):
        """
        Context manager for temporary configuration changes.
        
        Args:
            updates: Temporary configuration updates
        """
        if self._config is None:
            self.load_config()
        
        assert self._config is not None  # Type narrowing
        
        # Save current config
        original_config = self._config.dict()
        
        try:
            # Apply updates
            self.update_config(updates)
            yield self._config
        finally:
            # Restore original config
            self._config = BunsuiConfig(**original_config)
    
    def get_aws_client_config(self) -> Dict[str, Any]:
        """
        Get AWS client configuration for boto3.
        
        Returns:
            Dictionary of AWS client configuration
        """
        aws_config = self.get_aws_config()
        
        config = {
            'region_name': aws_config.region,
        }
        
        if aws_config.profile:
            config['profile_name'] = aws_config.profile
        
        if aws_config.access_key_id and aws_config.secret_access_key:
            config['aws_access_key_id'] = aws_config.access_key_id
            config['aws_secret_access_key'] = aws_config.secret_access_key
            
            if aws_config.session_token:
                config['aws_session_token'] = aws_config.session_token
        
        return config
    
    def __repr__(self) -> str:
        return f"ConfigManager(config_file={self._config_file})"


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        # Try to load from default location
        default_config_file = Path.home() / '.bunsui' / 'config' / 'config.yaml'
        if default_config_file.exists():
            _config_manager = ConfigManager(default_config_file)
        else:
            _config_manager = ConfigManager()
    return _config_manager


def set_config_manager(manager: ConfigManager) -> None:
    """Set global configuration manager instance."""
    global _config_manager
    _config_manager = manager 