"""
Configuration management commands for Bunsui CLI.
"""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box
import json
import yaml
import os
from pathlib import Path

from ...core.config.manager import ConfigManager, get_config_manager
from ...core.exceptions import ConfigurationError

console = Console()


@click.group()
def config():
    """設定管理コマンド"""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
@click.option('--global', 'global_config', is_flag=True, help='Set global configuration')
@click.option('--local', is_flag=True, help='Set local configuration (default)')
@click.pass_context
def set(ctx: click.Context, key: str, value: str, global_config: bool, local: bool):
    """設定値を設定"""
    try:
        config_manager = get_config_manager()
        
        # 値の型変換
        converted_value = _convert_value(value)
        
        # 設定値を設定
        config_manager.set_value(key, converted_value)
        
        # 設定を保存
        if global_config:
            # グローバル設定の場合
            global_config_file = Path.home() / '.bunsui' / 'config' / 'config.yaml'
            config_manager.save_config(global_config_file)
        else:
            # ローカル設定の場合
            local_config_file = Path.cwd() / '.bunsui' / 'config.yaml'
            config_manager.save_config(local_config_file)
        
        config_type = "global" if global_config else "local"
        console.print(f"[green]✓ Configuration updated successfully[/green]")
        console.print(f"Key: {key}")
        console.print(f"Value: {converted_value}")
        console.print(f"Scope: {config_type}")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error setting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('key')
@click.option('--global', 'global_config', is_flag=True, help='Get global configuration')
@click.option('--local', is_flag=True, help='Get local configuration (default)')
@click.option('--format', type=click.Choice(['text', 'json', 'yaml']), default='text', help='Output format')
@click.pass_context
def get(ctx: click.Context, key: str, global_config: bool, local: bool, format: str):
    """設定値を取得"""
    try:
        config_manager = get_config_manager()
        
        # 設定値を取得
        value = config_manager.get_value(key)
        
        if value is None:
            console.print(f"[yellow]Configuration key not found: {key}[/yellow]")
            return
        
        config_type = "global" if global_config else "local"
        
        if format == 'text':
            console.print(f"[bold blue]Configuration: {key}[/bold blue]")
            console.print(f"Value: {value}")
            console.print(f"Type: {type(value).__name__}")
            console.print(f"Scope: {config_type}")
        elif format == 'json':
            config_data = {
                "key": key,
                "value": value,
                "type": type(value).__name__,
                "scope": config_type
            }
            console.print(json.dumps(config_data, indent=2))
        else:  # yaml
            config_data = {
                "key": key,
                "value": value,
                "type": type(value).__name__,
                "scope": config_type
            }
            console.print(yaml.dump(config_data, default_flow_style=False))
            
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error getting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.option('--global', 'global_config', is_flag=True, help='List global configuration')
@click.option('--local', is_flag=True, help='List local configuration (default)')
@click.option('--all', is_flag=True, help='List all configuration')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def list(ctx: click.Context, global_config: bool, local: bool, all: bool, format: str):
    """設定一覧を表示"""
    try:
        config_manager = get_config_manager()
        
        # 設定を取得
        config = config_manager.config
        
        # 設定を階層化して表示
        config_dict = config.dict(exclude_unset=True)
        
        if format == 'table':
            _display_config_table(config_dict, all)
        elif format == 'json':
            console.print(json.dumps(config_dict, indent=2, default=str))
        else:  # yaml
            console.print(yaml.dump(config_dict, default_flow_style=False))
            
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error listing config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('key')
@click.option('--force', is_flag=True, help='Force delete without confirmation')
@click.pass_context
def delete(ctx: click.Context, key: str, force: bool):
    """設定を削除"""
    try:
        config_manager = get_config_manager()
        
        # 現在の値を確認
        current_value = config_manager.get_value(key)
        
        if current_value is None:
            console.print(f"[yellow]Configuration key not found: {key}[/yellow]")
            return
        
        if not force:
            console.print(f"[yellow]Current value: {current_value}[/yellow]")
            if not click.confirm(f"Are you sure you want to delete configuration '{key}'?"):
                console.print("[yellow]Delete cancelled[/yellow]")
                return
        
        # 設定を削除
        config_manager.delete_value(key)
        
        # 設定を保存
        config_manager.save_config()
        
        console.print(f"[green]✓ Configuration deleted: {key}[/green]")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error deleting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.option('--global', 'global_config', is_flag=True, help='Reset global configuration')
@click.option('--local', is_flag=True, help='Reset local configuration (default)')
@click.option('--all', is_flag=True, help='Reset all configuration')
@click.option('--force', is_flag=True, help='Force reset without confirmation')
@click.pass_context
def reset(ctx: click.Context, global_config: bool, local: bool, all: bool, force: bool):
    """設定をリセット"""
    try:
        config_manager = get_config_manager()
        
        scope = "all" if all else "global" if global_config else "local"
        
        if not force:
            if not click.confirm(f"Are you sure you want to reset {scope} configuration?"):
                console.print("[yellow]Reset cancelled[/yellow]")
                return
        
        # 設定をリセット
        config_manager.reset_config()
        
        # 設定を保存
        config_manager.save_config()
        
        console.print(f"[green]✓ Configuration reset successfully[/green]")
        console.print(f"Scope: {scope}")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error resetting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.pass_context
def validate(ctx: click.Context):
    """設定を検証"""
    try:
        config_manager = get_config_manager()
        
        # 設定を検証
        validation_result = config_manager.validate_config()
        
        console.print(f"[bold blue]Configuration Validation[/bold blue]")
        
        if validation_result['valid']:
            console.print("[green]✓ Configuration is valid[/green]")
        else:
            console.print("[red]✗ Configuration validation failed[/red]")
        
        # エラーの表示
        if validation_result['errors']:
            console.print(f"\n[bold red]Errors:[/bold red]")
            for error in validation_result['errors']:
                console.print(f"  [red]• {error}[/red]")
        
        # 警告の表示
        if validation_result['warnings']:
            console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
            for warning in validation_result['warnings']:
                console.print(f"  [yellow]• {warning}[/yellow]")
        
        # 検証結果の詳細をテーブルで表示
        table = Table(title="Validation Details", box=box.ROUNDED)
        table.add_column("Category", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Message", style="blue")
        
        # AWS設定の検証
        aws_config = config_manager.get_aws_config()
        if aws_config.region:
            table.add_row("AWS Region", "✓ Valid", f"Region: {aws_config.region}")
        else:
            table.add_row("AWS Region", "✗ Invalid", "No region configured")
        
        # 認証情報の検証
        if aws_config.profile or aws_config.access_key_id:
            table.add_row("AWS Credentials", "✓ Valid", "Credentials configured")
        else:
            table.add_row("AWS Credentials", "⚠ Warning", "No credentials configured")
        
        console.print(table)
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error validating config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('file_path')
@click.option('--format', type=click.Choice(['yaml', 'json']), default='yaml', help='Export format')
@click.pass_context
def export(ctx: click.Context, file_path: str, format: str):
    """設定をエクスポート"""
    try:
        config_manager = get_config_manager()
        
        # 設定をエクスポート
        config_str = config_manager.export_config(format)
        
        # ファイルに保存
        output_file = Path(file_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(config_str)
        
        console.print(f"[green]✓ Configuration exported successfully[/green]")
        console.print(f"File: {output_file}")
        console.print(f"Format: {format}")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error exporting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('file_path')
@click.option('--format', type=click.Choice(['yaml', 'json']), help='Import format (auto-detect if not specified)')
@click.option('--force', is_flag=True, help='Force import without confirmation')
@click.pass_context
def import_config(ctx: click.Context, file_path: str, format: Optional[str], force: bool):
    """設定をインポート"""
    try:
        config_manager = get_config_manager()
        
        input_file = Path(file_path)
        
        if not input_file.exists():
            console.print(f"[red]File not found: {input_file}[/red]")
            raise click.Abort()
        
        # フォーマットを自動検出
        if not format:
            if input_file.suffix.lower() in ['.yaml', '.yml']:
                format = 'yaml'
            elif input_file.suffix.lower() == '.json':
                format = 'json'
            else:
                console.print(f"[red]Cannot auto-detect format for file: {input_file}[/red]")
                raise click.Abort()
        
        if not force:
            if not click.confirm(f"Are you sure you want to import configuration from '{input_file}'?"):
                console.print("[yellow]Import cancelled[/yellow]")
                return
        
        # ファイルを読み込み
        with open(input_file, 'r') as f:
            config_str = f.read()
        
        # 設定をインポート
        config_manager.import_config(config_str, format)
        
        # 設定を保存
        config_manager.save_config()
        
        console.print(f"[green]✓ Configuration imported successfully[/green]")
        console.print(f"File: {input_file}")
        console.print(f"Format: {format}")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error importing config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.pass_context
def show(ctx: click.Context):
    """現在の設定を表示"""
    try:
        config_manager = get_config_manager()
        config = config_manager.config
        
        console.print(f"[bold blue]Bunsui Configuration[/bold blue]")
        console.print(f"Environment: {config.environment}")
        console.print(f"Debug: {config.debug}")
        console.print(f"Config Directory: {config.config_dir}")
        console.print(f"Data Directory: {config.data_dir}")
        console.print(f"Cache Directory: {config.cache_dir}")
        
        # AWS設定
        console.print(f"\n[bold green]AWS Configuration[/bold green]")
        aws_config = config.aws
        console.print(f"Region: {aws_config.region}")
        console.print(f"Profile: {aws_config.profile or 'N/A'}")
        console.print(f"DynamoDB Table Prefix: {aws_config.dynamodb_table_prefix}")
        console.print(f"S3 Bucket Prefix: {aws_config.s3_bucket_prefix}")
        console.print(f"Timeout: {aws_config.timeout}s")
        console.print(f"Max Retries: {aws_config.max_retries}")
        
        # パイプライン設定
        console.print(f"\n[bold yellow]Pipeline Configuration[/bold yellow]")
        pipeline_config = config.pipeline
        console.print(f"Default Timeout: {pipeline_config.default_timeout}s")
        console.print(f"Max Concurrent Jobs: {pipeline_config.max_concurrent_jobs}")
        console.print(f"Enable Checkpoints: {pipeline_config.enable_checkpoints}")
        console.print(f"Checkpoint Interval: {pipeline_config.checkpoint_interval}s")
        console.print(f"Retry Failed Jobs: {pipeline_config.retry_failed_jobs}")
        console.print(f"Max Job Retries: {pipeline_config.max_job_retries}")
        
        # ログ設定
        console.print(f"\n[bold magenta]Logging Configuration[/bold magenta]")
        logging_config = config.logging
        console.print(f"Level: {logging_config.level}")
        console.print(f"Log to File: {logging_config.log_to_file}")
        console.print(f"CloudWatch Logs: {logging_config.enable_cloudwatch}")
        
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error showing config: {e}[/red]")
        raise click.Abort()


def _convert_value(value: str):
    """値を適切な型に変換"""
    # ブール値の変換
    if value.lower() in ['true', 'false']:
        return value.lower() == 'true'
    
    # 数値の変換
    try:
        # 整数
        if '.' not in value:
            return int(value)
        # 浮動小数点
        return float(value)
    except ValueError:
        pass
    
    # 文字列として返す
    return value


def _display_config_table(config_dict: dict, show_all: bool = False):
    """設定をテーブル形式で表示"""
    table = Table(title="Configuration", box=box.ROUNDED)
    table.add_column("Section", style="cyan")
    table.add_column("Key", style="green")
    table.add_column("Value", style="yellow")
    table.add_column("Type", style="blue")
    
    def add_config_rows(data: dict, section: str = ""):
        for key, value in data.items():
            if isinstance(value, dict):
                add_config_rows(value, f"{section}.{key}" if section else key)
            else:
                # 機密情報をマスク
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                    if value:
                        display_value = "***HIDDEN***"
                    else:
                        display_value = "N/A"
                else:
                    display_value = str(value)
                
                table.add_row(
                    section,
                    key,
                    display_value,
                    type(value).__name__
                )
    
    add_config_rows(config_dict)
    console.print(table) 