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

console = Console()


@click.group()
def config():
    """設定管理コマンド"""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
@click.option('--scope', type=click.Choice(['local', 'project', 'global', 'auto']), 
              default='auto', help='設定のスコープ')
@click.pass_context
def set(ctx: click.Context, key: str, value: str, scope: str):
    """設定値を設定"""
    try:
        config_manager = get_config_manager()
        
        # 値の型変換
        converted_value = _convert_value(value)
        
        # 設定値を設定
        config_manager.set_value(key, converted_value)
        
        # 設定を保存
        config_manager.save_config(scope=scope)
        
        console.print(f"[green]✓ 設定が正常に更新されました[/green]")
        console.print(f"キー: {key}")
        console.print(f"値: {converted_value}")
        console.print(f"スコープ: {scope}")
        
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
@click.argument('key')
@click.pass_context
def get(ctx: click.Context, key: str):
    """設定値を取得"""
    try:
        config_manager = get_config_manager()
        value = config_manager.get_value(key)
        
        if value is None:
            console.print(f"[yellow]設定キー '{key}' が見つかりません[/yellow]")
        else:
            console.print(f"[bold cyan]{key}[/bold cyan]: {value}")
            
    except ConfigurationError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('key')
@click.pass_context
def delete(ctx: click.Context, key: str):
    """設定値を削除"""
    try:
        config_manager = get_config_manager()
        config_manager.delete_value(key)
        config_manager.save_config()
        
        console.print(f"[green]✓ 設定キー '{key}' を削除しました[/green]")
        
    except ConfigurationError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()


@config.command()
@click.option('--scope', type=click.Choice(['all', 'local', 'project', 'global']), 
              default='all', help='表示する設定のスコープ')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='出力形式')
@click.option('--verbose', '-v', is_flag=True, help='詳細表示（すべての設定項目を表示）')
@click.option('--show-defaults', is_flag=True, help='デフォルト値も表示')
@click.pass_context
def list(ctx: click.Context, scope: str, format: str, verbose: bool, show_defaults: bool):
    """設定一覧を表示"""
    try:
        if scope == 'all':
            # すべての設定情報を表示
            _display_all_configs(format, verbose, show_defaults)
        else:
            # 特定のスコープの設定を表示
            _display_scope_config(scope, format, verbose, show_defaults)
            
    except ConfigurationError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]設定エラー: {e}[/red]")
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


@config.command()
@click.argument('file_path')
@click.option('--format', type=click.Choice(['yaml', 'json']), 
              help='エクスポート形式（自動検出されない場合）')
@click.option('--scope', type=click.Choice(['local', 'project', 'global', 'current']), 
              default='current', help='エクスポートする設定のスコープ')
@click.pass_context
def export(ctx: click.Context, file_path: str, format: Optional[str], scope: str):
    """設定をエクスポート"""
    try:
        config_manager = get_config_manager()
        
        output_file = Path(file_path)
        
        # フォーマットを自動検出
        if not format:
            if output_file.suffix.lower() in ['.yaml', '.yml']:
                format = 'yaml'
            elif output_file.suffix.lower() == '.json':
                format = 'json'
            else:
                format = 'yaml'  # デフォルト
        
        # 設定をエクスポート
        config_str = config_manager.export_config(format)
        
        # ファイルに書き込み
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(config_str)
        
        console.print(f"[green]✓ 設定をエクスポートしました[/green]")
        console.print(f"ファイル: {output_file}")
        console.print(f"形式: {format}")
        console.print(f"スコープ: {scope}")
        
    except ConfigurationError as e:
        console.print(f"[red]設定エラー: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]エクスポートエラー: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('archive_path')
@click.option('--include-secrets', is_flag=True, 
              help='シークレットファイルも含める（注意：機密情報が含まれます）')
@click.option('--include-samples', is_flag=True, default=True,
              help='サンプルファイルも含める')
@click.option('--scope', type=click.Choice(['local', 'project', 'global', 'all']), 
              default='project', help='エクスポートするスコープ')
@click.pass_context
def backup(ctx: click.Context, archive_path: str, include_secrets: bool, 
           include_samples: bool, scope: str):
    """プロジェクト設定の完全バックアップを作成"""
    try:
        import tarfile
        import tempfile
        import shutil
        from datetime import datetime
        
        archive_file = Path(archive_path)
        if not archive_file.suffix:
            # 拡張子が指定されていない場合は .tar.gz を追加
            archive_file = archive_file.with_suffix('.tar.gz')
        
        console.print(f"[cyan]設定バックアップを作成中...[/cyan]")
        console.print(f"アーカイブ: {archive_file}")
        console.print(f"スコープ: {scope}")
        console.print(f"シークレット含む: {include_secrets}")
        console.print(f"サンプル含む: {include_samples}")
        
        # 一時ディレクトリでバックアップを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / 'bunsui-backup'
            backup_dir.mkdir()
            
            # メタデータファイルを作成
            metadata = {
                'backup_created_at': datetime.utcnow().isoformat(),
                'bunsui_version': '1.0.0',  # TODO: 実際のバージョンを取得
                'scope': scope,
                'include_secrets': include_secrets,
                'include_samples': include_samples,
                'project_root': str(find_project_root()) if find_project_root() else None,
                'current_directory': str(Path.cwd())
            }
            
            # 設定ファイルを収集
            collected_files = _collect_config_files(scope, include_secrets, include_samples)
            
            if not collected_files:
                console.print("[yellow]エクスポートする設定ファイルが見つかりません[/yellow]")
                return
            
            # ファイルをバックアップディレクトリにコピー
            for source_path, relative_path in collected_files:
                dest_path = backup_dir / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest_path)
                console.print(f"[dim]  + {relative_path}[/dim]")
            
            # メタデータを保存
            with open(backup_dir / 'metadata.json', 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # tarファイルを作成
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_file, 'w:gz') as tar:
                tar.add(backup_dir, arcname='bunsui-backup')
        
        console.print(f"[green]✓ バックアップが完了しました: {archive_file}[/green]")
        console.print(f"ファイル数: {len(collected_files)}")
        
        if include_secrets:
            console.print("[red]⚠ 注意: このバックアップには機密情報が含まれている可能性があります[/red]")
        
    except Exception as e:
        console.print(f"[red]バックアップエラー: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('archive_path')
@click.option('--target-dir', help='リストア先ディレクトリ（デフォルト: 現在のディレクトリ）')
@click.option('--dry-run', is_flag=True, help='実際にリストアせずに内容を表示')
@click.option('--force', is_flag=True, help='既存ファイルを強制上書き')
@click.pass_context
def restore(ctx: click.Context, archive_path: str, target_dir: Optional[str], 
            dry_run: bool, force: bool):
    """バックアップから設定をリストア"""
    try:
        import tarfile
        import tempfile
        
        archive_file = Path(archive_path)
        if not archive_file.exists():
            console.print(f"[red]バックアップファイルが見つかりません: {archive_file}[/red]")
            raise click.Abort()
        
        target_path = Path(target_dir) if target_dir else Path.cwd()
        
        console.print(f"[cyan]設定をリストア中...[/cyan]")
        console.print(f"バックアップ: {archive_file}")
        console.print(f"リストア先: {target_path}")
        console.print(f"ドライラン: {dry_run}")
        
        # 一時ディレクトリでアーカイブを展開
        with tempfile.TemporaryDirectory() as temp_dir:
            # tarファイルを展開
            with tarfile.open(archive_file, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            backup_dir = Path(temp_dir) / 'bunsui-backup'
            metadata_file = backup_dir / 'metadata.json'
            
            # メタデータを読み込み
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                console.print(f"\n[bold]バックアップ情報:[/bold]")
                console.print(f"作成日時: {metadata.get('backup_created_at', 'Unknown')}")
                console.print(f"Bunsuiバージョン: {metadata.get('bunsui_version', 'Unknown')}")
                console.print(f"スコープ: {metadata.get('scope', 'Unknown')}")
                console.print(f"シークレット含む: {metadata.get('include_secrets', False)}")
                console.print(f"元のプロジェクトルート: {metadata.get('project_root', 'Unknown')}")
            
            # リストアするファイルを収集
            restore_files = []
            for file_path in backup_dir.rglob('*'):
                if file_path.is_file() and file_path.name != 'metadata.json':
                    relative_path = file_path.relative_to(backup_dir)
                    target_file_path = target_path / relative_path
                    restore_files.append((file_path, target_file_path, relative_path))
            
            if not restore_files:
                console.print("[yellow]リストアするファイルが見つかりません[/yellow]")
                return
            
            # ファイル一覧を表示
            console.print(f"\n[bold]リストア対象ファイル ({len(restore_files)}個):[/bold]")
            for _, target_file_path, relative_path in restore_files:
                status = "新規" if not target_file_path.exists() else "上書き"
                status_color = "green" if status == "新規" else "yellow"
                console.print(f"[{status_color}]{status}[/{status_color}] {relative_path}")
            
            if dry_run:
                console.print("\n[cyan]ドライランモードのため、実際のリストアは行いません[/cyan]")
                return
            
            # 確認
            if not force:
                overwrite_files = [f for f in restore_files if f[1].exists()]
                if overwrite_files and not Confirm.ask(f"{len(overwrite_files)}個のファイルが上書きされます。続行しますか？"):
                    console.print("[yellow]リストアがキャンセルされました[/yellow]")
                    return
            
            # ファイルをリストア
            import shutil
            for source_path, target_file_path, relative_path in restore_files:
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_file_path)
                console.print(f"[green]✓[/green] {relative_path}")
        
        console.print(f"\n[green]✓ リストアが完了しました[/green]")
        console.print(f"リストアされたファイル数: {len(restore_files)}")
        
        if metadata.get('include_secrets'):
            console.print("[red]⚠ 注意: シークレットファイルがリストアされました[/red]")
        
    except Exception as e:
        console.print(f"[red]リストアエラー: {e}[/red]")
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


def _display_all_configs(format: str, verbose: bool = False, show_defaults: bool = False):
    """すべての設定を表示"""
    config_manager = get_config_manager()
    
    # 設定ファイルの読み込みを強制的に行う
    config_manager.load_config()
    
    # 実際の設定ファイルから読み込む
    if config_manager.loaded_config_file and config_manager.loaded_config_file.exists():
        # 設定ファイルが存在する場合、ファイルから直接読み込み
        import yaml
        import json
        
        with open(config_manager.loaded_config_file, 'r', encoding='utf-8') as f:
            if config_manager.loaded_config_file.suffix in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f) or {}
            else:
                config_data = json.load(f)
        
        # 設定ファイルのパスを表示
        console.print(f"[dim]📁 設定ファイル: {config_manager.loaded_config_file}[/dim]")
    else:
        # 設定ファイルが存在しない場合、デフォルト設定を使用
        config = config_manager.config
        config_data = config.model_dump()
        console.print("[dim]📁 設定ファイル: デフォルト設定を使用[/dim]")
    
    if format == 'table':
        _display_config_table(config_data, verbose=verbose, show_defaults=show_defaults)
    elif format == 'json':
        console.print(json.dumps(config_data, indent=2, default=str))
    else:  # yaml
        console.print(yaml.dump(config_data, default_flow_style=False))


def _display_scope_config(scope: str, format: str, verbose: bool = False, show_defaults: bool = False):
    """特定のスコープの設定を表示"""
    project_root = find_project_root()
    scope_files = {
        'local': Path.cwd() / '.bunsui' / 'config.yaml',
        'project': project_root / '.bunsui' / 'config.yaml' if project_root else None,
        'global': Path.home() / '.bunsui' / 'config' / 'config.yaml'
    }
    
    config_file = scope_files.get(scope)
    if not config_file or not config_file.exists():
        console.print(f"[yellow]{scope} スコープの設定ファイルが見つかりません[/yellow]")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.suffix in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
        
        if format == 'table':
            _display_config_table(config_data, verbose=verbose, show_defaults=show_defaults)
        elif format == 'json':
            console.print(json.dumps(config_data, indent=2, default=str))
        else:  # yaml
            console.print(yaml.dump(config_data, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]設定ファイル読み込みエラー: {e}[/red]")


def _display_config_table(config_data: dict, verbose: bool = False, show_defaults: bool = False):
    """設定をテーブル形式で表示"""
    
    if verbose:
        # 詳細表示: すべての設定をフラット化して表示
        _display_detailed_config_table(config_data, show_defaults)
    else:
        # 簡潔表示: カテゴリ別に重要な設定のみ表示
        _display_summary_config_table(config_data, show_defaults)


def _display_summary_config_table(config_data: dict, show_defaults: bool = False):
    """重要な設定のみを表示するサマリーテーブル"""
    
    # デフォルト設定を取得
    default_config_data = _get_default_config_dict()
    
    # 重要な設定項目の定義
    important_keys = {
        '基本設定': ['mode', 'version', 'created_at'],
        'AWS': ['aws.region', 'aws.profile', 'aws.dynamodb_table_prefix', 'aws.s3_bucket_prefix'],
        'パイプライン': ['defaults.timeout_seconds', 'defaults.max_concurrent_jobs', 'defaults.output_format'],
        'ディレクトリ': ['directories.data', 'directories.cache', 'directories.logs']
    }
    
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
    
    def is_value_modified(key_path: str, current_value, default_value) -> bool:
        """値がデフォルトから変更されているかチェック"""
        # パス系の設定は特別扱い（絶対パス展開されるため）
        if any(path_key in key_path for path_key in ['data_dir', 'config_dir', 'cache_dir']):
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
    
    table = Table(title="Bunsui 設定サマリー", box=box.ROUNDED)
    table.add_column("カテゴリ", style="cyan", min_width=12)
    table.add_column("設定項目", style="white", min_width=25)
    table.add_column("値", min_width=30)
    table.add_column("状態", style="dim", min_width=8)
    
    modified_count = 0
    total_count = 0
    
    for category, keys in important_keys.items():
        first_in_category = True
        for key_path in keys:
            current_value = get_nested_value(config_data, key_path)
            default_value = get_nested_value(default_config_data, key_path)
            
            # デフォルト値を表示しない場合、Noneや空文字列はスキップ
            if not show_defaults and (current_value is None or current_value == ""):
                continue
            
            total_count += 1
            
            # 機密情報をマスク
            if any(secret in key_path.lower() for secret in ['password', 'secret', 'key', 'token']):
                display_value = "****"
                value_style = "red"
                status = "機密"
            else:
                display_value = str(current_value) if current_value is not None else "未設定"
                if len(display_value) > 50:
                    display_value = display_value[:47] + "..."
                
                # デフォルト値と比較して色とステータスを決定
                is_modified = is_value_modified(key_path, current_value, default_value)
                if is_modified:
                    value_style = "yellow"  # カスタマイズされた値は黄色
                    status = "変更"
                    modified_count += 1
                else:
                    value_style = "green"   # デフォルト値は緑色
                    status = "標準"
            
            # 設定項目名を短縮
            short_key = key_path.split('.')[-1]
            
            category_display = category if first_in_category else ""
            table.add_row(
                category_display, 
                short_key, 
                f"[{value_style}]{display_value}[/{value_style}]",
                status
            )
            first_in_category = False
    
    console.print(table)
    
    # 変更統計を表示
    if total_count > 0:
        percentage = (modified_count / total_count) * 100
        console.print(f"\n[dim]📊 設定統計: {modified_count}/{total_count} 項目がデフォルトから変更されています ({percentage:.1f}%)[/dim]")
    
    # 凡例を表示
    console.print("\n[dim]🎨 凡例:[/dim]")
    console.print("  [green]■[/green] 標準値  [yellow]■[/yellow] カスタマイズ済み  [red]■[/red] 機密情報")
    
    # 詳細表示の案内
    console.print("\n[dim]💡 すべての設定を表示するには --verbose オプションを使用してください[/dim]")
    console.print("[dim]   例: bunsui config list --verbose[/dim]")


def _flatten_dict(d, parent_key='', sep='.'):
    """ネストした辞書をフラット化"""
    items = []
    for k, v in d.items():
        # 内部フィールドを除外
        if k.startswith('_'):
            continue
            
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _display_detailed_config_table(config_data: dict, show_defaults: bool = False):
    """詳細な設定をフラット化して表示"""
    
    # デフォルト設定を取得
    default_config_data = _get_default_config_dict()
    default_flat = _flatten_dict(default_config_data)
    
    flat_config = _flatten_dict(config_data)
    
    table = Table(title="Bunsui 設定（詳細）", box=box.ROUNDED)
    table.add_column("設定キー", style="cyan", min_width=35)
    table.add_column("値", min_width=30)
    table.add_column("型", style="dim", min_width=10)
    table.add_column("状態", style="dim", min_width=8)
    
    modified_count = 0
    total_count = 0
    
    for key, value in sorted(flat_config.items()):
        # デフォルト値を表示しない場合、空の値をスキップ
        if not show_defaults and (value is None or value == "" or 
                                 (hasattr(value, '__len__') and len(value) == 0)):
            continue
        
        total_count += 1
        default_value = default_flat.get(key)
        
        # 機密情報を隠す
        if any(secret in key.lower() for secret in ['password', 'secret', 'key', 'token']):
            display_value = "****"
            value_style = "red"
            status = "機密"
        else:
            display_value = str(value)
            if len(display_value) > 50:
                display_value = display_value[:47] + "..."
            
            # デフォルト値と比較
            if value != default_value:
                value_style = "yellow"  # カスタマイズされた値は黄色
                status = "変更"
                modified_count += 1
            else:
                value_style = "green"   # デフォルト値は緑色
                status = "標準"
        
        table.add_row(
            key, 
            f"[{value_style}]{display_value}[/{value_style}]",
            type(value).__name__,
            status
        )
    
    console.print(table)
    
    # 変更統計を表示
    if total_count > 0:
        percentage = (modified_count / total_count) * 100
        console.print(f"\n[dim]📊 設定統計: {modified_count}/{total_count} 項目がデフォルトから変更されています ({percentage:.1f}%)[/dim]")
    
    # 凡例を表示
    console.print("\n[dim]🎨 凡例:[/dim]")
    console.print("  [green]■[/green] 標準値  [yellow]■[/yellow] カスタマイズ済み  [red]■[/red] 機密情報")


def _get_default_config_dict() -> dict:
    """デフォルト設定の辞書を取得"""
    try:
        # デフォルトのBunsuiConfigインスタンスを作成
        from ...core.config.models import BunsuiConfig
        default_config = BunsuiConfig()
        return default_config.model_dump(exclude={'config_file_path'})
    except Exception:
        # フォールバック: 空の辞書を返す
        return {}


def _collect_config_files(scope: str, include_secrets: bool, include_samples: bool) -> List[tuple[Path, Path]]:
    """設定ファイルを収集"""
    collected_files = []
    
    if scope in ['project', 'all']:
        # プロジェクト設定を収集
        project_root = find_project_root()
        if project_root:
            _collect_from_directory(
                project_root / '.bunsui', 
                collected_files, 
                include_secrets, 
                include_samples,
                base_name='project'
            )
    
    if scope in ['local', 'all']:
        # ローカル設定を収集
        _collect_from_directory(
            Path.cwd() / '.bunsui', 
            collected_files, 
            include_secrets, 
            include_samples,
            base_name='local'
        )
    
    if scope in ['global', 'all']:
        # グローバル設定を収集
        _collect_from_directory(
            Path.home() / '.bunsui', 
            collected_files, 
            include_secrets, 
            include_samples,
            base_name='global'
        )
    
    return collected_files


def _collect_from_directory(source_dir: Path, collected_files: List[tuple[Path, Path]], 
                           include_secrets: bool, include_samples: bool, base_name: str):
    """ディレクトリから設定ファイルを収集"""
    if not source_dir.exists():
        return
    
    for file_path in source_dir.rglob('*'):
        if not file_path.is_file():
            continue
        
        # ファイル名による判定
        file_name = file_path.name.lower()
        relative_path = file_path.relative_to(source_dir)
        
        # 機密ファイルのチェック
        if 'secret' in file_name and not include_secrets:
            continue
        
        # サンプルファイルのチェック
        if not include_samples and ('sample' in str(relative_path).lower() or 
                                   'example' in str(relative_path).lower()):
            continue
        
        # キャッシュやログファイルは除外
        if any(exclude in str(relative_path).lower() for exclude in ['cache', 'logs', '__pycache__', '.pyc']):
            continue
        
        # バックアップでの相対パス
        backup_relative_path = Path(base_name) / relative_path
        collected_files.append((file_path, backup_relative_path)) 