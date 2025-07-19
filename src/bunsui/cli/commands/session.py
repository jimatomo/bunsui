
"""
Session management commands for Bunsui CLI.
"""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box
import json
import yaml
from datetime import datetime
import os

from ...core.session.manager import SessionManager
from ...core.session.repository import SessionRepository
from ...core.models.session import SessionStatus
from ...core.pipeline.repository import PipelineRepository
from ...aws.client import AWSClient
from ...core.config.manager import ConfigManager
from ...core.exceptions import ValidationError, SessionError
from ...aws.exceptions import AWSError

console = Console()


def get_session_manager() -> SessionManager:
    """セッションマネージャーのインスタンスを取得"""
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
        
        table_name = f"{aws_config.dynamodb_table_prefix}-sessions"
        return SessionManager(aws_client, table_name)
    except Exception as e:
        console.print(f"[red]Failed to initialize session manager: {e}[/red]")
        raise click.Abort()


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


@click.group()
def session():
    """セッション管理コマンド"""
    pass


@session.command()
@click.argument('pipeline_id')
@click.option('--parameters', '-p', multiple=True, help='Pipeline parameters (key=value)')
@click.option('--wait', '-w', is_flag=True, help='Wait for completion')
@click.option('--timeout', '-t', type=int, help='Timeout in seconds')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def start(ctx: click.Context, pipeline_id: str, parameters: tuple, wait: bool, 
          timeout: Optional[int], format: str):
    """セッションを開始"""
    try:
        # Parse parameters
        param_dict = {}
        for param in parameters:
            if '=' in param:
                key, value = param.split('=', 1)
                param_dict[key] = value
        
        console.print(f"[green]Starting session for pipeline: {pipeline_id}[/green]")
        
        if param_dict:
            console.print("Parameters:")
            for key, value in param_dict.items():
                console.print(f"  {key}: {value}")
        
        # パイプラインの存在確認
        pipeline_repository = get_pipeline_repository()
        pipeline = pipeline_repository.get_pipeline(pipeline_id)
        
        if not pipeline:
            console.print(f"[red]Pipeline not found: {pipeline_id}[/red]")
            raise click.Abort()
        
        # セッションの作成
        session_manager = get_session_manager()
        
        # ユーザー情報の取得
        user_name = os.getenv('USER', 'unknown')
        user_id = os.getenv('USER_ID', user_name)  # USER_IDが設定されていない場合はUSERを使用
        
        # メタデータの準備
        metadata = {
            "parameters": param_dict,
            "timeout": timeout,
            "wait": wait
        }
        
        # セッションの作成
        session = session_manager.create_session(
            pipeline_id=pipeline_id,
            metadata=metadata,
            total_steps=len(pipeline.jobs),
            user_id=user_id,
            user_name=user_name
        )
        
        # セッションの開始
        started_session = session_manager.start_session(session.session_id)
        
        console.print(f"[green]✓ Session started successfully[/green]")
        console.print(f"Session ID: {started_session.session_id}")
        
        # Wait機能の実装
        if wait:
            console.print("[yellow]Waiting for session completion...[/yellow]")
            # ここで実際の待機ロジックを実装
            # 現在は簡単なステータス表示のみ
            console.print("[yellow]Note: Wait functionality will be implemented with Step Functions integration[/yellow]")
        
        # 結果の表示
        session_data = {
            "session_id": started_session.session_id,
            "pipeline_id": started_session.pipeline_id,
            "pipeline_name": pipeline.name,
            "status": started_session.status.value,
            "parameters": param_dict,
            "started_at": started_session.started_at.isoformat() if started_session.started_at else None,
            "timeout": timeout,
            "total_jobs": started_session.total_jobs,
            "user_name": started_session.user_name
        }
        
        if format == 'table':
            table = Table(title="Session Started", box=box.ROUNDED)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in session_data.items():
                if key == 'parameters':
                    value = json.dumps(value) if value else '{}'
                table.add_row(key, str(value))
            
            console.print(table)
        elif format == 'json':
            console.print(json.dumps(session_data, indent=2, ensure_ascii=False))
        else:  # yaml
            console.print(yaml.dump(session_data, default_flow_style=False, allow_unicode=True))
            
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error starting session: {e}[/red]")
        raise click.Abort()


@session.command()
@click.argument('session_id')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def status(ctx: click.Context, session_id: str, format: str):
    """セッションのステータスを表示"""
    try:
        # セッションの取得
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise click.Abort()
        
        # パイプライン情報の取得
        pipeline_repository = get_pipeline_repository()
        pipeline = pipeline_repository.get_pipeline(session.pipeline_id)
        
        # セッション統計の取得
        stats = session_manager.get_session_statistics(session_id)
        
        if format == 'table':
            console.print(f"[bold blue]Session: {session.session_id}[/bold blue]")
            console.print(f"Pipeline: {session.pipeline_id}")
            console.print(f"Pipeline Name: {pipeline.name if pipeline else 'N/A'}")
            console.print(f"Status: {session.status.value}")
            console.print(f"Progress: {stats['progress']['completion_percentage']:.1f}%")
            console.print(f"Started: {session.started_at.strftime('%Y-%m-%d %H:%M:%S') if session.started_at else 'N/A'}")
            console.print(f"Completed: {session.completed_at.strftime('%Y-%m-%d %H:%M:%S') if session.completed_at else 'N/A'}")
            console.print(f"User: {session.user_name or 'N/A'}")
            console.print(f"Total Jobs: {session.total_jobs}")
            console.print(f"Completed Jobs: {session.completed_jobs}")
            console.print(f"Failed Jobs: {session.failed_jobs}")
            
            if session.error_message:
                console.print(f"[red]Error: {session.error_message}[/red]")
            
            # 実行時間の表示
            if 'current_runtime_seconds' in stats:
                runtime = stats['current_runtime_seconds']
                console.print(f"Current Runtime: {runtime:.1f}s")
            elif 'total_runtime_seconds' in stats:
                runtime = stats['total_runtime_seconds']
                console.print(f"Total Runtime: {runtime:.1f}s")
            
            # チェックポイントの表示
            if session.checkpoints:
                console.print(f"\n[bold]Recent Checkpoints:[/bold]")
                # 最新5件のチェックポイントを表示
                recent_checkpoints = sorted(session.checkpoints, key=lambda x: x.created_at, reverse=True)[:5]
                
                checkpoint_table = Table(title="Checkpoints", box=box.ROUNDED)
                checkpoint_table.add_column("Time", style="cyan")
                checkpoint_table.add_column("Job", style="green")
                checkpoint_table.add_column("Type", style="yellow")
                checkpoint_table.add_column("Message", style="blue")
                
                for checkpoint in recent_checkpoints:
                    checkpoint_table.add_row(
                        checkpoint.created_at.strftime('%H:%M:%S'),
                        checkpoint.job_id,
                        checkpoint.checkpoint_type.value,
                        checkpoint.message or "N/A"
                    )
                
                console.print(checkpoint_table)
                
        elif format == 'json':
            session_data = {
                "session_id": session.session_id,
                "pipeline_id": session.pipeline_id,
                "pipeline_name": pipeline.name if pipeline else None,
                "status": session.status.value,
                "progress": stats['progress'],
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "error_message": session.error_message,
                "error_code": session.error_code,
                "user_name": session.user_name,
                "configuration": session.configuration,
                "tags": session.tags,
                "checkpoints": [
                    {
                        "checkpoint_id": cp.checkpoint_id,
                        "type": cp.checkpoint_type.value,
                        "job_id": cp.job_id,
                        "created_at": cp.created_at.isoformat(),
                        "message": cp.message
                    }
                    for cp in session.checkpoints
                ],
                "statistics": stats
            }
            console.print(json.dumps(session_data, indent=2, ensure_ascii=False))
        else:  # yaml
            session_data = {
                "session_id": session.session_id,
                "pipeline_id": session.pipeline_id,
                "pipeline_name": pipeline.name if pipeline else None,
                "status": session.status.value,
                "progress": stats['progress'],
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "error_message": session.error_message,
                "error_code": session.error_code,
                "user_name": session.user_name,
                "configuration": session.configuration,
                "tags": session.tags,
                "checkpoints": [
                    {
                        "checkpoint_id": cp.checkpoint_id,
                        "type": cp.checkpoint_type.value,
                        "job_id": cp.job_id,
                        "created_at": cp.created_at.isoformat(),
                        "message": cp.message
                    }
                    for cp in session.checkpoints
                ],
                "statistics": stats
            }
            console.print(yaml.dump(session_data, default_flow_style=False, allow_unicode=True))
            
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error getting session status: {e}[/red]")
        raise click.Abort()


@session.command()
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.option('--status', help='Filter by status')
@click.option('--pipeline', help='Filter by pipeline ID')
@click.option('--limit', type=int, default=50, help='Maximum number of sessions to show')
@click.pass_context
def list(ctx: click.Context, format: str, status: Optional[str], pipeline: Optional[str], limit: int):
    """セッション一覧を表示"""
    try:
        # セッション管理の取得
        session_manager = get_session_manager()
        
        # ステータスフィルタの準備
        status_filter = None
        if status:
            try:
                status_filter = SessionStatus(status)
            except ValueError:
                console.print(f"[red]Invalid status: {status}[/red]")
                console.print(f"Valid statuses: {', '.join([s.value for s in SessionStatus])}")
                raise click.Abort()
        
        # セッション一覧の取得
        sessions = session_manager.list_sessions(
            pipeline_id=pipeline,
            status=status_filter,
            limit=limit
        )
        
        # パイプライン名を取得するためのリポジトリ
        pipeline_repository = get_pipeline_repository()
        
        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return
        
        if format == 'table':
            table = Table(title="Sessions", box=box.ROUNDED)
            table.add_column("ID", style="cyan", width=36, no_wrap=True)
            table.add_column("Pipeline", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Progress", style="blue")
            table.add_column("Started", style="magenta")
            table.add_column("Completed", style="red")
            
            for session in sessions:
                status_color = {
                    "completed": "green",
                    "failed": "red",
                    "running": "yellow",
                    "paused": "blue",
                    "cancelled": "gray"
                }.get(session.status.value, "gray")
                
                progress = session.get_progress_percentage()
                completed_time = session.completed_at.strftime('%Y-%m-%d %H:%M:%S') if session.completed_at else "N/A"
                
                # パイプライン名を取得
                pipeline_name = session.pipeline_name
                if not pipeline_name:
                    try:
                        # パイプラインリポジトリから名前を取得
                        pipeline_obj = pipeline_repository.get_pipeline(session.pipeline_id)
                        if pipeline_obj:
                            pipeline_name = pipeline_obj.name
                        else:
                            pipeline_name = session.pipeline_id
                    except:
                        pipeline_name = session.pipeline_id
                
                table.add_row(
                    session.session_id,
                    pipeline_name,
                    f"[{status_color}]{session.status.value}[/{status_color}]",
                    f"{progress:.1f}%",
                    session.started_at.strftime('%Y-%m-%d %H:%M:%S') if session.started_at else "N/A",
                    completed_time
                )
            
            console.print(table)
        elif format == 'json':
            sessions_data = [
                {
                    "session_id": s.session_id,
                    "pipeline_id": s.pipeline_id,
                    "pipeline_name": s.pipeline_name,
                    "status": s.status.value,
                    "progress": s.get_progress_percentage(),
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "user_name": s.user_name,
                    "total_jobs": s.total_jobs,
                    "completed_jobs": s.completed_jobs,
                    "failed_jobs": s.failed_jobs
                }
                for s in sessions
            ]
            console.print(json.dumps(sessions_data, indent=2, ensure_ascii=False))
        else:  # yaml
            sessions_data = [
                {
                    "session_id": s.session_id,
                    "pipeline_id": s.pipeline_id,
                    "pipeline_name": s.pipeline_name,
                    "status": s.status.value,
                    "progress": s.get_progress_percentage(),
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "user_name": s.user_name,
                    "total_jobs": s.total_jobs,
                    "completed_jobs": s.completed_jobs,
                    "failed_jobs": s.failed_jobs
                }
                for s in sessions
            ]
            console.print(yaml.dump(sessions_data, default_flow_style=False, allow_unicode=True))
            
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error listing sessions: {e}[/red]")
        raise click.Abort()


@session.command()
@click.argument('session_id')
@click.pass_context
def pause(ctx: click.Context, session_id: str):
    """セッションを一時停止"""
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise click.Abort()
        
        # セッションの一時停止
        paused_session = session_manager.pause_session(session_id)
        
        console.print(f"[green]✓ Session paused successfully[/green]")
        console.print(f"Session ID: {paused_session.session_id}")
        console.print(f"Status: {paused_session.status.value}")
        
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error pausing session: {e}[/red]")
        raise click.Abort()


@session.command()
@click.argument('session_id')
@click.pass_context
def resume(ctx: click.Context, session_id: str):
    """セッションを再開"""
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise click.Abort()
        
        # セッションの再開
        resumed_session = session_manager.resume_session(session_id)
        
        console.print(f"[green]✓ Session resumed successfully[/green]")
        console.print(f"Session ID: {resumed_session.session_id}")
        console.print(f"Status: {resumed_session.status.value}")
        
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error resuming session: {e}[/red]")
        raise click.Abort()


@session.command()
@click.argument('session_id')
@click.option('--force', is_flag=True, help='Force cancellation without confirmation')
@click.pass_context
def cancel(ctx: click.Context, session_id: str, force: bool):
    """セッションをキャンセル"""
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise click.Abort()
        
        if not force:
            console.print(f"[yellow]Session Details:[/yellow]")
            console.print(f"  ID: {session.session_id}")
            console.print(f"  Pipeline: {session.pipeline_id}")
            console.print(f"  Status: {session.status.value}")
            console.print(f"  Progress: {session.get_progress_percentage():.1f}%")
            
            if not click.confirm(f"Are you sure you want to cancel session '{session.session_id}'?"):
                console.print("[yellow]Cancellation cancelled[/yellow]")
                return
        
        # セッションのキャンセル
        cancelled_session = session_manager.cancel_session(session_id)
        
        console.print(f"[green]✓ Session cancelled successfully[/green]")
        console.print(f"Session ID: {cancelled_session.session_id}")
        console.print(f"Status: {cancelled_session.status.value}")
        
    except SessionError as e:
        console.print(f"[red]Session error: {e}[/red]")
        raise click.Abort()
    except AWSError as e:
        console.print(f"[red]AWS error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error cancelling session: {e}[/red]")
        raise click.Abort() 