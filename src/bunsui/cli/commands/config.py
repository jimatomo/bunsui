"""
Configuration commands for Bunsui CLI.
"""

import click
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Confirm
from rich.text import Text
import json
import yaml
from pathlib import Path

from ...core.config.manager import (
    ConfigManager, 
    get_config_manager, 
    get_config_info,
    find_project_root,
    find_config_files
)
from ...core.exceptions import ConfigurationError

console = Console(force_terminal=True, color_system="auto")


@click.group()
def config():
    """設定管理コマンド"""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
@click.pass_context
def set(ctx: click.Context, key: str, value: str):
    """設定値を設定"""
    try:
        config_manager = get_config_manager()
        
        # 値の型変換
        converted_value = _convert_value(value)
        
        # 設定値を設定
        config_manager.set_value(key, converted_value)
        
        # 設定を保存
        config_manager.save_config()
        
        console.print(f"[green]✓ 設定が正常に更新されました[/green]")
        console.print(f"キー: {key}")
        console.print(f"値: {converted_value}")
        
        # 保存先ファイルを表示
        if config_manager.loaded_config_file:
            console.print(f"保存先: {config_manager.loaded_config_file}")
        
    except ConfigurationError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()





@config.command()
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='出力形式')
@click.option('--check-version', is_flag=True, help='バージョンの整合性をチェック')
@click.pass_context
def list(ctx: click.Context, format: str, check_version: bool):
    """設定を表示"""
    try:
        if check_version:
            _check_config_versions()
            return
            
        _display_all_configs(format)
            
    except Exception as e:
        console.print(f"[red]設定の表示中にエラーが発生しました: {e}[/red]")
        raise click.Abort()


@config.command()
@click.pass_context
def info(ctx: click.Context):
    """設定情報を表示"""
    try:
        config_info = get_config_info()
        
        # パネルで情報を表示
        info_text = []
        
        # 現在読み込まれている設定ファイル
        if config_info['loaded_config_file']:
            info_text.append(f"[green]現在の設定ファイル:[/green] {config_info['loaded_config_file']}")
        else:
            info_text.append("[yellow]設定ファイル: デフォルト設定を使用[/yellow]")
        
        # プロジェクトルート
        if config_info['project_root']:
            info_text.append(f"[blue]プロジェクトルート:[/blue] {config_info['project_root']}")
        
        # 環境変数での設定
        if config_info['environment_config']:
            info_text.append(f"[cyan]環境変数BUNSUI_CONFIG_FILE:[/cyan] {config_info['environment_config']}")
        
        console.print(Panel(
            "\n".join(info_text),
            title="🔧 Bunsui 設定情報",
            border_style="cyan"
        ))

        
        # 検索パスを表示
        table = Table(title="設定ファイル検索パス（優先順位順）", box=box.ROUNDED)
        table.add_column("優先順位", style="cyan", width=8)
        table.add_column("パス", style="white")
        table.add_column("存在", style="bold")
        
        for i, path in enumerate(config_info['search_paths'], 1):
            exists = "✓" if path in config_info['existing_config_files'] else "✗"
            exists_style = "green" if exists == "✓" else "red"
            table.add_row(str(i), path, f"[{exists_style}]{exists}[/{exists_style}]")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]情報取得エラー: {e}[/red]")
        raise click.Abort()








def _repair_config_file(config_file: Path):
    """設定ファイルを修復"""
    import re
    
    # ファイルを読み込み
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Pythonオブジェクトタグを削除
    # !!python/object/apply:bunsui.aws.dynamodb.schemas.TableName を削除
    content = re.sub(r'\? !!python/object/apply:bunsui\.aws\.dynamodb\.schemas\.TableName\s*\n\s*-\s*([^\n]+)\s*\n\s*:\s*([^\n]+)', r'\1: \2', content)
    
    # 複数行のマッピングを単純なキー: 値の形式に変換
    content = re.sub(r'\? !!python/object/apply:[^\n]*\s*\n\s*-\s*([^\n]+)\s*\n\s*:\s*([^\n]+)', r'\1: \2', content)
    
    # 修復された内容を保存
    with open(config_file, 'w') as f:
        f.write(content)


def _convert_value(value: str):
    """文字列値を適切な型に変換"""
    # ブール値
    if value.lower() in ['true', 'false']:
        return value.lower() == 'true'
    
    # 整数
    try:
        return int(value)
    except ValueError:
        pass
    
    # 浮動小数点数
    try:
        return float(value)
    except ValueError:
        pass
    
    # JSON文字列
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # 文字列として返す
    return value


def _display_all_configs(format: str):
    """すべての設定を表示"""
    from pathlib import Path
    import yaml
    import json
    
    # 設定ファイルの検索パス
    config_paths = [
        Path.cwd() / '.bunsui' / 'config.yaml',
        Path.home() / '.bunsui' / 'config' / 'config.yaml',
        Path('/etc/bunsui/config.yaml')
    ]
    
    # 最初に見つかった設定ファイルを使用
    config_file = None
    for path in config_paths:
        if path.exists():
            config_file = path
            break
    
    if config_file:
        # 設定ファイルが存在する場合、ファイルから直接読み込み
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix in ['.yaml', '.yml']:
                    config_data = yaml.safe_load(f) or {}
                else:
                    config_data = json.load(f)
            
            # 設定ファイルのパスを表示
            console.print(f"[dim]📁 設定ファイル: {config_file}[/dim]")
        except Exception as e:
            console.print(f"[red]設定ファイル読み込みエラー: {e}[/red]")
            return
    else:
        # 設定ファイルが存在しない場合、デフォルト設定を使用
        config_data = _get_default_config_dict()
        console.print("[dim]📁 設定ファイル: デフォルト設定を使用[/dim]")
    
    if format == 'table':
        _display_config_table(config_data)
    elif format == 'json':
        console.print(json.dumps(config_data, indent=2, default=str))
    else:  # yaml
        console.print(yaml.dump(config_data, default_flow_style=False))


def _check_config_versions():
    """設定ファイルのバージョン整合性をチェック"""
    from pathlib import Path
    from rich.table import Table
    from rich.console import Console
    
    console = Console(force_terminal=True, color_system="auto")
    
    # サポートされているバージョン
    SUPPORTED_VERSIONS = ["1.0.0"]
    RECOMMENDED_VERSION = "1.0.0"
    
    # 設定ファイルの検索パス
    config_paths = [
        Path.cwd() / '.bunsui' / 'config.yaml',
        Path.home() / '.bunsui' / 'config' / 'config.yaml',
        Path('/etc/bunsui/config.yaml')
    ]
    
    table = Table(title="設定ファイルバージョンチェック", box=box.ROUNDED)
    table.add_column("ファイル", style="white", min_width=30)
    table.add_column("バージョン", style="white", min_width=10)
    table.add_column("状態", style="white", min_width=15)
    table.add_column("推奨", style="white", min_width=10)
    
    found_files = []
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                version = config_data.get('version', '未設定')
                found_files.append((config_path, version))
                
                # バージョンの状態を判定
                if version == '未設定':
                    status = "[red]バージョン未設定[/red]"
                    recommended = RECOMMENDED_VERSION
                elif version in SUPPORTED_VERSIONS:
                    if version == RECOMMENDED_VERSION:
                        status = "[green]✓ 推奨バージョン[/green]"
                    else:
                        status = "[yellow]⚠ サポート済み[/yellow]"
                    recommended = RECOMMENDED_VERSION
                else:
                    status = "[red]✗ 非サポート[/red]"
                    recommended = RECOMMENDED_VERSION
                
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
                    RECOMMENDED_VERSION
                )
    
    if not found_files:
        console.print("[yellow]設定ファイルが見つかりません[/yellow]")
        console.print(f"[dim]推奨バージョン: {RECOMMENDED_VERSION}[/dim]")
        return
    
    console.print(table)
    
    # サマリー情報
    console.print(f"\n[bold]サポートされているバージョン:[/bold] {', '.join(SUPPORTED_VERSIONS)}")
    console.print(f"[bold]推奨バージョン:[/bold] {RECOMMENDED_VERSION}")
    
    # 推奨バージョンでないファイルがある場合の警告
    outdated_files = [f for f, v in found_files if v != RECOMMENDED_VERSION and v != '未設定']
    if outdated_files:
        console.print(f"\n[yellow]⚠ {len(outdated_files)}個のファイルが推奨バージョンと異なります[/yellow]")
        console.print("[dim]バージョンを更新するには 'bunsui config migrate' を使用してください[/dim]")


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


def _display_config_table(config_data: dict):
    """設定をテーブル形式で表示"""
    # 詳細表示: すべての設定をフラット化して表示
    _display_detailed_config_table(config_data)
    



def _flatten_dict(d, parent_key='', sep='.'):
    """ネストした辞書をフラット化"""
    items = []
    for k, v in d.items():
        # 内部フィールドを除外
        if k.startswith('_'):
            continue
            
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        # suffixとprefixの設定項目を除外
        if any(exclude_key in new_key.lower() for exclude_key in ['suffix', 'prefix']):
            continue
            
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _display_detailed_config_table(config_data: dict):
    """詳細な設定をフラット化して表示"""
    
    # デフォルト設定を取得
    default_config_data = _get_default_config_dict()
    default_flat = _flatten_dict(default_config_data)
    
    flat_config = _flatten_dict(config_data)
    
    def get_nested_value(data: dict, key_path: str):
        """ネストした辞書から値を取得"""
        keys = key_path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def get_default_value_for_key(key_path: str, default_config_data: dict):
        """設定項目の名前をマッピングしてデフォルト値を取得"""
        # 設定項目名のマッピング
        key_mapping = {
            'pipeline.default_timeout': 'pipeline.default_timeout',
            'pipeline.max_concurrent_jobs': 'pipeline.max_concurrent_jobs',
            'logging.level': 'logging.level',
            'data_dir': 'data_dir',
            'cache_dir': 'cache_dir',
            'aws.region': 'aws.region',
            'aws.profile': 'aws.profile',
            'aws.dynamodb_table_prefix': 'aws.dynamodb_table_prefix',
            'aws.s3_bucket_prefix': 'aws.s3_bucket_prefix',
            'mode': 'mode',
            'version': 'version',
            'created_at': 'created_at'
        }
        
        # マッピングされたキーを使用してデフォルト値を取得
        mapped_key = key_mapping.get(key_path, key_path)
        return get_nested_value(default_config_data, mapped_key)
    
    def is_value_modified(key_path: str, current_value, default_value) -> bool:
        """値がデフォルトから変更されているかチェック"""
        # パス系の設定は特別扱い（絶対パス展開されるため）
        if any(path_key in key_path for path_key in ['data_dir', 'config_dir', 'cache_dir', 'directories.data', 'directories.cache', 'directories.logs']):
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
        
        # その他は値で直接比較
        return current_value != default_value
    
    table = Table(title="Bunsui 設定（詳細）", box=box.ROUNDED)
    table.add_column("カテゴリ", style="white", min_width=12)
    table.add_column("設定項目", style="white", min_width=40)
    table.add_column("現在の値", style="white", min_width=30)
    table.add_column("デフォルト値", min_width=30)
    
    modified_count = 0
    total_count = 0
    
    # カテゴリ別に設定を整理
    categorized_config = {}
    for key, value in sorted(flat_config.items()):
        # すべての設定項目を表示（空の値も含む）
        # 内部的な管理用の設定のみ除外
        if key.startswith('_'):
            continue
        
        # カテゴリを決定
        if key.startswith('aws.'):
            category = 'AWS'
        elif key.startswith('pipeline.'):
            category = 'パイプライン'
        elif key.startswith('logging.'):
            category = 'ログ'
        elif key.startswith('security.'):
            category = 'セキュリティ'
        elif key.startswith('directories.'):
            category = 'ディレクトリ'
        elif key in ['mode', 'version', 'created_at', 'environment', 'debug']:
            category = '基本設定'
        else:
            category = 'その他'
        
        if category not in categorized_config:
            categorized_config[category] = []
        categorized_config[category].append((key, value))
    
    # カテゴリ別に表示
    for category, items in categorized_config.items():
        first_in_category = True
        for key, value in items:
            total_count += 1
            default_value = get_default_value_for_key(key, default_config_data)
            
            # 機密情報を隠す
            if any(secret in key.lower() for secret in ['password', 'secret', 'key', 'token']):
                display_value = "****"
                value_style = "red"
            else:
                # 空の値の特別処理
                if value is None:
                    display_value = "未設定"
                    value_style = "yellow"
                elif value == "":
                    display_value = "空文字列"
                    value_style = "yellow"
                elif hasattr(value, '__len__') and len(value) == 0:
                    display_value = "空"
                    value_style = "yellow"
                else:
                    display_value = str(value)
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."
                
                # AWSリソースの設定項目は特別な色分け
                if key.startswith('aws.'):
                    # aws.profileとaws.regionは基本設定として扱う
                    if key in ['aws.profile', 'aws.region']:
                        if is_value_modified(key, value, default_value):
                            # デフォルト値と異なる場合は黄色
                            value_style = "yellow"
                            modified_count += 1
                        else:
                            # デフォルト値と同じ場合は緑色
                            value_style = "green"
                    else:
                        # その他のAWSリソース関連の設定は常にblue色で表示
                        value_style = "blue"
                        # ただし、デフォルト値と異なる場合はカウント
                        if is_value_modified(key, value, default_value):
                            modified_count += 1
                else:
                    # その他の設定項目
                    if is_value_modified(key, value, default_value):
                        # デフォルト値と異なる場合は黄色
                        value_style = "yellow"
                        modified_count += 1
                    else:
                        # デフォルト値と同じ場合は緑色
                        value_style = "green"
            
            # 設定項目名を完全なドット区切りキーで表示
            full_key = key
            
            # デフォルト値の表示
            default_display = str(default_value) if default_value is not None else "未設定"
            if len(default_display) > 50:
                default_display = default_display[:47] + "..."
            
            category_display = category if first_in_category else ""
            
            # デバッグ用: 色分けの確認
            # console.print(f"[dim]DEBUG: {key} -> style={value_style}[/dim]")
            
            table.add_row(
                category_display,
                full_key,
                Text(display_value, style=value_style),
                Text(default_display, style="dim")
            )
            first_in_category = False
    
    console.print(table)
    
    # 変更統計を表示
    if total_count > 0:
        percentage = (modified_count / total_count) * 100
        console.print(f"\n[dim]📊 設定統計: {modified_count}/{total_count} 項目がデフォルトから変更されています ({percentage:.1f}%)[/dim]")
    
    # 凡例を表示
    console.print("\n[dim]🎨 凡例:[/dim]")
    console.print("  [green]■[/green] 標準値  [yellow]■[/yellow] カスタマイズ済み  [red]■[/red] 機密情報  [cyan]■[/cyan] AWSリソース")


def _get_default_config_dict() -> dict:
    """デフォルト設定の辞書を取得"""
    try:
        # デフォルトのBunsuiConfigインスタンスを作成
        from ...core.config.models import BunsuiConfig
        default_config = BunsuiConfig()
        config_dict = default_config.model_dump(exclude={'config_file_path'})
        
        # デバッグ用: デフォルト設定の内容を確認
        # console.print(f"[dim]DEBUG: デフォルト設定 = {config_dict}[/dim]")
        
        return config_dict
    except Exception as e:
        # フォールバック: 基本的なデフォルト値を返す
        # console.print(f"[dim]DEBUG: デフォルト設定取得エラー: {e}[/dim]")
        return {
            'mode': 'development',
            'version': '1.0.0',
            'created_at': None,
            'aws': {
                'region': 'us-east-1',
                'profile': None,
                'dynamodb_table_prefix': 'bunsui',
                's3_bucket_prefix': 'bunsui'
            },
            'pipeline': {
                'default_timeout': 3600,
                'max_concurrent_jobs': 10
            },
            'logging': {
                'level': 'INFO'
            },
            'data_dir': str(Path.home() / '.bunsui' / 'data'),
            'cache_dir': str(Path.home() / '.bunsui' / 'cache')
        }


 


 