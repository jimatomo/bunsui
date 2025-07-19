"""
Log management commands for Bunsui CLI.
"""

import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box
import json
import yaml
from datetime import datetime, timezone
import time
import re

from ...core.logging.service import LogService, LogFilter, LogFormat
from ...aws.s3.client import S3StorageManager
from ...core.session.manager import SessionManager
from ...aws.client import AWSClient
from ...core.config.manager import ConfigManager
from ...core.exceptions import ValidationError

console = Console()


def get_log_service() -> LogService:
    """ログサービスのインスタンスを取得"""
    try:
        config_manager = ConfigManager()
        aws_config = config_manager.get_aws_config()
        
        aws_client = AWSClient(
            "s3",
            region_name=aws_config.region,
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            aws_session_token=aws_config.session_token,
            profile_name=aws_config.profile
        )
        
        s3_storage = S3StorageManager(
            bucket_name=f"{aws_config.s3_bucket_prefix}-storage",
            region=aws_config.region
        )
        
        # DynamoDB client for session manager
        dynamodb_client = AWSClient(
            "dynamodb",
            region_name=aws_config.region,
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            aws_session_token=aws_config.session_token,
            profile_name=aws_config.profile
        )
        
        session_manager = SessionManager(
            aws_client=dynamodb_client,
            table_name=f"{aws_config.dynamodb_table_prefix or 'bunsui'}-sessions"
        )
        
        return LogService(s3_storage, session_manager)
    except Exception as e:
        console.print(f"[red]Failed to initialize log service: {e}[/red]")
        raise click.Abort()


def parse_timestamp(timestamp_str: str) -> datetime:
    """ISO形式のタイムスタンプをパース"""
    try:
        # ISO形式の日時をパース
        if 'T' in timestamp_str:
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        else:
            # 日付のみの場合
            return datetime.strptime(timestamp_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValidationError(f"Invalid timestamp format: {timestamp_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)")


def create_log_filter(since: Optional[str], until: Optional[str], level: Optional[str],
                     pattern: Optional[str], case_sensitive: bool) -> LogFilter:
    """ログフィルターを作成"""
    since_dt = None
    until_dt = None
    
    if since:
        since_dt = parse_timestamp(since)
    if until:
        until_dt = parse_timestamp(until)
    
    return LogFilter(
        level=level,
        since=since_dt,
        until=until_dt,
        pattern=pattern,
        case_sensitive=case_sensitive
    )


@click.group()
def logs():
    """ログ管理コマンド"""
    pass


@logs.command()
@click.argument('session_id')
@click.option('--follow', '-f', is_flag=True, help='Follow log updates in real-time')
@click.option('--lines', '-n', type=int, default=50, help='Number of lines to show')
@click.option('--since', help='Show logs since timestamp (ISO format)')
@click.option('--until', help='Show logs until timestamp (ISO format)')
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help='Filter by log level')
@click.option('--format', type=click.Choice(['text', 'json', 'yaml']), default='text', help='Output format')
@click.option('--job-id', help='Filter by job ID')
@click.option('--pipeline-id', help='Filter by pipeline ID')
@click.pass_context
def tail(ctx: click.Context, session_id: str, follow: bool, lines: int, since: Optional[str],
          until: Optional[str], level: Optional[str], format: str, job_id: Optional[str], 
          pipeline_id: Optional[str]):
    """セッションのログを表示"""
    try:
        console.print(f"[green]Showing logs for session: {session_id}[/green]")
        
        # Show filter information
        filters = []
        if since:
            filters.append(f"Since: {since}")
        if until:
            filters.append(f"Until: {until}")
        if level:
            filters.append(f"Level: {level}")
        if job_id:
            filters.append(f"Job ID: {job_id}")
        if pipeline_id:
            filters.append(f"Pipeline ID: {pipeline_id}")
        
        if filters:
            console.print("Filters: " + ", ".join(filters))
        
        # Get log service
        log_service = get_log_service()
        
        # Create log filter
        log_filter = LogFilter(
            level=level,
            since=parse_timestamp(since) if since else None,
            until=parse_timestamp(until) if until else None,
            job_id=job_id,
            pipeline_id=pipeline_id
        )
        
        # Get logs
        log_entries = log_service.get_session_logs(
            session_id=session_id,
            log_filter=log_filter,
            limit=lines
        )
        
        if not log_entries:
            console.print("[yellow]No logs found for the specified criteria[/yellow]")
            return
        
        # Display logs
        if format == 'text':
            for entry in log_entries:
                timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                level_color = {
                    "DEBUG": "blue",
                    "INFO": "green", 
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red bold"
                }.get(entry.level, "white")
                
                # Include job_id and pipeline_id if available
                context_info = []
                if entry.context.get('job_id'):
                    context_info.append(f"job={entry.context['job_id']}")
                if entry.context.get('pipeline_id'):
                    context_info.append(f"pipeline={entry.context['pipeline_id']}")
                
                context_str = f" [{', '.join(context_info)}]" if context_info else ""
                
                console.print(f"[{level_color}]{entry.level:<8}[/{level_color}] {timestamp_str}{context_str} - {entry.message}")
        
        elif format == 'json':
            console.print(json.dumps([entry.raw_data for entry in log_entries], indent=2, default=str))
        
        else:  # yaml
            console.print(yaml.dump([entry.raw_data for entry in log_entries], default_flow_style=False))
        
        # Handle follow mode
        if follow:
            console.print("[yellow]Following logs (press Ctrl+C to stop)...[/yellow]")
            try:
                # Get the last timestamp
                last_timestamp = log_entries[-1].timestamp if log_entries else datetime.min.replace(tzinfo=timezone.utc)
                
                while True:
                    time.sleep(2)  # Poll every 2 seconds
                    
                    # Update filter to get only new logs
                    follow_filter = LogFilter(
                        level=level,
                        since=last_timestamp,
                        until=None,
                        job_id=job_id,
                        pipeline_id=pipeline_id
                    )
                    
                    new_entries = log_service.get_session_logs(
                        session_id=session_id,
                        log_filter=follow_filter,
                        limit=100  # Get up to 100 new entries
                    )
                    
                    # Filter out entries we've already seen
                    new_entries = [e for e in new_entries if e.timestamp > last_timestamp]
                    
                    if new_entries:
                        for entry in new_entries:
                            if format == 'text':
                                timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                                level_color = {
                                    "DEBUG": "blue",
                                    "INFO": "green",
                                    "WARNING": "yellow", 
                                    "ERROR": "red",
                                    "CRITICAL": "red bold"
                                }.get(entry.level, "white")
                                
                                context_info = []
                                if entry.context.get('job_id'):
                                    context_info.append(f"job={entry.context['job_id']}")
                                if entry.context.get('pipeline_id'):
                                    context_info.append(f"pipeline={entry.context['pipeline_id']}")
                                
                                context_str = f" [{', '.join(context_info)}]" if context_info else ""
                                
                                console.print(f"[{level_color}]{entry.level:<8}[/{level_color}] {timestamp_str}{context_str} - {entry.message}")
                            
                            elif format == 'json':
                                console.print(json.dumps(entry.raw_data, indent=2, default=str))
                            
                            else:  # yaml
                                console.print(yaml.dump(entry.raw_data, default_flow_style=False))
                        
                        last_timestamp = new_entries[-1].timestamp
                        
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/yellow]")
                
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error showing logs: {e}[/red]")
        raise click.Abort()


@logs.command()
@click.argument('session_id')
@click.option('--output', '-o', help='Output file path')
@click.option('--format', type=click.Choice(['json', 'yaml', 'csv']), default='json', help='Output format')
@click.option('--since', help='Download logs since timestamp (ISO format)')
@click.option('--until', help='Download logs until timestamp (ISO format)')
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help='Filter by log level')
@click.option('--job-id', help='Filter by job ID')
@click.option('--pipeline-id', help='Filter by pipeline ID')
@click.pass_context
def download(ctx: click.Context, session_id: str, output: Optional[str], format: str,
             since: Optional[str], until: Optional[str], level: Optional[str],
             job_id: Optional[str], pipeline_id: Optional[str]):
    """ログをダウンロード"""
    try:
        console.print(f"[green]Downloading logs for session: {session_id}[/green]")
        
        # Show filter information
        filters = []
        if since:
            filters.append(f"Since: {since}")
        if until:
            filters.append(f"Until: {until}")
        if level:
            filters.append(f"Level: {level}")
        if job_id:
            filters.append(f"Job ID: {job_id}")
        if pipeline_id:
            filters.append(f"Pipeline ID: {pipeline_id}")
        
        if filters:
            console.print("Filters: " + ", ".join(filters))
        
        # Get log service
        log_service = get_log_service()
        
        # Create log filter
        log_filter = LogFilter(
            level=level,
            since=parse_timestamp(since) if since else None,
            until=parse_timestamp(until) if until else None,
            job_id=job_id,
            pipeline_id=pipeline_id
        )
        
        # Convert format string to LogFormat enum
        log_format = LogFormat(format.upper())
        
        # Download logs
        content = log_service.download_session_logs(
            session_id=session_id,
            output_format=log_format,
            log_filter=log_filter
        )
        
        # Determine output file name if not provided
        if output:
            output_file = output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = format
            output_file = f"logs_{session_id}_{timestamp}.{extension}"
        
        # Write to file or stdout
        if output or not output:  # Always write to file for download command
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                console.print(f"[green]Logs downloaded to: {output_file}[/green]")
                console.print(f"[blue]File size: {len(content.encode('utf-8'))} bytes[/blue]")
                
                # Show some statistics
                if content:
                    line_count = content.count('\n') + 1 if content.strip() else 0
                    console.print(f"[blue]Lines: {line_count}[/blue]")
                
            except IOError as e:
                console.print(f"[red]Failed to write to file: {e}[/red]")
                # Fallback to stdout
                console.print("[yellow]Displaying content to stdout instead:[/yellow]")
                console.print(content)
        
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error downloading logs: {e}[/red]")
        raise click.Abort()


@logs.command()
@click.argument('session_id')
@click.option('--pattern', '-p', help='Search pattern (regex)')
@click.option('--case-sensitive', is_flag=True, help='Case-sensitive search')
@click.option('--lines', '-n', type=int, default=50, help='Number of lines to show')
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help='Filter by log level')
@click.option('--format', type=click.Choice(['text', 'json', 'yaml']), default='text', help='Output format')
@click.option('--since', help='Show logs since timestamp (ISO format)')
@click.option('--until', help='Show logs until timestamp (ISO format)')
@click.option('--job-id', help='Filter by job ID')
@click.option('--pipeline-id', help='Filter by pipeline ID')
@click.pass_context
def filter(ctx: click.Context, session_id: str, pattern: Optional[str], case_sensitive: bool,
           lines: int, level: Optional[str], format: str, since: Optional[str],
           until: Optional[str], job_id: Optional[str], pipeline_id: Optional[str]):
    """ログをフィルタリング"""
    try:
        console.print(f"[green]Filtering logs for session: {session_id}[/green]")
        
        # Show filter information
        filters = []
        if pattern:
            sensitivity = "case-sensitive" if case_sensitive else "case-insensitive"
            filters.append(f"Pattern: {pattern} ({sensitivity})")
        if level:
            filters.append(f"Level: {level}")
        if since:
            filters.append(f"Since: {since}")
        if until:
            filters.append(f"Until: {until}")
        if job_id:
            filters.append(f"Job ID: {job_id}")
        if pipeline_id:
            filters.append(f"Pipeline ID: {pipeline_id}")
        
        if filters:
            console.print("Filters: " + ", ".join(filters))
        
        # Get log service
        log_service = get_log_service()
        
        # Create log filter
        log_filter = LogFilter(
            level=level,
            since=parse_timestamp(since) if since else None,
            until=parse_timestamp(until) if until else None,
            pattern=pattern,
            case_sensitive=case_sensitive,
            job_id=job_id,
            pipeline_id=pipeline_id
        )
        
        # Get filtered logs
        log_entries = log_service.get_session_logs(
            session_id=session_id,
            log_filter=log_filter,
            limit=None  # Don't limit initially, we'll apply lines limit after
        )
        
        if not log_entries:
            console.print("[yellow]No logs found matching the specified criteria[/yellow]")
            return
        
        # Apply lines limit to the most recent entries
        if lines > 0:
            log_entries = log_entries[-lines:]
        
        console.print(f"[blue]Found {len(log_entries)} matching log entries[/blue]")
        
        # Display results
        if format == 'text':
            for entry in log_entries:
                timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                level_color = {
                    "DEBUG": "blue",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red bold"
                }.get(entry.level, "white")
                
                # Include job_id and pipeline_id if available
                context_info = []
                if entry.context.get('job_id'):
                    context_info.append(f"job={entry.context['job_id']}")
                if entry.context.get('pipeline_id'):
                    context_info.append(f"pipeline={entry.context['pipeline_id']}")
                
                context_str = f" [{', '.join(context_info)}]" if context_info else ""
                
                # Highlight pattern matches if pattern was provided
                message = entry.message
                if pattern:
                    try:
                        flags = 0 if case_sensitive else re.IGNORECASE
                        regex = re.compile(pattern, flags)
                        # Highlight matches with yellow background
                        message = regex.sub(lambda m: f"[yellow on black]{m.group()}[/yellow on black]", message)
                    except re.error:
                        # Invalid regex, show original message
                        pass
                
                console.print(f"[{level_color}]{entry.level:<8}[/{level_color}] {timestamp_str}{context_str} - {message}")
        
        elif format == 'json':
            console.print(json.dumps([entry.raw_data for entry in log_entries], indent=2, default=str))
        
        else:  # yaml
            console.print(yaml.dump([entry.raw_data for entry in log_entries], default_flow_style=False))
            
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except re.error as e:
        console.print(f"[red]Invalid regex pattern: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error filtering logs: {e}[/red]")
        raise click.Abort()


@logs.command()
@click.argument('session_id')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
@click.pass_context
def summary(ctx: click.Context, session_id: str, format: str):
    """ログサマリーを表示"""
    try:
        console.print(f"[green]Log summary for session: {session_id}[/green]")
        
        # Get log service
        log_service = get_log_service()
        
        # Get log summary
        log_summary = log_service.get_log_summary(session_id)
        
        if format == 'table':
            console.print(f"[bold blue]Session: {log_summary.session_id}[/bold blue]")
            console.print(f"Total entries: {log_summary.total_entries}")
            
            if log_summary.time_range['start'] and log_summary.time_range['end']:
                console.print(f"Time range: {log_summary.time_range['start']} to {log_summary.time_range['end']}")
                
                # Calculate duration if we have both start and end times
                if log_summary.first_entry and log_summary.last_entry:
                    duration = log_summary.last_entry - log_summary.first_entry
                    total_seconds = int(duration.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if hours > 0:
                        duration_str = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        duration_str = f"{minutes}m {seconds}s"
                    else:
                        duration_str = f"{seconds}s"
                    
                    console.print(f"Duration: {duration_str}")
            else:
                console.print("Time range: No logs found")
            
            # Level summary
            if log_summary.levels:
                level_table = Table(title="Log Levels", box=box.ROUNDED)
                level_table.add_column("Level", style="cyan")
                level_table.add_column("Count", style="green")
                level_table.add_column("Percentage", style="blue")
                
                for level, count in sorted(log_summary.levels.items()):
                    percentage = (count / log_summary.total_entries * 100) if log_summary.total_entries > 0 else 0
                    level_color = {
                        "DEBUG": "blue",
                        "INFO": "green",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "red bold"
                    }.get(level, "white")
                    
                    level_table.add_row(
                        f"[{level_color}]{level}[/{level_color}]",
                        str(count),
                        f"{percentage:.1f}%"
                    )
                
                console.print(level_table)
            
            # Job summary
            if log_summary.jobs:
                job_table = Table(title="Jobs", box=box.ROUNDED)
                job_table.add_column("Job ID", style="cyan")
                job_table.add_column("Entries", style="green")
                job_table.add_column("Errors", style="red")
                job_table.add_column("Error Rate", style="yellow")
                
                for job_id, job_data in sorted(log_summary.jobs.items()):
                    entries = job_data['entries']
                    errors = job_data['errors']
                    error_rate = (errors / entries * 100) if entries > 0 else 0
                    
                    error_rate_color = "red" if error_rate > 10 else "yellow" if error_rate > 1 else "green"
                    
                    job_table.add_row(
                        job_id,
                        str(entries),
                        str(errors),
                        f"[{error_rate_color}]{error_rate:.1f}%[/{error_rate_color}]"
                    )
                
                console.print(job_table)
            
            # Health summary
            if log_summary.total_entries > 0:
                error_count = log_summary.levels.get('ERROR', 0) + log_summary.levels.get('CRITICAL', 0)
                warning_count = log_summary.levels.get('WARNING', 0)
                
                health_table = Table(title="Health Summary", box=box.ROUNDED)
                health_table.add_column("Metric", style="cyan")
                health_table.add_column("Value", style="white")
                health_table.add_column("Status", style="white")
                
                # Error rate
                error_rate = (error_count / log_summary.total_entries * 100)
                error_status = "[red]High[/red]" if error_rate > 5 else "[yellow]Medium[/yellow]" if error_rate > 1 else "[green]Low[/green]"
                health_table.add_row("Error Rate", f"{error_rate:.1f}%", error_status)
                
                # Warning rate
                warning_rate = (warning_count / log_summary.total_entries * 100)
                warning_status = "[red]High[/red]" if warning_rate > 20 else "[yellow]Medium[/yellow]" if warning_rate > 5 else "[green]Low[/green]"
                health_table.add_row("Warning Rate", f"{warning_rate:.1f}%", warning_status)
                
                # Overall health
                if error_rate > 5 or warning_rate > 20:
                    overall_health = "[red]Poor[/red]"
                elif error_rate > 1 or warning_rate > 10:
                    overall_health = "[yellow]Fair[/yellow]"
                else:
                    overall_health = "[green]Good[/green]"
                
                health_table.add_row("Overall Health", "", overall_health)
                
                console.print(health_table)
            
        elif format == 'json':
            # Convert summary to dictionary
            summary_dict = {
                "session_id": log_summary.session_id,
                "total_entries": log_summary.total_entries,
                "levels": log_summary.levels,
                "time_range": log_summary.time_range,
                "jobs": log_summary.jobs
            }
            console.print(json.dumps(summary_dict, indent=2, default=str))
            
        else:  # yaml
            summary_dict = {
                "session_id": log_summary.session_id,
                "total_entries": log_summary.total_entries,
                "levels": log_summary.levels,
                "time_range": log_summary.time_range,
                "jobs": log_summary.jobs
            }
            console.print(yaml.dump(summary_dict, default_flow_style=False))
            
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error showing log summary: {e}[/red]")
        raise click.Abort() 