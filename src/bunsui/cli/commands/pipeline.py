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
import os
from pathlib import Path

from ...core.models.pipeline import Pipeline, PipelineStatus
from ...core.pipeline.repository import PipelineRepository
from ...aws.client import AWSClient
from ...core.config.manager import ConfigManager
from ...core.exceptions import ValidationError
from ...aws.exceptions import AWSError

console = Console()


def get_pipeline_repository() -> PipelineRepository:
    """パイプラインリポジトリのインスタンスを取得"""
    try:
        config_manager = ConfigManager()
        aws_config = config_manager.get_aws_config()
        
        aws_client = AWSClient(
            "dynamodb",
            region_name=aws_config.region,
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            aws_session_token=aws_config.session_token,
            profile_name=aws_config.profile
        )
        
        table_name = f"{aws_config.dynamodb_table_prefix}-pipelines"
        return PipelineRepository(aws_client, table_name)
    except Exception as e:
        console.print(f"[red]Failed to initialize pipeline repository: {e}[/red]")
        raise click.Abort()


def load_pipeline_from_file(file_path: str) -> Pipeline:
    """ファイルからパイプライン定義を読み込む"""
    try:
        import uuid
        from ...core.models.pipeline import JobStatus
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise ValidationError(f"File not found: {file_path}")
        
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            if file_path_obj.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif file_path_obj.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValidationError(f"Unsupported file format: {file_path_obj.suffix}")
        
        # バリデーション
        if 'name' not in data:
            raise ValidationError("Pipeline name is required")
        
        # ジョブデータに必要なフィールドを追加
        jobs_data = []
        for job_data in data.get('jobs', []):
            job_dict = dict(job_data)  # コピーを作成
            # 必要なフィールドを設定
            if 'status' not in job_dict:
                job_dict['status'] = JobStatus.PENDING.value
            if 'dependencies' not in job_dict:
                job_dict['dependencies'] = []
            if 'operations' not in job_dict:
                job_dict['operations'] = []
            if 'timeout_seconds' not in job_dict:
                job_dict['timeout_seconds'] = 3600
            if 'retry_count' not in job_dict:
                job_dict['retry_count'] = 3
            if 'retry_delay_seconds' not in job_dict:
                job_dict['retry_delay_seconds'] = 60
            if 'tags' not in job_dict:
                job_dict['tags'] = {}
            if 'metadata' not in job_dict:
                job_dict['metadata'] = {}
            
            jobs_data.append(job_dict)
        
        # Pipeline データの作成
        pipeline_data = {
            'pipeline_id': str(uuid.uuid4()),  # 自動生成
            'name': data['name'],
            'description': data.get('description', ''),
            'version': data.get('version', '1.0.0'),
            'status': PipelineStatus.DRAFT.value,  # 新規作成時はDRAFT
            'jobs': jobs_data,
            'timeout_seconds': data.get('timeout_seconds', 3600),
            'max_concurrent_jobs': data.get('max_concurrent_jobs', 10),
            'tags': data.get('tags', {}),
            'metadata': data.get('metadata', {})
        }
        
        return Pipeline.from_dict(pipeline_data)
    except Exception as e:
        console.print(f"[red]Failed to load pipeline from file: {e}[/red]")
        raise click.Abort()


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
        # ファイルからパイプライン定義を読み込む
        pipeline = load_pipeline_from_file(file)
        
        # CLI引数でオーバーライド
        if name:
            pipeline.name = name
        if description:
            pipeline.description = description
        
        # 現在のユーザー情報を設定
        pipeline.user_name = os.getenv('USER', 'unknown')
        pipeline.user_id = os.getenv('USER', 'unknown')
        
        if dry_run:
            console.print(f"[yellow]Dry run: Would create pipeline '{pipeline.name}' from {file}[/yellow]")
            
            # バリデーション結果の表示
            if pipeline.validate_dependencies():
                console.print("[green]✓ Dependencies are valid[/green]")
            else:
                console.print("[red]✗ Invalid dependencies detected[/red]")
            
            cycles = pipeline.detect_cycles()
            if cycles:
                console.print(f"[red]✗ Dependency cycles detected: {cycles}[/red]")
            else:
                console.print("[green]✓ No dependency cycles[/green]")
                
        else:
            console.print(f"[green]Creating pipeline '{pipeline.name}' from {file}[/green]")
            
            # リポジトリに保存
            repository = get_pipeline_repository()
            created_pipeline = repository.create_pipeline(pipeline)
            
            console.print(f"[green]✓ Pipeline created successfully[/green]")
            console.print(f"Pipeline ID: {created_pipeline.pipeline_id}")
            
        # 結果の表示
        pipeline_data = {
            "pipeline_id": pipeline.pipeline_id,
            "name": pipeline.name,
            "description": pipeline.description,
            "version": pipeline.version,
            "status": pipeline.status.value,
            "jobs_count": len(pipeline.jobs),
            "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None
        }
        
        if format == 'json':
            console.print(json.dumps(pipeline_data, indent=2, ensure_ascii=False))
        else:
            console.print(yaml.dump(pipeline_data, default_flow_style=False, allow_unicode=True))
            
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
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
        # リポジトリから取得
        repository = get_pipeline_repository()
        
        # ステータスフィルタの準備
        status_filter = None
        if status:
            try:
                status_filter = PipelineStatus(status)
            except ValueError:
                console.print(f"[red]Invalid status: {status}[/red]")
                console.print(f"Valid statuses: {', '.join([s.value for s in PipelineStatus])}")
                raise click.Abort()
        
        # パイプライン一覧を取得
        pipelines = repository.list_pipelines(
            status=status_filter,
            limit=limit if not all else 1000
        )
        
        if not pipelines:
            console.print("[yellow]No pipelines found[/yellow]")
            return
        
        # フォーマットに応じて表示
        if format == 'table':
            table = Table(title="Pipelines", box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Version", style="blue")
            table.add_column("Status", style="yellow")
            table.add_column("Jobs", style="magenta")
            table.add_column("Created", style="blue")
            table.add_column("Updated", style="blue")
            
            for pipeline in pipelines:
                status_color = "green" if pipeline.status == PipelineStatus.ACTIVE else "red"
                table.add_row(
                    pipeline.pipeline_id,
                    pipeline.name,
                    pipeline.version,
                    f"[{status_color}]{pipeline.status.value}[/{status_color}]",
                    str(len(pipeline.jobs)),
                    pipeline.created_at.strftime("%Y-%m-%d %H:%M") if pipeline.created_at else "N/A",
                    pipeline.updated_at.strftime("%Y-%m-%d %H:%M") if pipeline.updated_at else "N/A"
                )
            
            console.print(table)
        elif format == 'json':
            pipelines_data = [
                {
                    "pipeline_id": p.pipeline_id,
                    "name": p.name,
                    "version": p.version,
                    "status": p.status.value,
                    "description": p.description,
                    "jobs_count": len(p.jobs),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "user_name": p.user_name,
                    "tags": p.tags
                }
                for p in pipelines
            ]
            console.print(json.dumps(pipelines_data, indent=2, ensure_ascii=False))
        else:  # yaml
            pipelines_data = [
                {
                    "pipeline_id": p.pipeline_id,
                    "name": p.name,
                    "version": p.version,
                    "status": p.status.value,
                    "description": p.description,
                    "jobs_count": len(p.jobs),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "user_name": p.user_name,
                    "tags": p.tags
                }
                for p in pipelines
            ]
            console.print(yaml.dump(pipelines_data, default_flow_style=False, allow_unicode=True))
            
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
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
        # リポジトリから取得
        repository = get_pipeline_repository()
        pipeline = repository.get_pipeline(pipeline_id)
        
        if not pipeline:
            console.print(f"[red]Pipeline not found: {pipeline_id}[/red]")
            raise click.Abort()
        
        if not force:
            console.print(f"[yellow]Pipeline Details:[/yellow]")
            console.print(f"  ID: {pipeline.pipeline_id}")
            console.print(f"  Name: {pipeline.name}")
            console.print(f"  Version: {pipeline.version}")
            console.print(f"  Jobs: {len(pipeline.jobs)}")
            
            if not click.confirm(f"Are you sure you want to delete pipeline '{pipeline.name}'?"):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return
        
        # パイプラインの削除
        success = repository.delete_pipeline(pipeline_id)
        
        if success:
            console.print(f"[green]✓ Pipeline '{pipeline.name}' deleted successfully[/green]")
        else:
            console.print(f"[red]Failed to delete pipeline: {pipeline_id}[/red]")
            raise click.Abort()
        
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
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
        # リポジトリから取得
        repository = get_pipeline_repository()
        pipeline = repository.get_pipeline(pipeline_id)
        
        if not pipeline:
            console.print(f"[red]Pipeline not found: {pipeline_id}[/red]")
            raise click.Abort()
        
        if format == 'table':
            console.print(f"[bold blue]Pipeline: {pipeline.name}[/bold blue]")
            console.print(f"ID: {pipeline.pipeline_id}")
            console.print(f"Version: {pipeline.version}")
            console.print(f"Status: {pipeline.status.value}")
            console.print(f"Description: {pipeline.description or 'N/A'}")
            console.print(f"Created: {pipeline.created_at.strftime('%Y-%m-%d %H:%M:%S') if pipeline.created_at else 'N/A'}")
            console.print(f"Updated: {pipeline.updated_at.strftime('%Y-%m-%d %H:%M:%S') if pipeline.updated_at else 'N/A'}")
            console.print(f"User: {pipeline.user_name or 'N/A'}")
            console.print(f"Timeout: {pipeline.timeout_seconds}s")
            console.print(f"Max Concurrent Jobs: {pipeline.max_concurrent_jobs}")
            
            # タグの表示
            if pipeline.tags:
                console.print("\n[bold]Tags:[/bold]")
                for key, value in pipeline.tags.items():
                    console.print(f"  {key}: {value}")
            
            # ジョブの表示
            if pipeline.jobs:
                table = Table(title="Jobs", box=box.ROUNDED)
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("Operations", style="magenta")
                table.add_column("Dependencies", style="blue")
                
                for job in pipeline.jobs:
                    status_color = {
                        "completed": "green",
                        "running": "yellow",
                        "failed": "red",
                        "pending": "gray"
                    }.get(job.status.value, "gray")
                    
                    dependencies_str = ", ".join(job.dependencies) if job.dependencies else "None"
                    
                    table.add_row(
                        job.job_id,
                        job.name,
                        f"[{status_color}]{job.status.value}[/{status_color}]",
                        str(len(job.operations)),
                        dependencies_str
                    )
                
                console.print(table)
            else:
                console.print("\n[yellow]No jobs defined[/yellow]")
                
        elif format == 'json':
            pipeline_data = {
                "pipeline_id": pipeline.pipeline_id,
                "name": pipeline.name,
                "version": pipeline.version,
                "description": pipeline.description,
                "status": pipeline.status.value,
                "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
                "updated_at": pipeline.updated_at.isoformat() if pipeline.updated_at else None,
                "user_name": pipeline.user_name,
                "user_id": pipeline.user_id,
                "timeout_seconds": pipeline.timeout_seconds,
                "max_concurrent_jobs": pipeline.max_concurrent_jobs,
                "tags": pipeline.tags,
                "metadata": pipeline.metadata,
                "jobs": [job.to_dict() for job in pipeline.jobs]
            }
            console.print(json.dumps(pipeline_data, indent=2, ensure_ascii=False))
        else:  # yaml
            pipeline_data = {
                "pipeline_id": pipeline.pipeline_id,
                "name": pipeline.name,
                "version": pipeline.version,
                "description": pipeline.description,
                "status": pipeline.status.value,
                "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
                "updated_at": pipeline.updated_at.isoformat() if pipeline.updated_at else None,
                "user_name": pipeline.user_name,
                "user_id": pipeline.user_id,
                "timeout_seconds": pipeline.timeout_seconds,
                "max_concurrent_jobs": pipeline.max_concurrent_jobs,
                "tags": pipeline.tags,
                "metadata": pipeline.metadata,
                "jobs": [job.to_dict() for job in pipeline.jobs]
            }
            console.print(yaml.dump(pipeline_data, default_flow_style=False, allow_unicode=True))
            
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
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
        # リポジトリから取得
        repository = get_pipeline_repository()
        pipeline = repository.get_pipeline(pipeline_id)
        
        if not pipeline:
            console.print(f"[red]Pipeline not found: {pipeline_id}[/red]")
            raise click.Abort()
        
        # 更新対象の確認
        updates = {}
        if file:
            # ファイルから新しい定義を読み込み
            updated_pipeline = load_pipeline_from_file(file)
            # 既存のメタデータを保持
            updated_pipeline.pipeline_id = pipeline.pipeline_id
            updated_pipeline.created_at = pipeline.created_at
            updated_pipeline.user_id = pipeline.user_id
            updated_pipeline.user_name = pipeline.user_name
            # バージョンを更新
            version_parts = pipeline.version.split('.')
            version_parts[-1] = str(int(version_parts[-1]) + 1)
            updated_pipeline.version = '.'.join(version_parts)
            
            updates['file'] = file
        else:
            # 部分更新
            updated_pipeline = pipeline.copy()
            
        if name:
            updated_pipeline.name = name
            updates['name'] = name
        if description:
            updated_pipeline.description = description
            updates['description'] = description
            
        if not updates:
            console.print("[yellow]No updates specified[/yellow]")
            return
            
        if dry_run:
            console.print(f"[yellow]Dry run: Would update pipeline '{pipeline.name}'[/yellow]")
            console.print("Updates:")
            for key, value in updates.items():
                console.print(f"  {key}: {value}")
            
            # バリデーション結果の表示
            if updated_pipeline.validate_dependencies():
                console.print("[green]✓ Dependencies are valid[/green]")
            else:
                console.print("[red]✗ Invalid dependencies detected[/red]")
            
            cycles = updated_pipeline.detect_cycles()
            if cycles:
                console.print(f"[red]✗ Dependency cycles detected: {cycles}[/red]")
            else:
                console.print("[green]✓ No dependency cycles[/green]")
        else:
            console.print(f"[green]Updating pipeline '{pipeline.name}'[/green]")
            console.print("Updates:")
            for key, value in updates.items():
                console.print(f"  {key}: {value}")
            
            # リポジトリで更新
            updated_pipeline = repository.update_pipeline(updated_pipeline)
            
            console.print(f"[green]✓ Pipeline updated successfully[/green]")
            console.print(f"New version: {updated_pipeline.version}")
            
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error updating pipeline: {e}[/red]")
        raise click.Abort() 