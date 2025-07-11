"""
Pipeline management commands for Bunsui CLI.
"""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box
import json
import yaml

console = Console()


@click.group()
def pipeline():
    """パイプライン管理コマンド"""
    pass


@pipeline.command()
@click.option('--file', '-f', required=True, help='Pipeline definition file')
@click.option('--name', '-n', help='Pipeline name (overrides file definition)')
@click.option('--description', '-d', help='Pipeline description')
@click.option('--dry-run', is_flag=True, help='Validate without creating')
@click.option('--format', type=click.Choice(['yaml', 'json']), default='yaml', help='Output format')
@click.pass_context
def create(ctx: click.Context, file: str, name: Optional[str], description: Optional[str], 
           dry_run: bool, format: str):
    """新しいパイプラインを作成"""
    try:
        # TODO: Implement pipeline creation logic
        if dry_run:
            console.print(f"[yellow]Dry run: Would create pipeline from {file}[/yellow]")
        else:
            console.print(f"[green]Creating pipeline from {file}[/green]")
            
        # Placeholder for actual implementation
        pipeline_data = {
            "id": "pipeline-123",
            "name": name or "New Pipeline",
            "description": description or "Pipeline created via CLI",
            "status": "created",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        if format == 'json':
            console.print(json.dumps(pipeline_data, indent=2))
        else:
            console.print(yaml.dump(pipeline_data, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error creating pipeline: {e}[/red]")
        raise click.Abort()


@pipeline.command()
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.option('--status', help='Filter by status')
@click.option('--limit', type=int, default=50, help='Maximum number of pipelines to show')
@click.option('--all', is_flag=True, help='Show all pipelines (ignore limit)')
@click.pass_context
def list(ctx: click.Context, format: str, status: Optional[str], limit: int, all: bool):
    """パイプライン一覧を表示"""
    try:
        # TODO: Implement actual pipeline listing
        pipelines = [
            {
                "id": "pipeline-1",
                "name": "ETL Pipeline",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "last_run": "2024-01-15T10:30:00Z"
            },
            {
                "id": "pipeline-2", 
                "name": "Data Processing",
                "status": "inactive",
                "created_at": "2024-01-02T00:00:00Z",
                "last_run": "2024-01-10T15:45:00Z"
            }
        ]
        
        if status:
            pipelines = [p for p in pipelines if p["status"] == status]
        
        if not all and limit:
            pipelines = pipelines[:limit]
        
        if format == 'table':
            table = Table(title="Pipelines", box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="blue")
            table.add_column("Last Run", style="magenta")
            
            for pipeline in pipelines:
                status_color = "green" if pipeline["status"] == "active" else "red"
                table.add_row(
                    pipeline["id"],
                    pipeline["name"],
                    f"[{status_color}]{pipeline['status']}[/{status_color}]",
                    pipeline["created_at"],
                    pipeline["last_run"]
                )
            
            console.print(table)
        elif format == 'json':
            console.print(json.dumps(pipelines, indent=2))
        else:  # yaml
            console.print(yaml.dump(pipelines, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error listing pipelines: {e}[/red]")
        raise click.Abort()


@pipeline.command()
@click.argument('pipeline_id')
@click.option('--force', is_flag=True, help='Force deletion without confirmation')
@click.pass_context
def delete(ctx: click.Context, pipeline_id: str, force: bool):
    """パイプラインを削除"""
    try:
        if not force:
            if not click.confirm(f"Are you sure you want to delete pipeline '{pipeline_id}'?"):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return
        
        # TODO: Implement actual pipeline deletion
        console.print(f"[green]Deleted pipeline: {pipeline_id}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error deleting pipeline: {e}[/red]")
        raise click.Abort()


@pipeline.command()
@click.argument('pipeline_id')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def show(ctx: click.Context, pipeline_id: str, format: str):
    """パイプラインの詳細を表示"""
    try:
        # TODO: Implement actual pipeline details retrieval
        pipeline_data = {
            "id": pipeline_id,
            "name": "Sample Pipeline",
            "description": "A sample pipeline for demonstration",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "jobs": [
                {"id": "job-1", "name": "Extract", "status": "completed"},
                {"id": "job-2", "name": "Transform", "status": "running"},
                {"id": "job-3", "name": "Load", "status": "pending"}
            ]
        }
        
        if format == 'table':
            console.print(f"[bold blue]Pipeline: {pipeline_data['name']}[/bold blue]")
            console.print(f"ID: {pipeline_data['id']}")
            console.print(f"Status: {pipeline_data['status']}")
            console.print(f"Created: {pipeline_data['created_at']}")
            console.print(f"Updated: {pipeline_data['updated_at']}")
            
            if pipeline_data.get('jobs'):
                table = Table(title="Jobs", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Status", style="yellow")
                
                for job in pipeline_data['jobs']:
                    status_color = "green" if job["status"] == "completed" else "yellow"
                    table.add_row(
                        job["id"],
                        job["name"],
                        f"[{status_color}]{job['status']}[/{status_color}]"
                    )
                
                console.print(table)
        elif format == 'json':
            console.print(json.dumps(pipeline_data, indent=2))
        else:  # yaml
            console.print(yaml.dump(pipeline_data, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error showing pipeline: {e}[/red]")
        raise click.Abort()


@pipeline.command()
@click.argument('pipeline_id')
@click.option('--file', '-f', help='New pipeline definition file')
@click.option('--name', '-n', help='New pipeline name')
@click.option('--description', '-d', help='New pipeline description')
@click.option('--dry-run', is_flag=True, help='Validate without updating')
@click.pass_context
def update(ctx: click.Context, pipeline_id: str, file: Optional[str], name: Optional[str],
           description: Optional[str], dry_run: bool):
    """パイプラインを更新"""
    try:
        if dry_run:
            console.print(f"[yellow]Dry run: Would update pipeline {pipeline_id}[/yellow]")
        else:
            console.print(f"[green]Updating pipeline: {pipeline_id}[/green]")
        
        # TODO: Implement actual pipeline update logic
        updates = {}
        if file:
            updates['file'] = file
        if name:
            updates['name'] = name
        if description:
            updates['description'] = description
            
        if updates:
            console.print("Updates:", updates)
        else:
            console.print("[yellow]No updates specified[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error updating pipeline: {e}[/red]")
        raise click.Abort() 