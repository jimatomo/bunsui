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
from datetime import datetime
import time

console = Console()


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
@click.pass_context
def tail(ctx: click.Context, session_id: str, follow: bool, lines: int, since: Optional[str],
          until: Optional[str], level: Optional[str], format: str):
    """セッションのログを表示"""
    try:
        console.print(f"[green]Showing logs for session: {session_id}[/green]")
        
        if since:
            console.print(f"Since: {since}")
        if until:
            console.print(f"Until: {until}")
        if level:
            console.print(f"Level: {level}")
        
        # TODO: Implement actual log retrieval
        log_entries = [
            {
                "timestamp": "2024-01-15T10:30:15Z",
                "level": "INFO",
                "message": "Session started",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:20Z",
                "level": "INFO",
                "message": "Starting job: extract-data",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:25Z",
                "level": "WARNING",
                "message": "Large dataset detected, processing may take longer",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:30Z",
                "level": "INFO",
                "message": "Job completed successfully",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            }
        ]
        
        if level:
            log_entries = [log for log in log_entries if log["level"] == level]
        
        if format == 'text':
            for entry in log_entries[-lines:]:
                timestamp = entry["timestamp"]
                level_color = {
                    "DEBUG": "blue",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red"
                }.get(entry["level"], "white")
                
                console.print(f"[{level_color}]{entry['level']}[/{level_color}] {timestamp} - {entry['message']}")
        elif format == 'json':
            console.print(json.dumps(log_entries[-lines:], indent=2))
        else:  # yaml
            console.print(yaml.dump(log_entries[-lines:], default_flow_style=False))
        
        if follow:
            console.print("[yellow]Following logs (press Ctrl+C to stop)...[/yellow]")
            # TODO: Implement real-time log following
            try:
                while True:
                    time.sleep(1)
                    # Simulate new log entries
                    new_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": "Processing data...",
                        "job_id": "job-2",
                        "pipeline_id": "pipeline-1"
                    }
                    console.print(f"[green]{new_entry['level']}[/green] {new_entry['timestamp']} - {new_entry['message']}")
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/yellow]")
                
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
@click.pass_context
def download(ctx: click.Context, session_id: str, output: Optional[str], format: str,
             since: Optional[str], until: Optional[str], level: Optional[str]):
    """ログをダウンロード"""
    try:
        console.print(f"[green]Downloading logs for session: {session_id}[/green]")
        
        # TODO: Implement actual log download
        log_entries = [
            {
                "timestamp": "2024-01-15T10:30:15Z",
                "level": "INFO",
                "message": "Session started",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:20Z",
                "level": "INFO",
                "message": "Starting job: extract-data",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:25Z",
                "level": "WARNING",
                "message": "Large dataset detected, processing may take longer",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:30Z",
                "level": "INFO",
                "message": "Job completed successfully",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            }
        ]
        
        if level:
            log_entries = [log for log in log_entries if log["level"] == level]
        
        if output:
            with open(output, 'w') as f:
                if format == 'json':
                    json.dump(log_entries, f, indent=2)
                elif format == 'yaml':
                    yaml.dump(log_entries, f, default_flow_style=False)
                elif format == 'csv':
                    import csv
                    writer = csv.DictWriter(f, fieldnames=['timestamp', 'level', 'message', 'job_id', 'pipeline_id'])
                    writer.writeheader()
                    writer.writerows(log_entries)
            
            console.print(f"[green]Logs downloaded to: {output}[/green]")
        else:
            if format == 'json':
                console.print(json.dumps(log_entries, indent=2))
            elif format == 'yaml':
                console.print(yaml.dump(log_entries, default_flow_style=False))
            elif format == 'csv':
                import csv
                import io
                output_buffer = io.StringIO()
                writer = csv.DictWriter(output_buffer, fieldnames=['timestamp', 'level', 'message', 'job_id', 'pipeline_id'])
                writer.writeheader()
                writer.writerows(log_entries)
                console.print(output_buffer.getvalue())
                
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
@click.pass_context
def filter(ctx: click.Context, session_id: str, pattern: Optional[str], case_sensitive: bool,
           lines: int, level: Optional[str], format: str):
    """ログをフィルタリング"""
    try:
        console.print(f"[green]Filtering logs for session: {session_id}[/green]")
        
        if pattern:
            console.print(f"Pattern: {pattern}")
        if level:
            console.print(f"Level: {level}")
        
        # TODO: Implement actual log filtering
        log_entries = [
            {
                "timestamp": "2024-01-15T10:30:15Z",
                "level": "INFO",
                "message": "Session started",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:20Z",
                "level": "INFO",
                "message": "Starting job: extract-data",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:25Z",
                "level": "WARNING",
                "message": "Large dataset detected, processing may take longer",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            },
            {
                "timestamp": "2024-01-15T10:30:30Z",
                "level": "INFO",
                "message": "Job completed successfully",
                "job_id": "job-1",
                "pipeline_id": "pipeline-1"
            }
        ]
        
        # Apply filters
        if level:
            log_entries = [log for log in log_entries if log["level"] == level]
        
        if pattern:
            import re
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            log_entries = [log for log in log_entries if regex.search(log["message"])]
        
        if format == 'text':
            for entry in log_entries[-lines:]:
                timestamp = entry["timestamp"]
                level_color = {
                    "DEBUG": "blue",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red"
                }.get(entry["level"], "white")
                
                console.print(f"[{level_color}]{entry['level']}[/{level_color}] {timestamp} - {entry['message']}")
        elif format == 'json':
            console.print(json.dumps(log_entries[-lines:], indent=2))
        else:  # yaml
            console.print(yaml.dump(log_entries[-lines:], default_flow_style=False))
            
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
        
        # TODO: Implement actual log summary
        summary_data = {
            "session_id": session_id,
            "total_entries": 150,
            "levels": {
                "DEBUG": 20,
                "INFO": 100,
                "WARNING": 15,
                "ERROR": 10,
                "CRITICAL": 5
            },
            "time_range": {
                "start": "2024-01-15T10:30:00Z",
                "end": "2024-01-15T11:30:00Z"
            },
            "jobs": {
                "job-1": {"entries": 50, "errors": 2},
                "job-2": {"entries": 75, "errors": 5},
                "job-3": {"entries": 25, "errors": 3}
            }
        }
        
        if format == 'table':
            console.print(f"[bold blue]Session: {summary_data['session_id']}[/bold blue]")
            console.print(f"Total entries: {summary_data['total_entries']}")
            console.print(f"Time range: {summary_data['time_range']['start']} to {summary_data['time_range']['end']}")
            
            # Level summary
            level_table = Table(title="Log Levels", box=box.ROUNDED)
            level_table.add_column("Level", style="cyan")
            level_table.add_column("Count", style="green")
            
            for level, count in summary_data['levels'].items():
                level_color = {
                    "DEBUG": "blue",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red"
                }.get(level, "white")
                level_table.add_row(f"[{level_color}]{level}[/{level_color}]", str(count))
            
            console.print(level_table)
            
            # Job summary
            job_table = Table(title="Jobs", box=box.ROUNDED)
            job_table.add_column("Job ID", style="cyan")
            job_table.add_column("Entries", style="green")
            job_table.add_column("Errors", style="red")
            
            for job_id, job_data in summary_data['jobs'].items():
                job_table.add_row(job_id, str(job_data['entries']), str(job_data['errors']))
            
            console.print(job_table)
            
        elif format == 'json':
            console.print(json.dumps(summary_data, indent=2))
        else:  # yaml
            console.print(yaml.dump(summary_data, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error showing log summary: {e}[/red]")
        raise click.Abort() 