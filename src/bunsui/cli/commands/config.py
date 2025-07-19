"""
Configuration commands for Bunsui CLI.
"""

import click
from typing import Optional, List, Dict, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
import json
import yaml
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from ...core.config.manager import (
    get_config_manager, 
    get_config_info,
    find_config_files,
)
from ...core.exceptions import ConfigurationError

console = Console(force_terminal=True, color_system="auto")


class ConfigCategory(Enum):
    """設定カテゴリの列挙型"""
    AWS = "AWS"
    PIPELINE = "パイプライン"
    LOGGING = "ログ"
    SECURITY = "セキュリティ"
    DIRECTORIES = "ディレクトリ"
    BASIC = "基本設定"
    OTHER = "その他"


class ValueStyle(Enum):
    """値の表示スタイルの列挙型"""
    DEFAULT = "green"
    MODIFIED = "yellow"
    SECRET = "red"
    AWS_RESOURCE = "blue"


@dataclass
class ConfigItem:
    """設定項目のデータクラス"""
    key: str
    value: Any
    category: ConfigCategory
    default_value: Any
    is_modified: bool
    is_secret: bool
    display_value: str
    style: ValueStyle


class ConfigDisplayFormatter:
    """設定表示のフォーマッター"""
    
    # 機密情報のキーワード
    SECRET_KEYWORDS = ['password', 'secret', 'key', 'token']
    
    # パス系設定のキーワード
    PATH_KEYWORDS = ['data_dir', 'config_dir', 'cache_dir', 'directories.data', 'directories.cache', 'directories.logs']
    
    # AWS基本設定（リソースとして色分けしない）
    AWS_BASIC_KEYS = ['aws.profile', 'aws.region']
    
    # 除外するキーワード
    EXCLUDE_KEYWORDS = ['suffix', 'prefix']
    
    @staticmethod
    def format_value(value: Any, max_length: int = 50) -> str:
        """値を表示用にフォーマット"""
        if value is None:
            return "未設定"
        elif value == "":
            return "空文字列"
        # elif hasattr(value, '__len__') and len(value) == 0:
        #     return "空"
        else:
            display_value = str(value)
            if len(display_value) > max_length:
                return display_value[:max_length-3] + "..."
            return display_value
    
    @staticmethod
    def is_secret_key(key: str) -> bool:
        """機密情報のキーかどうかを判定"""
        return any(secret in key.lower() for secret in ConfigDisplayFormatter.SECRET_KEYWORDS)
    
    @staticmethod
    def get_category(key: str) -> ConfigCategory:
        """キーからカテゴリを決定"""
        if key.startswith('aws.'):
            return ConfigCategory.AWS
        elif key.startswith('pipeline.'):
            return ConfigCategory.PIPELINE
        elif key.startswith('logging.'):
            return ConfigCategory.LOGGING
        elif key.startswith('security.'):
            return ConfigCategory.SECURITY
        elif key.startswith('directories.'):
            return ConfigCategory.DIRECTORIES
        elif key.startswith('defaults.'):
            return ConfigCategory.BASIC
        elif key in ['mode', 'version', 'created_at', 'environment', 'debug']:
            return ConfigCategory.BASIC
        else:
            return ConfigCategory.OTHER
    
    @staticmethod
    def get_value_style(key: str, is_modified: bool, is_secret: bool) -> ValueStyle:
        """値の表示スタイルを決定"""
        if is_secret:
            return ValueStyle.SECRET
        
        if key.startswith('aws.'):
            if key in ConfigDisplayFormatter.AWS_BASIC_KEYS:
                return ValueStyle.MODIFIED if is_modified else ValueStyle.DEFAULT
            else:
                return ValueStyle.AWS_RESOURCE
        
        if is_modified:
            return ValueStyle.MODIFIED
        else:
            return ValueStyle.DEFAULT


class ConfigDataLoader:
    """設定データの読み込みを担当"""
    
    @staticmethod
    def get_config_paths() -> List[Path]:
        """設定ファイルの検索パスを取得"""
        return find_config_files()
    
    @staticmethod
    def load_config_data() -> Tuple[Dict[str, Any], Optional[Path]]:
        """設定データを読み込み"""
        config_paths = ConfigDataLoader.get_config_paths()
        
        for config_file in config_paths:
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        if config_file.suffix in ['.yaml', '.yml']:
                            config_data = yaml.safe_load(f) or {}
                        else:
                            config_data = json.load(f)
                    return config_data, config_file
                except Exception as e:
                    console.print(f"[red]設定ファイル読み込みエラー: {e}[/red]")
                    continue
        
        # 設定ファイルが見つからない場合、デフォルト設定を使用
        return ConfigDataLoader.get_default_config_dict(), None
    
    @staticmethod
    def get_default_config_dict() -> Dict[str, Any]:
        """デフォルト設定の辞書を取得"""
        # 古い形式の設定ファイルとの互換性のため、実際のデフォルト値を定義
        return {
            # 基本設定
            'mode': 'development',
            'version': '1.0.0',
            'created_at': None,
            'environment': 'development',
            'debug': False,
            
            # AWS設定
            'aws': {
                'region': 'us-east-1',
                'profile': None,
                'dynamodb_table_prefix': 'bunsui',
                's3_bucket_prefix': 'bunsui',
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 1,
                'created_resources': None
            },
            
            # パイプライン設定
            'pipeline': {
                'default_timeout': 3600,
                'max_concurrent_jobs': 10,
                'enable_checkpoints': True,
                'checkpoint_interval': 300,
                'retry_failed_jobs': True,
                'max_job_retries': 3,
                'exponential_backoff': True,
                'enable_metrics': True,
                'metrics_namespace': 'Bunsui/Pipeline'
            },
            
            # ログ設定
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'log_to_file': False,
                'log_file_path': None,
                'log_file_rotation': 'midnight',
                'log_file_max_bytes': 10485760,
                'log_file_backup_count': 7,
                'enable_cloudwatch': False,
                'cloudwatch_log_group': '/aws/bunsui',
                'cloudwatch_log_stream_prefix': 'pipeline'
            },
            
            # セキュリティ設定
            'security': {
                'encrypt_at_rest': True,
                'encrypt_in_transit': True,
                'kms_key_id': None,
                'assume_role_arn': None,
                'external_id': None,
                'api_key_required': False,
                'api_key_header': 'X-API-Key'
            },
            
            # ディレクトリ設定
            'directories': {
                'data': str(Path.home() / '.bunsui' / 'data'),
                'cache': str(Path.home() / '.bunsui' / 'cache'),
                'logs': str(Path.home() / '.bunsui' / 'logs')
            },
            
            # デフォルト設定（古い形式の互換性）
            'defaults': {
                'timeout_seconds': 3600,
                'max_concurrent_jobs': 10,
                'output_format': 'table'
            },
            
            # パス設定（新しい形式）
            'data_dir': str(Path.home() / '.bunsui' / 'data'),
            'config_dir': str(Path.home() / '.bunsui' / 'config'),
            'cache_dir': str(Path.home() / '.bunsui' / 'cache')
        }


class ConfigAnalyzer:
    """設定データの分析を担当"""
    
    @staticmethod
    def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """ネストした辞書をフラット化"""
        items = []
        for k, v in d.items():
            # 内部フィールドを除外
            if k.startswith('_'):
                continue
                
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            # suffixとprefixの設定項目を除外
            if any(exclude_key in new_key.lower() for exclude_key in ConfigDisplayFormatter.EXCLUDE_KEYWORDS):
                continue
                
            if isinstance(v, dict):
                items.extend(ConfigAnalyzer.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    @staticmethod
    def get_nested_value(data: Dict[str, Any], key_path: str) -> Any:
        """ネストした辞書から値を取得"""
        keys = key_path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    @staticmethod
    def is_value_modified(key_path: str, current_value: Any, default_value: Any) -> bool:
        """値がデフォルトから変更されているかチェック"""
        # パス系の設定は特別扱い（絶対パス展開されるため）
        if any(path_key in key_path for path_key in ConfigDisplayFormatter.PATH_KEYWORDS):
            # パス系は名前で判定
            if hasattr(current_value, 'name'):
                current_name = current_value.name
            else:
                current_name = str(current_value).split('/')[-1] if current_value else ''
                
            if hasattr(default_value, 'name'):
                default_name = default_value.name
            else:
                default_name = str(default_value).split('/')[-1] if default_value else ''
                
            return current_name != default_name
        
        # デフォルト値がNoneの場合は、現在の値が設定されているかチェック
        if default_value is None:
            return current_value is not None and current_value != ""
        
        # その他は値で直接比較
        return current_value != default_value


class ConfigTableRenderer:
    """設定テーブルの描画を担当"""
    
    @staticmethod
    def create_config_table() -> Table:
        """設定テーブルを作成"""
        table = Table(title="Bunsui Configs", box=box.ROUNDED)
        table.add_column("カテゴリ", style="white", min_width=12)
        table.add_column("設定項目", style="white", min_width=40)
        table.add_column("現在の値", style="white", min_width=30)
        table.add_column("デフォルト値", min_width=30)
        return table
    
    @staticmethod
    def render_config_items(config_items: List[ConfigItem]) -> Tuple[Table, int, int]:
        """設定項目をテーブルに描画"""
        table = ConfigTableRenderer.create_config_table()
        modified_count = 0
        total_count = 0
        
        # カテゴリ別にグループ化
        categorized_items = {}
        for item in config_items:
            if item.category not in categorized_items:
                categorized_items[item.category] = []
            categorized_items[item.category].append(item)
        
        # カテゴリ別に表示
        for category, items in categorized_items.items():
            first_in_category = True
            for item in items:
                total_count += 1
                if item.is_modified:
                    modified_count += 1
                
                category_display = category.value if first_in_category else ""
                
                table.add_row(
                    category_display,
                    item.key,
                    Text(item.display_value, style=item.style.value),
                    Text(ConfigDisplayFormatter.format_value(item.default_value), style="dim")
                )
                first_in_category = False
        
        return table, modified_count, total_count
    
    @staticmethod
    def render_legend():
        """凡例を表示"""
        console.print("\n[dim]🎨 凡例:[/dim]")
        console.print("  [green]■[/green] 標準値  [yellow]■[/yellow] カスタマイズ済み  [red]■[/red] 機密情報  [cyan]■[/cyan] AWSリソース")
    
    @staticmethod
    def render_statistics(modified_count: int, total_count: int):
        """統計情報を表示"""
        if total_count > 0:
            percentage = (modified_count / total_count) * 100
            console.print(f"\n[dim]📊 設定統計: {modified_count}/{total_count} 項目がデフォルトから変更されています ({percentage:.1f}%)[/dim]")


class ConfigVersionChecker:
    """設定ファイルのバージョンチェックを担当"""
    
    SUPPORTED_VERSIONS = ["1.0.0"]
    RECOMMENDED_VERSION = "1.0.0"
    
    @staticmethod
    def check_versions():
        """設定ファイルのバージョン整合性をチェック"""
        config_paths = ConfigDataLoader.get_config_paths()
        
        table = Table(title="設定ファイルバージョンチェック", box=box.ROUNDED)
        table.add_column("ファイル", style="white", min_width=30)
        table.add_column("バージョン", style="white", min_width=10)
        table.add_column("状態", style="white", min_width=15)
        table.add_column("推奨", style="white", min_width=10)
        
        found_files = []
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                    
                    version = config_data.get('version', '未設定')
                    found_files.append((config_path, version))
                    
                    status, recommended = ConfigVersionChecker._get_version_status(version)
                    
                    table.add_row(
                        str(config_path),
                        version,
                        status,
                        recommended
                    )
                    
                except Exception as e:
                    table.add_row(
                        str(config_path),
                        "エラー",
                        f"[red]読み込み失敗: {e}[/red]",
                        ConfigVersionChecker.RECOMMENDED_VERSION
                    )
        
        if not found_files:
            console.print("[yellow]設定ファイルが見つかりません[/yellow]")
            console.print(f"[dim]推奨バージョン: {ConfigVersionChecker.RECOMMENDED_VERSION}[/dim]")
            return
        
        console.print(table)
        ConfigVersionChecker._render_version_summary(found_files)
    
    @staticmethod
    def _get_version_status(version: str) -> Tuple[str, str]:
        """バージョンの状態を判定"""
        if version == '未設定':
            return "[red]バージョン未設定[/red]", ConfigVersionChecker.RECOMMENDED_VERSION
        elif version in ConfigVersionChecker.SUPPORTED_VERSIONS:
            if version == ConfigVersionChecker.RECOMMENDED_VERSION:
                return "[green]✓ 推奨バージョン[/green]", ConfigVersionChecker.RECOMMENDED_VERSION
            else:
                return "[yellow]⚠ サポート済み[/yellow]", ConfigVersionChecker.RECOMMENDED_VERSION
        else:
            return "[red]✗ 非サポート[/red]", ConfigVersionChecker.RECOMMENDED_VERSION
    
    @staticmethod
    def _render_version_summary(found_files: List[Tuple[Path, str]]):
        """バージョンサマリーを表示"""
        console.print(f"\n[bold]サポートされているバージョン:[/bold] {', '.join(ConfigVersionChecker.SUPPORTED_VERSIONS)}")
        console.print(f"[bold]推奨バージョン:[/bold] {ConfigVersionChecker.RECOMMENDED_VERSION}")
        
        # 推奨バージョンでないファイルがある場合の警告
        outdated_files = [f for f, v in found_files if v != ConfigVersionChecker.RECOMMENDED_VERSION and v != '未設定']
        if outdated_files:
            console.print(f"\n[yellow]⚠ {len(outdated_files)}個のファイルが推奨バージョンと異なります[/yellow]")
            console.print("[dim]バージョンを更新するには 'bunsui config migrate' を使用してください[/dim]")


class ConfigCommandHandler:
    """設定コマンドのハンドラー"""
    
    @staticmethod
    def display_configs(format: str):
        """設定を表示"""
        try:
            config_data, config_file = ConfigDataLoader.load_config_data()
            
            if config_file:
                console.print(f"[dim]📁 設定ファイル: {config_file}[/dim]")
            else:
                console.print("[dim]📁 設定ファイル: デフォルト設定を使用[/dim]")
            
            if format == 'table':
                ConfigCommandHandler._display_config_table(config_data)
            elif format == 'json':
                console.print(json.dumps(config_data, indent=2, default=str, ensure_ascii=False))
            else:  # yaml
                console.print(yaml.dump(config_data, default_flow_style=False, allow_unicode=True))
                
        except Exception as e:
            console.print(f"[red]設定の表示中にエラーが発生しました: {e}[/red]")
            raise click.Abort()
    
    @staticmethod
    def display_info():
        """設定情報を表示"""
        try:
            config_info = get_config_info()
            ConfigCommandHandler._render_info_panel(config_info)
            ConfigCommandHandler._render_search_paths_table(config_info)
        except Exception as e:
            console.print(f"[red]情報取得エラー: {e}[/red]")
            raise click.Abort()
    
    @staticmethod
    def _display_config_table(config_data: Dict[str, Any]):
        """設定をテーブル形式で表示"""
        default_config_data = ConfigDataLoader.get_default_config_dict()
        flat_config = ConfigAnalyzer.flatten_dict(config_data)
        
        config_items = []
        for key, value in sorted(flat_config.items()):
            if key.startswith('_'):
                continue
            
            default_value = ConfigAnalyzer.get_nested_value(default_config_data, key)
            is_modified = ConfigAnalyzer.is_value_modified(key, value, default_value)
            is_secret = ConfigDisplayFormatter.is_secret_key(key)
            category = ConfigDisplayFormatter.get_category(key)
            
            if is_secret:
                display_value = "****"
            else:
                display_value = ConfigDisplayFormatter.format_value(value)
            
            style = ConfigDisplayFormatter.get_value_style(key, is_modified, is_secret)
            
            config_items.append(ConfigItem(
                key=key,
                value=value,
                category=category,
                default_value=default_value,
                is_modified=is_modified,
                is_secret=is_secret,
                display_value=display_value,
                style=style
            ))
        
        table, modified_count, total_count = ConfigTableRenderer.render_config_items(config_items)
        console.print(table)
        ConfigTableRenderer.render_statistics(modified_count, total_count)
        ConfigTableRenderer.render_legend()
    
    @staticmethod
    def _render_info_panel(config_info: Dict[str, Any]):
        """情報パネルを表示"""
        info_text = []
        
        if config_info['loaded_config_file']:
            info_text.append(f"[green]現在の設定ファイル:[/green] {config_info['loaded_config_file']}")
        else:
            info_text.append("[yellow]設定ファイル: デフォルト設定を使用[/yellow]")
        
        if config_info['project_root']:
            info_text.append(f"[blue]プロジェクトルート:[/blue] {config_info['project_root']}")
        
        if config_info['environment_config']:
            info_text.append(f"[cyan]環境変数BUNSUI_CONFIG_FILE:[/cyan] {config_info['environment_config']}")
        
        console.print(Panel(
            "\n".join(info_text),
            title="🔧 Bunsui 設定情報",
            border_style="cyan"
        ))
    
    @staticmethod
    def _render_search_paths_table(config_info: Dict[str, Any]):
        """検索パステーブルを表示"""
        table = Table(title="設定ファイル検索パス（優先順位順）", box=box.ROUNDED)
        table.add_column("優先順位", style="cyan", width=8)
        table.add_column("パス", style="white")
        table.add_column("存在", style="bold")
        
        for i, path in enumerate(config_info['search_paths'], 1):
            exists = "✓" if path in config_info['existing_config_files'] else "✗"
            exists_style = "green" if exists == "✓" else "red"
            table.add_row(str(i), path, f"[{exists_style}]{exists}[/{exists_style}]")
        
        console.print(table)


# Click コマンド定義
@click.group()
def config():
    """設定管理コマンド"""
    pass


@config.command()
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='出力形式')
@click.option('--check-version', is_flag=True, help='バージョンの整合性をチェック')
@click.pass_context
def list(ctx: click.Context, format: str, check_version: bool):
    """設定を表示"""
    if check_version:
        ConfigVersionChecker.check_versions()
    else:
        ConfigCommandHandler.display_configs(format)


@config.command()
@click.pass_context
def info(ctx: click.Context):
    """設定情報を表示"""
    ConfigCommandHandler.display_info()


# 後方互換性のための関数（削除予定）
def _repair_config_file(config_file: Path):
    """設定ファイルを修復（後方互換性のため残存）"""
    import re
    
    with open(config_file, 'r') as f:
        content = f.read()
    
    content = re.sub(r'\? !!python/object/apply:bunsui\.aws\.dynamodb\.schemas\.TableName\s*\n\s*-\s*([^\n]+)\s*\n\s*:\s*([^\n]+)', r'\1: \2', content)
    content = re.sub(r'\? !!python/object/apply:[^\n]*\s*\n\s*-\s*([^\n]+)\s*\n\s*:\s*([^\n]+)', r'\1: \2', content)
    
    with open(config_file, 'w') as f:
        f.write(content)


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """プロジェクトルートディレクトリを見つける（後方互換性のため残存）"""
    current = start_path or Path.cwd()
    
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists():
            return parent
        if (parent / 'pyproject.toml').exists():
            return parent
        if (parent / 'setup.py').exists():
            return parent
        if (parent / 'package.json').exists():
            return parent
        if (parent / '.bunsui').exists():
            return parent
    
    return None


 