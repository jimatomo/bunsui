"""
Configuration manager for Bunsui.

This module provides the ConfigManager class for managing
application configuration from multiple sources.
"""

import os
from pathlib import Path

from typing import Optional, Dict, Any, List
import yaml
import json
from contextlib import contextmanager

from .models import BunsuiConfig, AWSConfig, PipelineConfig, LoggingConfig, SecurityConfig
from ..exceptions import ConfigurationError


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    プロジェクトルートディレクトリを見つける
    
    Args:
        start_path: 検索開始パス（デフォルト: 現在のディレクトリ）
        
    Returns:
        プロジェクトルートパス（見つからない場合はNone）
    """
    current = start_path or Path.cwd()
    
    # ファイルシステムのルートまで遡る
    for parent in [current] + list(current.parents):
        # Git リポジトリの場合
        if (parent / '.git').exists():
            return parent
        # pyproject.toml がある場合
        if (parent / 'pyproject.toml').exists():
            return parent
        # setup.py がある場合
        if (parent / 'setup.py').exists():
            return parent
        # package.json がある場合（Node.js プロジェクト）
        if (parent / 'package.json').exists():
            return parent
        # Bunsui 設定ディレクトリがある場合
        if (parent / '.bunsui').exists():
            return parent
    
    return None


def find_config_files() -> List[Path]:
    """
    設定ファイルの検索優先順位に基づいてファイルパスのリストを返す
    
    Returns:
        設定ファイルパスのリスト（優先順位順）
    """
    config_files = []
    
    # 1. 環境変数で指定されたファイル（最優先）
    env_config = os.environ.get('BUNSUI_CONFIG_FILE')
    if env_config:
        config_files.append(Path(env_config))
    
    # 2. 環境変数で指定されたディレクトリ内の設定ファイル
    env_config_dir = os.environ.get('BUNSUI_CONFIG_DIR')
    if env_config_dir:
        config_files.append(Path(env_config_dir) / 'config.yaml')
        config_files.append(Path(env_config_dir) / 'bunsui.yaml')
    
    # 3. 現在ディレクトリの .bunsui/config.yaml
    current_dir_config = Path.cwd() / '.bunsui' / 'config.yaml'
    config_files.append(current_dir_config)
    
    # 4. プロジェクトルートの .bunsui/config.yaml
    project_root = find_project_root()
    if project_root:
        project_config = project_root / '.bunsui' / 'config.yaml'
        # 現在ディレクトリと異なる場合のみ追加
        if project_config != current_dir_config:
            config_files.append(project_config)
    
    # 5. ホームディレクトリの ~/.bunsui/config/config.yaml
    home_config = Path.home() / '.bunsui' / 'config' / 'config.yaml'
    config_files.append(home_config)
    
    # 6. システム全体の設定（コンテナ対応）
    system_configs = [
        Path('/etc/bunsui/config.yaml'),
        Path('/etc/bunsui/bunsui.yaml'),
        Path('/usr/local/etc/bunsui/config.yaml'),
        Path('/opt/bunsui/config.yaml')
    ]
    config_files.extend(system_configs)
    
    return config_files


def find_existing_config_file() -> Optional[Path]:
    """
    存在する設定ファイルを優先順位に基づいて検索
    
    Returns:
        見つかった設定ファイルパス（存在しない場合はNone）
    """
    for config_file in find_config_files():
        if config_file.exists():
            return config_file
    return None


def find_secrets_files() -> List[Path]:
    """
    シークレットファイルの検索優先順位に基づいてファイルパスのリストを返す
    
    Returns:
        シークレットファイルパスのリスト（優先順位順）
    """
    secrets_files = []
    
    # 1. 環境変数で指定されたファイル（最優先）
    env_secrets = os.environ.get('BUNSUI_SECRETS_FILE')
    if env_secrets:
        secrets_files.append(Path(env_secrets))
    
    # 2. 環境変数で指定されたディレクトリ内のシークレットファイル
    env_config_dir = os.environ.get('BUNSUI_CONFIG_DIR')
    if env_config_dir:
        secrets_files.append(Path(env_config_dir) / 'secrets.yaml')
    
    # 3. 現在ディレクトリの .bunsui/secrets.yaml
    current_dir_secrets = Path.cwd() / '.bunsui' / 'secrets.yaml'
    secrets_files.append(current_dir_secrets)
    
    # 4. プロジェクトルートの .bunsui/secrets.yaml
    project_root = find_project_root()
    if project_root:
        project_secrets = project_root / '.bunsui' / 'secrets.yaml'
        # 現在ディレクトリと異なる場合のみ追加
        if project_secrets != current_dir_secrets:
            secrets_files.append(project_secrets)
    
    # 5. ホームディレクトリの ~/.bunsui/config/secrets.yaml
    home_secrets = Path.home() / '.bunsui' / 'config' / 'secrets.yaml'
    secrets_files.append(home_secrets)
    
    # 6. システム全体のシークレット（コンテナ対応）
    system_secrets = [
        Path('/etc/bunsui/secrets.yaml'),
        Path('/usr/local/etc/bunsui/secrets.yaml'),
        Path('/run/secrets/bunsui.yaml'),  # Docker Swarm secrets
        Path('/var/secrets/bunsui.yaml')   # Kubernetes secrets
    ]
    secrets_files.extend(system_secrets)
    
    return secrets_files


def find_existing_secrets_file() -> Optional[Path]:
    """
    存在するシークレットファイルを優先順位に基づいて検索
    
    Returns:
        見つかったシークレットファイルパス（存在しない場合はNone）
    """
    for secrets_file in find_secrets_files():
        if secrets_file.exists():
            return secrets_file
    return None


def is_sensitive_key(key_path: str) -> bool:
    """
    設定キーが機密情報かどうかを判定
    
    Args:
        key_path: ドット区切りの設定キーパス
        
    Returns:
        機密情報の場合True
    """
    sensitive_keywords = [
        'password', 'secret', 'key', 'token', 'credential',
        'access_key_id', 'secret_access_key', 'session_token',
        'api_key', 'private_key', 'certificate', 'passphrase'
    ]
    
    key_lower = key_path.lower()
    return any(keyword in key_lower for keyword in sensitive_keywords)


def separate_sensitive_config(config_data: dict) -> tuple[dict, dict]:
    """
    設定データを機密情報と非機密情報に分離
    
    Args:
        config_data: 設定データ
        
    Returns:
        (非機密設定, 機密設定) のタプル
    """
    def separate_dict(data: dict, parent_key: str = '') -> tuple[dict, dict]:
        """辞書を再帰的に分離"""
        public_data = {}
        sensitive_data = {}
        
        for key, value in data.items():
            current_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                # 辞書の場合は再帰的に処理
                public_sub, sensitive_sub = separate_dict(value, current_key)
                if public_sub:
                    public_data[key] = public_sub
                if sensitive_sub:
                    sensitive_data[key] = sensitive_sub
            else:
                # 機密情報かどうかを判定
                if is_sensitive_key(current_key):
                    sensitive_data[key] = value
                else:
                    public_data[key] = value
        
        return public_data, sensitive_data
    
    return separate_dict(config_data)


def find_environment_config_files(environment: str) -> List[Path]:
    """
    環境固有設定ファイルの検索優先順位に基づいてファイルパスのリストを返す
    
    Args:
        environment: 環境名（development, staging, production, etc.）
        
    Returns:
        環境固有設定ファイルパスのリスト（優先順位順）
    """
    env_config_files = []
    
    # 1. 現在ディレクトリの .bunsui/config.{environment}.yaml
    current_dir_env_config = Path.cwd() / '.bunsui' / f'config.{environment}.yaml'
    env_config_files.append(current_dir_env_config)
    
    # 2. プロジェクトルートの .bunsui/config.{environment}.yaml
    project_root = find_project_root()
    if project_root:
        project_env_config = project_root / '.bunsui' / f'config.{environment}.yaml'
        # 現在ディレクトリと異なる場合のみ追加
        if project_env_config != current_dir_env_config:
            env_config_files.append(project_env_config)
    
    # 3. ホームディレクトリの ~/.bunsui/config/config.{environment}.yaml
    home_env_config = Path.home() / '.bunsui' / 'config' / f'config.{environment}.yaml'
    env_config_files.append(home_env_config)
    
    return env_config_files


def find_existing_environment_config_files(environment: str) -> List[Path]:
    """
    存在する環境固有設定ファイルを優先順位に基づいて検索
    
    Args:
        environment: 環境名
        
    Returns:
        見つかった環境固有設定ファイルパスのリスト
    """
    existing_files = []
    for config_file in find_environment_config_files(environment):
        if config_file.exists():
            existing_files.append(config_file)
    return existing_files


class ConfigManager:
    """
    Manages Bunsui configuration from multiple sources.
    
    Configuration sources (in order of precedence):
    1. Environment variables (BUNSUI_CONFIG_FILE)
    2. Current directory (.bunsui/config.yaml)
    3. Project root (.bunsui/config.yaml)
    4. Home directory (~/.bunsui/config/config.yaml)
    5. System directory (/etc/bunsui/config.yaml)
    6. Environment variables (BUNSUI_*)
    7. Default values
    
    Secrets sources (in order of precedence):
    1. Environment variables (BUNSUI_SECRETS_FILE)
    2. Current directory (.bunsui/secrets.yaml)
    3. Project root (.bunsui/secrets.yaml)
    4. Home directory (~/.bunsui/config/secrets.yaml)
    """
    
    def __init__(self, config_file: Optional[Path] = None, secrets_file: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Optional configuration file path
            secrets_file: Optional secrets file path
        """
        self._config: Optional[BunsuiConfig] = None
        self._config_file = config_file
        self._secrets_file = secrets_file
        self._loaded_config_file: Optional[Path] = None
        self._loaded_secrets_file: Optional[Path] = None
        self._aws_clients: Dict[str, Any] = {}
        
    @property
    def config(self) -> BunsuiConfig:
        """Get current configuration."""
        if self._config is None:
            self.load_config()
        assert self._config is not None  # Type narrowing
        return self._config
    
    @property
    def loaded_config_file(self) -> Optional[Path]:
        """Get the path of the currently loaded configuration file."""
        return self._loaded_config_file
    
    @property
    def loaded_secrets_file(self) -> Optional[Path]:
        """Get the path of the currently loaded secrets file."""
        return self._loaded_secrets_file
    
    def get_config_search_paths(self) -> List[Path]:
        """Get list of configuration file search paths in order of precedence."""
        return find_config_files()
    
    def get_secrets_search_paths(self) -> List[Path]:
        """Get list of secrets file search paths in order of precedence."""
        return find_secrets_files()
    
    def load_config(self, config_file: Optional[Path] = None, secrets_file: Optional[Path] = None) -> BunsuiConfig:
        """
        Load configuration from file and environment with secrets support.
        
        Args:
            config_file: Optional configuration file path
            secrets_file: Optional secrets file path
            
        Returns:
            Loaded configuration
        """
        # 設定ファイルの読み込み（既存のロジック）
        if config_file:
            # 明示的にファイルが指定された場合
            self._config_file = config_file
            self._loaded_config_file = config_file
            if config_file.exists():
                self._config = self._load_config_with_inheritance(config_file)
            else:
                raise ConfigurationError(f"Specified configuration file not found: {config_file}")
        else:
            # 自動検索モード
            if self._config_file and self._config_file.exists():
                # 初期化時に指定されたファイルがある場合
                self._loaded_config_file = self._config_file
                self._config = self._load_config_with_inheritance(self._config_file)
            else:
                # 優先順位に基づいて検索
                found_config_file = find_existing_config_file()
                if found_config_file:
                    self._loaded_config_file = found_config_file
                    self._config = self._load_config_with_inheritance(found_config_file)
                else:
                    # デフォルト設定を使用
                    self._loaded_config_file = None
                    self._config = BunsuiConfig()
        
        # シークレットファイルの読み込み
        self._load_secrets(secrets_file)
        
        # 環境固有設定の読み込み
        self._load_environment_overrides()
        
        # Environment variables automatically override via Pydantic
        
        # Create necessary directories
        self._config.create_directories()
        
        return self._config
    
    def _load_secrets(self, secrets_file: Optional[Path] = None) -> None:
        """
        シークレットファイルを読み込んで設定に適用
        
        Args:
            secrets_file: シークレットファイルのパス
        """
        import yaml
        import json
        
        if secrets_file:
            self._secrets_file = secrets_file
            target_secrets_file = secrets_file
        else:
            # 自動検索
            if self._secrets_file and self._secrets_file.exists():
                target_secrets_file = self._secrets_file
            else:
                target_secrets_file = find_existing_secrets_file()
        
        if target_secrets_file and target_secrets_file.exists():
            self._loaded_secrets_file = target_secrets_file
            
            try:
                with open(target_secrets_file, 'r', encoding='utf-8') as f:
                    if target_secrets_file.suffix in ['.yaml', '.yml']:
                        secrets_data = yaml.safe_load(f) or {}
                    elif target_secrets_file.suffix == '.json':
                        secrets_data = json.load(f)
                    else:
                        # console.print(f"[yellow]Unsupported secrets file format: {target_secrets_file}[/yellow]") # Removed console.print
                        pass # Removed console.print
                
                # シークレットデータを設定に適用
                self._apply_secrets_to_config(secrets_data)
                
            except Exception as e:
                # console.print(f"[yellow]Failed to load secrets file {target_secrets_file}: {e}[/yellow]") # Removed console.print
                pass # Removed console.print
    
    def _apply_secrets_to_config(self, secrets_data: dict) -> None:
        """
        シークレットデータを設定に適用
        
        Args:
            secrets_data: シークレットデータ
        """
        def apply_nested_secrets(config_obj, secrets_dict, path=""):
            """ネストしたシークレットを適用"""
            for key, value in secrets_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(value, dict):
                    # ネストした辞書の場合
                    if hasattr(config_obj, key):
                        nested_obj = getattr(config_obj, key)
                        if nested_obj is not None:
                            apply_nested_secrets(nested_obj, value, current_path)
                else:
                    # 値の場合
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)
        
        apply_nested_secrets(self._config, secrets_data)
    
    def _load_environment_overrides(self) -> None:
        """
        環境固有の設定オーバーライドを読み込んで適用
        """
        if not self._config:
            return
        
        # 現在の環境を取得
        environment = self._config.environment
        if not environment:
            return
        
        # 環境固有設定ファイルを検索
        env_config_files = find_existing_environment_config_files(environment)
        
        import yaml
        import json
        
        # 見つかった環境固有設定ファイルを順番に適用
        for env_config_file in env_config_files:
            try:
                with open(env_config_file, 'r', encoding='utf-8') as f:
                    if env_config_file.suffix in ['.yaml', '.yml']:
                        env_data = yaml.safe_load(f) or {}
                    elif env_config_file.suffix == '.json':
                        env_data = json.load(f)
                    else:
                        continue
                
                # 環境固有設定を現在の設定にマージ
                self._apply_environment_overrides(env_data)
                
            except Exception as e:
                # 環境固有設定の読み込みに失敗してもエラーとしない
                pass
    
    def _apply_environment_overrides(self, env_data: dict) -> None:
        """
        環境固有設定を現在の設定に適用
        
        Args:
            env_data: 環境固有設定データ
        """
        def apply_nested_overrides(config_obj, override_dict, path=""):
            """ネストした設定オーバーライドを適用"""
            for key, value in override_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(value, dict):
                    # ネストした辞書の場合
                    if hasattr(config_obj, key):
                        nested_obj = getattr(config_obj, key)
                        if nested_obj is not None:
                            apply_nested_overrides(nested_obj, value, current_path)
                else:
                    # 値の場合
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)
        
        apply_nested_overrides(self._config, env_data)
    
    def create_environment_config_template(self, environment: str, template_path: Optional[Path] = None) -> Path:
        """
        環境固有設定テンプレートを作成
        
        Args:
            environment: 環境名
            template_path: テンプレートファイルのパス（指定しない場合は自動決定）
            
        Returns:
            作成されたテンプレートファイルのパス
        """
        if not template_path:
            # プロジェクトルートまたは現在ディレクトリに作成
            project_root = find_project_root()
            base_dir = project_root if project_root else Path.cwd()
            template_path = base_dir / '.bunsui' / f'config.{environment}.yaml'
        
        # 環境別のデフォルト設定
        env_templates = {
            'development': {
                'debug': True,
                'aws': {
                    'region': 'us-east-1',
                    'dynamodb_table_prefix': f'bunsui-dev',
                    's3_bucket_prefix': f'bunsui-dev'
                },
                'logging': {
                    'level': 'DEBUG',
                    'log_to_file': True,
                    'enable_cloudwatch': False
                }
            },
            'staging': {
                'debug': False,
                'aws': {
                    'region': 'us-east-1',
                    'dynamodb_table_prefix': f'bunsui-staging',
                    's3_bucket_prefix': f'bunsui-staging'
                },
                'logging': {
                    'level': 'INFO',
                    'log_to_file': True,
                    'enable_cloudwatch': True
                },
                'pipeline': {
                    'max_concurrent_jobs': 3
                }
            },
            'production': {
                'debug': False,
                'aws': {
                    'region': 'us-east-1',
                    'dynamodb_table_prefix': f'bunsui-prod',
                    's3_bucket_prefix': f'bunsui-prod'
                },
                'logging': {
                    'level': 'WARNING',
                    'log_to_file': True,
                    'enable_cloudwatch': True
                },
                'pipeline': {
                    'max_concurrent_jobs': 10,
                    'default_timeout': 7200
                },
                'security': {
                    'encrypt_at_rest': True,
                    'encrypt_in_transit': True
                }
            }
        }
        
        template_data = env_templates.get(environment, {
            'debug': False,
            'aws': {
                'dynamodb_table_prefix': f'bunsui-{environment}',
                's3_bucket_prefix': f'bunsui-{environment}'
            }
        })
        
        # テンプレートファイルを保存
        template_path.parent.mkdir(parents=True, exist_ok=True)
        
        import yaml
        with open(template_path, 'w', encoding='utf-8') as f:
            yaml.dump(template_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        return template_path
    
    def save_config_separated(self, config_file: Optional[Path] = None, secrets_file: Optional[Path] = None, scope: str = 'auto') -> None:
        """
        設定を機密情報と非機密情報に分離して保存
        
        Args:
            config_file: 設定ファイルパス
            secrets_file: シークレットファイルパス
            scope: 設定のスコープ
        """
        if self._config is None:
            raise ConfigurationError("No configuration loaded")
        
        # 保存先ファイルパスの決定
        if not config_file:
            config_file = self._determine_config_file_path(scope)
        
        if not secrets_file:
            secrets_file = self._determine_secrets_file_path(config_file, scope)
        
        # 設定データを取得
        config_data = self._config.model_dump(exclude={'config_file_path'}, exclude_unset=True)
        
        # 機密情報と非機密情報に分離
        public_config, sensitive_config = separate_sensitive_config(config_data)
        
        # 非機密設定ファイルを保存
        config_file.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(public_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        # 機密設定ファイルを保存（データがある場合のみ）
        if sensitive_config:
            secrets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(secrets_file, 'w', encoding='utf-8') as f:
                yaml.dump(sensitive_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # シークレットファイルの権限を制限
            import stat
            secrets_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        
        self._loaded_config_file = config_file
        self._loaded_secrets_file = secrets_file if sensitive_config else None
    
    def _determine_config_file_path(self, scope: str) -> Path:
        """設定ファイルパスを決定"""
        if scope == 'local':
            return Path.cwd() / '.bunsui' / 'config.yaml'
        elif scope == 'project':
            project_root = find_project_root()
            if project_root:
                return project_root / '.bunsui' / 'config.yaml'
            else:
                return Path.cwd() / '.bunsui' / 'config.yaml'
        elif scope == 'global':
            return Path.home() / '.bunsui' / 'config' / 'config.yaml'
        else:  # auto
            if self._loaded_config_file:
                return self._loaded_config_file
            else:
                project_root = find_project_root()
                if project_root:
                    return project_root / '.bunsui' / 'config.yaml'
                else:
                    return Path.cwd() / '.bunsui' / 'config.yaml'
    
    def _determine_secrets_file_path(self, config_file: Path, scope: str) -> Path:
        """シークレットファイルパスを決定"""
        # 設定ファイルと同じディレクトリに配置
        return config_file.parent / 'secrets.yaml'
    
    def _load_config_with_inheritance(self, config_file: Path) -> BunsuiConfig:
        """
        継承をサポートして設定ファイルを読み込む
        
        Args:
            config_file: 設定ファイルのパス
            
        Returns:
            読み込まれた設定
        """
        import yaml
        import json
        from copy import deepcopy
        
        # 循環参照チェック用
        loaded_files = set()
        
        def load_with_extends(file_path: Path, visited: set) -> dict:
            """extendsを処理しながら設定を読み込む"""
            abs_path = file_path.resolve()
            
            if abs_path in visited:
                raise ConfigurationError(f"Circular reference detected in configuration files: {abs_path}")
            
            visited.add(abs_path)
            
            if not file_path.exists():
                raise ConfigurationError(f"Configuration file not found: {file_path}")
            
            # ファイルを読み込み
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix in ['.yaml', '.yml']:
                    data = yaml.safe_load(f) or {}
                elif file_path.suffix == '.json':
                    data = json.load(f)
                else:
                    raise ConfigurationError(f"Unsupported configuration file format: {file_path.suffix}")
            
            # プロジェクト設定内のextendsをチェック
            extends_path = None
            if 'project' in data and isinstance(data['project'], dict) and 'extends' in data['project']:
                extends_path = data['project']['extends']
            elif 'extends' in data:  # 古い形式もサポート
                extends_path = data['extends']
            
            if extends_path:
                # 継承元ファイルパスを解決
                if not Path(extends_path).is_absolute():
                    # 現在の設定ファイルからの相対パス
                    extends_file = file_path.parent / extends_path
                else:
                    extends_file = Path(extends_path)
                
                # 継承元を再帰的に読み込み
                base_data = load_with_extends(extends_file, visited.copy())
                
                # 設定をマージ（現在の設定が優先）
                merged_data = self._deep_merge_config(base_data, data)
                
                # extendsキーを削除（設定モデルには不要）
                if 'project' in merged_data and isinstance(merged_data['project'], dict):
                    merged_data['project'].pop('extends', None)
                merged_data.pop('extends', None)
                
                return merged_data
            else:
                return data
        
        # 継承を処理して設定データを取得
        config_data = load_with_extends(config_file, set())
        
        # BunsuiConfigインスタンスを作成
        config = BunsuiConfig(**config_data)
        config.set_config_file_path(config_file)
        
        return config
    
    def _deep_merge_config(self, base: dict, override: dict) -> dict:
        """
        設定を深くマージする
        
        Args:
            base: ベース設定
            override: オーバーライド設定
            
        Returns:
            マージされた設定
        """
        from copy import deepcopy
        
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 辞書の場合は再帰的にマージ
                result[key] = self._deep_merge_config(result[key], value)
            else:
                # その他の場合は上書き
                result[key] = deepcopy(value)
        
        return result
    
    def create_base_config_template(self, template_path: Path, template_type: str = 'standard') -> None:
        """
        ベース設定テンプレートを作成
        
        Args:
            template_path: テンプレートファイルのパス
            template_type: テンプレートタイプ ('minimal', 'standard', 'advanced')
        """
        templates = {
            'minimal': {
                'project': {
                    'name': 'base-template',
                    'description': 'Minimal base configuration template',
                    'version': '1.0.0'
                },
                'environment': 'development',
                'aws': {
                    'region': 'us-east-1',
                    'timeout': 30,
                    'max_retries': 3
                }
            },
            'standard': {
                'project': {
                    'name': 'base-template',
                    'description': 'Standard base configuration template',
                    'version': '1.0.0'
                },
                'environment': 'development',
                'debug': False,
                'aws': {
                    'region': 'us-east-1',
                    'timeout': 30,
                    'max_retries': 3,
                    'retry_delay': 1
                },
                'pipeline': {
                    'default_timeout': 3600,
                    'max_concurrent_jobs': 5,
                    'enable_checkpoints': True,
                    'retry_failed_jobs': True
                },
                'logging': {
                    'level': 'INFO',
                    'log_to_file': True,
                    'enable_cloudwatch': False
                }
            },
            'advanced': {
                'project': {
                    'name': 'base-template',
                    'description': 'Advanced base configuration template',
                    'version': '1.0.0'
                },
                'environment': 'development',
                'debug': False,
                'aws': {
                    'region': 'us-east-1',
                    'timeout': 30,
                    'max_retries': 3,
                    'retry_delay': 1
                },
                'pipeline': {
                    'default_timeout': 3600,
                    'max_concurrent_jobs': 10,
                    'enable_checkpoints': True,
                    'checkpoint_interval': 300,
                    'retry_failed_jobs': True,
                    'max_job_retries': 3,
                    'exponential_backoff': True,
                    'enable_metrics': True
                },
                'logging': {
                    'level': 'INFO',
                    'log_to_file': True,
                    'log_file_rotation': 'midnight',
                    'log_file_backup_count': 7,
                    'enable_cloudwatch': True
                },
                'security': {
                    'encrypt_at_rest': True,
                    'encrypt_in_transit': True
                }
            }
        }
        
        template_data = templates.get(template_type, templates['standard'])
        
        # テンプレートファイルを保存
        template_path.parent.mkdir(parents=True, exist_ok=True)
        
        import yaml
        with open(template_path, 'w', encoding='utf-8') as f:
            yaml.dump(template_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    def save_config(self, config_file: Optional[Path] = None, scope: str = 'auto') -> None:
        """
        Save current configuration to file.
        
        Args:
            config_file: Optional configuration file path
            scope: Configuration scope ('local', 'project', 'global', 'auto')
        """
        if self._config is None:
            raise ConfigurationError("No configuration loaded")
        
        if config_file:
            # 明示的にファイルパスが指定された場合
            target_file = config_file
        elif scope == 'local':
            # ローカル（現在ディレクトリ）
            target_file = Path.cwd() / '.bunsui' / 'config.yaml'
        elif scope == 'project':
            # プロジェクト
            project_root = find_project_root()
            if project_root:
                target_file = project_root / '.bunsui' / 'config.yaml'
            else:
                target_file = Path.cwd() / '.bunsui' / 'config.yaml'
        elif scope == 'global':
            # グローバル（ホームディレクトリ）
            target_file = Path.home() / '.bunsui' / 'config' / 'config.yaml'
        else:  # auto
            # 現在読み込まれているファイルまたはデフォルト
            if self._loaded_config_file:
                target_file = self._loaded_config_file
            else:
                # デフォルトはプロジェクト設定
                project_root = find_project_root()
                if project_root:
                    target_file = project_root / '.bunsui' / 'config.yaml'
                else:
                    target_file = Path.cwd() / '.bunsui' / 'config.yaml'
        
        self._config.to_file(target_file)
        self._loaded_config_file = target_file
    
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
        
        data = self._config.model_dump(exclude_unset=True)
        
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
        original_config = self._config.model_dump()
        
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


def get_config_manager(config_file: Optional[Path] = None) -> ConfigManager:
    """
    Get global configuration manager instance.
    
    Args:
        config_file: Optional configuration file path
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        if config_file:
            _config_manager = ConfigManager(config_file)
        else:
            # 自動検索モードで初期化
            _config_manager = ConfigManager()
    return _config_manager


def set_config_manager(manager: ConfigManager) -> None:
    """Set global configuration manager instance."""
    global _config_manager
    _config_manager = manager 


def get_config_info() -> Dict[str, Any]:
    """
    現在の設定情報を取得
    
    Returns:
        設定情報の辞書
    """
    manager = get_config_manager()
    
    # 設定を確実に読み込む
    manager.config
    
    return {
        'loaded_config_file': str(manager.loaded_config_file) if manager.loaded_config_file else None,
        'search_paths': [str(path) for path in manager.get_config_search_paths()],
        'existing_config_files': [
            str(path) for path in manager.get_config_search_paths() 
            if path.exists()
        ],
        'project_root': str(find_project_root()) if find_project_root() else None,
        'environment_config': os.environ.get('BUNSUI_CONFIG_FILE'),
    }


def reset_config_manager() -> None:
    """Reset global configuration manager instance."""
    global _config_manager
    _config_manager = None 