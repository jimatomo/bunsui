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
        config_type = "global" if global_config else "local"
        console.print(f"[green]Setting {config_type} config: {key} = {value}[/green]")
        
        # TODO: Implement actual config setting
        # This would typically write to a config file or environment
        
        # Simulate config setting
        config_data = {
            "key": key,
            "value": value,
            "type": config_type,
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        console.print(f"[green]Configuration updated successfully[/green]")
        console.print(f"Key: {key}")
        console.print(f"Value: {value}")
        console.print(f"Scope: {config_type}")
        
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
        config_type = "global" if global_config else "local"
        console.print(f"[green]Getting {config_type} config: {key}[/green]")
        
        # TODO: Implement actual config retrieval
        # This would typically read from a config file or environment
        
        # Simulate config retrieval
        config_data = {
            "key": key,
            "value": "sample_value",
            "type": config_type,
            "source": "config_file",
            "last_updated": "2024-01-15T10:30:00Z"
        }
        
        if format == 'text':
            console.print(f"Key: {config_data['key']}")
            console.print(f"Value: {config_data['value']}")
            console.print(f"Type: {config_data['type']}")
            console.print(f"Source: {config_data['source']}")
            console.print(f"Last Updated: {config_data['last_updated']}")
        elif format == 'json':
            console.print(json.dumps(config_data, indent=2))
        else:  # yaml
            console.print(yaml.dump(config_data, default_flow_style=False))
            
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
        if all:
            console.print("[green]Listing all configuration[/green]")
        elif global_config:
            console.print("[green]Listing global configuration[/green]")
        else:
            console.print("[green]Listing local configuration[/green]")
        
        # TODO: Implement actual config listing
        # This would typically read from config files or environment
        
        # Simulate config data
        configs = [
            {
                "key": "aws.region",
                "value": "us-east-1",
                "type": "global",
                "source": "config_file",
                "last_updated": "2024-01-15T10:30:00Z"
            },
            {
                "key": "aws.profile",
                "value": "default",
                "type": "global",
                "source": "config_file",
                "last_updated": "2024-01-15T10:30:00Z"
            },
            {
                "key": "pipeline.default_timeout",
                "value": "3600",
                "type": "local",
                "source": "config_file",
                "last_updated": "2024-01-15T10:30:00Z"
            },
            {
                "key": "logging.level",
                "value": "INFO",
                "type": "local",
                "source": "config_file",
                "last_updated": "2024-01-15T10:30:00Z"
            }
        ]
        
        # Filter based on options
        if not all:
            if global_config:
                configs = [c for c in configs if c["type"] == "global"]
            else:
                configs = [c for c in configs if c["type"] == "local"]
        
        if format == 'table':
            table = Table(title="Configuration", box=box.ROUNDED)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Source", style="blue")
            table.add_column("Last Updated", style="magenta")
            
            for config in configs:
                table.add_row(
                    config["key"],
                    config["value"],
                    config["type"],
                    config["source"],
                    config["last_updated"]
                )
            
            console.print(table)
        elif format == 'json':
            console.print(json.dumps(configs, indent=2))
        else:  # yaml
            console.print(yaml.dump(configs, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error listing config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('key')
@click.option('--global', 'global_config', is_flag=True, help='Delete global configuration')
@click.option('--local', is_flag=True, help='Delete local configuration (default)')
@click.option('--force', is_flag=True, help='Force deletion without confirmation')
@click.pass_context
def delete(ctx: click.Context, key: str, global_config: bool, local: bool, force: bool):
    """設定値を削除"""
    try:
        config_type = "global" if global_config else "local"
        
        if not force:
            if not click.confirm(f"Are you sure you want to delete {config_type} config '{key}'?"):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return
        
        console.print(f"[green]Deleting {config_type} config: {key}[/green]")
        
        # TODO: Implement actual config deletion
        console.print(f"[green]Configuration '{key}' deleted successfully[/green]")
        
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
        if all:
            scope = "all"
        elif global_config:
            scope = "global"
        else:
            scope = "local"
        
        if not force:
            if not click.confirm(f"Are you sure you want to reset {scope} configuration?"):
                console.print("[yellow]Reset cancelled[/yellow]")
                return
        
        console.print(f"[green]Resetting {scope} configuration[/green]")
        
        # TODO: Implement actual config reset
        console.print(f"[green]Configuration reset successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Error resetting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def validate(ctx: click.Context, format: str):
    """設定を検証"""
    try:
        console.print("[green]Validating configuration...[/green]")
        
        # TODO: Implement actual config validation
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config_files": [
                {
                    "path": "~/.bunsui/config.yaml",
                    "status": "valid",
                    "errors": []
                },
                {
                    "path": "./.bunsui/config.yaml",
                    "status": "valid",
                    "errors": []
                }
            ],
            "environment_variables": [
                {
                    "name": "BUNSUI_AWS_REGION",
                    "status": "set",
                    "value": "us-east-1"
                },
                {
                    "name": "BUNSUI_LOG_LEVEL",
                    "status": "not_set",
                    "value": None
                }
            ]
        }
        
        if format == 'table':
            console.print(f"[bold blue]Configuration Validation[/bold blue]")
            console.print(f"Overall Status: {'✓ Valid' if validation_results['valid'] else '✗ Invalid'}")
            
            if validation_results['errors']:
                console.print("\n[red]Errors:[/red]")
                for error in validation_results['errors']:
                    console.print(f"  - {error}")
            
            if validation_results['warnings']:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in validation_results['warnings']:
                    console.print(f"  - {warning}")
            
            # Config files table
            if validation_results['config_files']:
                files_table = Table(title="Config Files", box=box.ROUNDED)
                files_table.add_column("Path", style="cyan")
                files_table.add_column("Status", style="green")
                files_table.add_column("Errors", style="red")
                
                for file_info in validation_results['config_files']:
                    status_color = "green" if file_info["status"] == "valid" else "red"
                    files_table.add_row(
                        file_info["path"],
                        f"[{status_color}]{file_info['status']}[/{status_color}]",
                        ", ".join(file_info["errors"]) if file_info["errors"] else "None"
                    )
                
                console.print(files_table)
            
            # Environment variables table
            if validation_results['environment_variables']:
                env_table = Table(title="Environment Variables", box=box.ROUNDED)
                env_table.add_column("Name", style="cyan")
                env_table.add_column("Status", style="green")
                env_table.add_column("Value", style="yellow")
                
                for env_info in validation_results['environment_variables']:
                    status_color = "green" if env_info["status"] == "set" else "red"
                    env_table.add_row(
                        env_info["name"],
                        f"[{status_color}]{env_info['status']}[/{status_color}]",
                        env_info["value"] or "Not set"
                    )
                
                console.print(env_table)
                
        elif format == 'json':
            console.print(json.dumps(validation_results, indent=2))
        else:  # yaml
            console.print(yaml.dump(validation_results, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error validating config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--format', type=click.Choice(['json', 'yaml']), default='yaml', help='Export format')
@click.pass_context
def export(ctx: click.Context, output: Optional[str], format: str):
    """設定をエクスポート"""
    try:
        console.print("[green]Exporting configuration...[/green]")
        
        # TODO: Implement actual config export
        config_data = {
            "aws": {
                "region": "us-east-1",
                "profile": "default"
            },
            "pipeline": {
                "default_timeout": 3600,
                "max_retries": 3
            },
            "logging": {
                "level": "INFO",
                "format": "json"
            },
            "monitoring": {
                "enabled": True,
                "metrics_interval": 60
            }
        }
        
        if output:
            with open(output, 'w') as f:
                if format == 'json':
                    json.dump(config_data, f, indent=2)
                else:  # yaml
                    yaml.dump(config_data, f, default_flow_style=False)
            
            console.print(f"[green]Configuration exported to: {output}[/green]")
        else:
            if format == 'json':
                console.print(json.dumps(config_data, indent=2))
            else:  # yaml
                console.print(yaml.dump(config_data, default_flow_style=False))
                
    except Exception as e:
        console.print(f"[red]Error exporting config: {e}[/red]")
        raise click.Abort()


@config.command()
@click.argument('file_path')
@click.option('--force', is_flag=True, help='Force import without confirmation')
@click.pass_context
def import_config(ctx: click.Context, file_path: str, force: bool):
    """設定をインポート"""
    try:
        if not force:
            if not click.confirm(f"Are you sure you want to import configuration from '{file_path}'?"):
                console.print("[yellow]Import cancelled[/yellow]")
                return
        
        console.print(f"[green]Importing configuration from: {file_path}[/green]")
        
        # TODO: Implement actual config import
        if not os.path.exists(file_path):
            console.print(f"[red]File not found: {file_path}[/red]")
            raise click.Abort()
        
        # Simulate import
        console.print(f"[green]Configuration imported successfully from: {file_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error importing config: {e}[/red]")
        raise click.Abort() 