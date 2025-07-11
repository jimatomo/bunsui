"""
Interactive mode for Bunsui CLI.
"""

import click
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.table import Table
from rich import box
from datetime import datetime
import cmd

console = Console()


class BunsuiInteractive(cmd.Cmd):
    """Interactive shell for Bunsui CLI."""
    
    intro = """
    [bold blue]Bunsui Interactive Mode[/bold blue]
    
    Welcome to Bunsui! Type 'help' or '?' to list commands.
    Type 'exit' or 'quit' to exit.
    """
    
    prompt = "[bold green]bunsui>[/bold green] "
    
    def __init__(self, ctx: click.Context):
        super().__init__()
        self.ctx = ctx
        self.current_pipeline = None
        self.current_session = None
        
    def do_pipeline(self, arg):
        """Pipeline management commands.
        
        Usage:
            pipeline list                    - List all pipelines
            pipeline create <name>          - Create a new pipeline
            pipeline show <id>              - Show pipeline details
            pipeline delete <id>            - Delete a pipeline
        """
        args = arg.split()
        if not args:
            console.print("[red]Error: Pipeline command requires arguments[/red]")
            return
        
        command = args[0]
        
        if command == "list":
            self._pipeline_list()
        elif command == "create":
            if len(args) < 2:
                console.print("[red]Error: Pipeline name required[/red]")
                return
            self._pipeline_create(args[1])
        elif command == "show":
            if len(args) < 2:
                console.print("[red]Error: Pipeline ID required[/red]")
                return
            self._pipeline_show(args[1])
        elif command == "delete":
            if len(args) < 2:
                console.print("[red]Error: Pipeline ID required[/red]")
                return
            self._pipeline_delete(args[1])
        else:
            console.print(f"[red]Unknown pipeline command: {command}[/red]")
    
    def do_session(self, arg):
        """Session management commands.
        
        Usage:
            session list                     - List all sessions
            session start <pipeline_id>     - Start a new session
            session status <id>             - Show session status
            session pause <id>              - Pause a session
            session resume <id>             - Resume a session
            session cancel <id>             - Cancel a session
        """
        args = arg.split()
        if not args:
            console.print("[red]Error: Session command requires arguments[/red]")
            return
        
        command = args[0]
        
        if command == "list":
            self._session_list()
        elif command == "start":
            if len(args) < 2:
                console.print("[red]Error: Pipeline ID required[/red]")
                return
            self._session_start(args[1])
        elif command == "status":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._session_status(args[1])
        elif command == "pause":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._session_pause(args[1])
        elif command == "resume":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._session_resume(args[1])
        elif command == "cancel":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._session_cancel(args[1])
        else:
            console.print(f"[red]Unknown session command: {command}[/red]")
    
    def do_logs(self, arg):
        """Log management commands.
        
        Usage:
            logs tail <session_id>          - Show session logs
            logs download <session_id>      - Download session logs
            logs filter <session_id>        - Filter session logs
            logs summary <session_id>       - Show log summary
        """
        args = arg.split()
        if not args:
            console.print("[red]Error: Logs command requires arguments[/red]")
            return
        
        command = args[0]
        
        if command == "tail":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._logs_tail(args[1])
        elif command == "download":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._logs_download(args[1])
        elif command == "filter":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._logs_filter(args[1])
        elif command == "summary":
            if len(args) < 2:
                console.print("[red]Error: Session ID required[/red]")
                return
            self._logs_summary(args[1])
        else:
            console.print(f"[red]Unknown logs command: {command}[/red]")
    
    def do_config(self, arg):
        """Configuration management commands.
        
        Usage:
            config list                     - List all configuration
            config get <key>               - Get configuration value
            config set <key> <value>       - Set configuration value
            config delete <key>            - Delete configuration
            config validate                - Validate configuration
            config export                  - Export configuration
        """
        args = arg.split()
        if not args:
            console.print("[red]Error: Config command requires arguments[/red]")
            return
        
        command = args[0]
        
        if command == "list":
            self._config_list()
        elif command == "get":
            if len(args) < 2:
                console.print("[red]Error: Config key required[/red]")
                return
            self._config_get(args[1])
        elif command == "set":
            if len(args) < 3:
                console.print("[red]Error: Config key and value required[/red]")
                return
            self._config_set(args[1], args[2])
        elif command == "delete":
            if len(args) < 2:
                console.print("[red]Error: Config key required[/red]")
                return
            self._config_delete(args[1])
        elif command == "validate":
            self._config_validate()
        elif command == "export":
            self._config_export()
        else:
            console.print(f"[red]Unknown config command: {command}[/red]")
    
    def do_status(self, arg):
        """Show current status and system information."""
        self._show_status()
    
    def do_clear(self, arg):
        """Clear the screen."""
        console.clear()
    
    def do_exit(self, arg):
        """Exit the interactive mode."""
        console.print("[yellow]Goodbye![/yellow]")
        return True
    
    def do_quit(self, arg):
        """Exit the interactive mode."""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Exit on EOF (Ctrl+D)."""
        return self.do_exit(arg)
    
    def default(self, line):
        """Handle unknown commands."""
        console.print(f"[red]Unknown command: {line}[/red]")
        console.print("Type 'help' for available commands.")
    
    def _pipeline_list(self):
        """List pipelines interactively."""
        console.print("[green]Listing pipelines...[/green]")
        
        # TODO: Implement actual pipeline listing
        pipelines = [
            {"id": "pipeline-1", "name": "ETL Pipeline", "status": "active"},
            {"id": "pipeline-2", "name": "Data Processing", "status": "inactive"}
        ]
        
        table = Table(title="Pipelines", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status", style="yellow")
        
        for pipeline in pipelines:
            status_color = "green" if pipeline["status"] == "active" else "red"
            table.add_row(
                pipeline["id"],
                pipeline["name"],
                f"[{status_color}]{pipeline['status']}[/{status_color}]"
            )
        
        console.print(table)
    
    def _pipeline_create(self, name: str):
        """Create pipeline interactively."""
        console.print(f"[green]Creating pipeline: {name}[/green]")
        
        # Interactive prompts
        description = Prompt.ask("Description (optional)")
        timeout = IntPrompt.ask("Timeout (seconds)", default=3600)
        
        # TODO: Implement actual pipeline creation
        console.print(f"[green]Pipeline '{name}' created successfully[/green]")
    
    def _pipeline_show(self, pipeline_id: str):
        """Show pipeline details interactively."""
        console.print(f"[green]Showing pipeline: {pipeline_id}[/green]")
        
        # TODO: Implement actual pipeline details
        pipeline_data = {
            "id": pipeline_id,
            "name": "Sample Pipeline",
            "description": "A sample pipeline",
            "status": "active",
            "jobs": [
                {"id": "job-1", "name": "Extract", "status": "completed"},
                {"id": "job-2", "name": "Transform", "status": "running"}
            ]
        }
        
        console.print(f"ID: {pipeline_data['id']}")
        console.print(f"Name: {pipeline_data['name']}")
        console.print(f"Status: {pipeline_data['status']}")
        
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
    
    def _pipeline_delete(self, pipeline_id: str):
        """Delete pipeline interactively."""
        if Confirm.ask(f"Are you sure you want to delete pipeline '{pipeline_id}'?"):
            console.print(f"[green]Deleting pipeline: {pipeline_id}[/green]")
            # TODO: Implement actual pipeline deletion
            console.print(f"[green]Pipeline '{pipeline_id}' deleted successfully[/green]")
        else:
            console.print("[yellow]Deletion cancelled[/yellow]")
    
    def _session_list(self):
        """List sessions interactively."""
        console.print("[green]Listing sessions...[/green]")
        
        # TODO: Implement actual session listing
        sessions = [
            {"id": "session-1", "pipeline_id": "pipeline-1", "status": "running"},
            {"id": "session-2", "pipeline_id": "pipeline-2", "status": "completed"}
        ]
        
        table = Table(title="Sessions", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Pipeline", style="green")
        table.add_column("Status", style="yellow")
        
        for session in sessions:
            status_color = "green" if session["status"] == "completed" else "yellow"
            table.add_row(
                session["id"],
                session["pipeline_id"],
                f"[{status_color}]{session['status']}[/{status_color}]"
            )
        
        console.print(table)
    
    def _session_start(self, pipeline_id: str):
        """Start session interactively."""
        console.print(f"[green]Starting session for pipeline: {pipeline_id}[/green]")
        
        # Interactive prompts
        wait = Confirm.ask("Wait for completion?")
        timeout = IntPrompt.ask("Timeout (seconds)", default=3600)
        
        # TODO: Implement actual session start
        session_id = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        console.print(f"[green]Session started: {session_id}[/green]")
        self.current_session = session_id
    
    def _session_status(self, session_id: str):
        """Show session status interactively."""
        console.print(f"[green]Session status: {session_id}[/green]")
        
        # TODO: Implement actual session status
        status_data = {
            "id": session_id,
            "status": "running",
            "progress": 65,
            "started_at": "2024-01-15T10:30:00Z"
        }
        
        console.print(f"Status: {status_data['status']}")
        console.print(f"Progress: {status_data['progress']}%")
        console.print(f"Started: {status_data['started_at']}")
    
    def _session_pause(self, session_id: str):
        """Pause session interactively."""
        if Confirm.ask(f"Are you sure you want to pause session '{session_id}'?"):
            console.print(f"[green]Pausing session: {session_id}[/green]")
            # TODO: Implement actual session pause
            console.print(f"[green]Session '{session_id}' paused successfully[/green]")
        else:
            console.print("[yellow]Pause cancelled[/yellow]")
    
    def _session_resume(self, session_id: str):
        """Resume session interactively."""
        console.print(f"[green]Resuming session: {session_id}[/green]")
        # TODO: Implement actual session resume
        console.print(f"[green]Session '{session_id}' resumed successfully[/green]")
    
    def _session_cancel(self, session_id: str):
        """Cancel session interactively."""
        if Confirm.ask(f"Are you sure you want to cancel session '{session_id}'?"):
            console.print(f"[green]Cancelling session: {session_id}[/green]")
            # TODO: Implement actual session cancellation
            console.print(f"[green]Session '{session_id}' cancelled successfully[/green]")
        else:
            console.print("[yellow]Cancellation cancelled[/yellow]")
    
    def _logs_tail(self, session_id: str):
        """Show logs interactively."""
        console.print(f"[green]Showing logs for session: {session_id}[/green]")
        
        # TODO: Implement actual log retrieval
        log_entries = [
            {"timestamp": "2024-01-15T10:30:15Z", "level": "INFO", "message": "Session started"},
            {"timestamp": "2024-01-15T10:30:20Z", "level": "INFO", "message": "Processing data..."}
        ]
        
        for entry in log_entries:
            level_color = "green" if entry["level"] == "INFO" else "yellow"
            console.print(f"[{level_color}]{entry['level']}[/{level_color}] {entry['timestamp']} - {entry['message']}")
    
    def _logs_download(self, session_id: str):
        """Download logs interactively."""
        output_file = Prompt.ask("Output file path", default=f"logs_{session_id}.json")
        console.print(f"[green]Downloading logs for session: {session_id}[/green]")
        # TODO: Implement actual log download
        console.print(f"[green]Logs downloaded to: {output_file}[/green]")
    
    def _logs_filter(self, session_id: str):
        """Filter logs interactively."""
        pattern = Prompt.ask("Search pattern (regex)")
        level = Prompt.ask("Log level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO")
        console.print(f"[green]Filtering logs for session: {session_id}[/green]")
        # TODO: Implement actual log filtering
        console.print(f"Pattern: {pattern}, Level: {level}")
    
    def _logs_summary(self, session_id: str):
        """Show log summary interactively."""
        console.print(f"[green]Log summary for session: {session_id}[/green]")
        
        # TODO: Implement actual log summary
        summary_data = {
            "total_entries": 150,
            "levels": {"INFO": 100, "WARNING": 30, "ERROR": 20}
        }
        
        console.print(f"Total entries: {summary_data['total_entries']}")
        for level, count in summary_data['levels'].items():
            console.print(f"{level}: {count}")
    
    def _config_list(self):
        """List configuration interactively."""
        console.print("[green]Listing configuration...[/green]")
        
        # TODO: Implement actual config listing
        configs = [
            {"key": "aws.region", "value": "us-east-1"},
            {"key": "logging.level", "value": "INFO"}
        ]
        
        table = Table(title="Configuration", box=box.ROUNDED)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        
        for config in configs:
            table.add_row(config["key"], config["value"])
        
        console.print(table)
    
    def _config_get(self, key: str):
        """Get configuration interactively."""
        console.print(f"[green]Getting config: {key}[/green]")
        # TODO: Implement actual config retrieval
        console.print(f"Value: sample_value")
    
    def _config_set(self, key: str, value: str):
        """Set configuration interactively."""
        console.print(f"[green]Setting config: {key} = {value}[/green]")
        # TODO: Implement actual config setting
        console.print(f"[green]Configuration updated successfully[/green]")
    
    def _config_delete(self, key: str):
        """Delete configuration interactively."""
        if Confirm.ask(f"Are you sure you want to delete config '{key}'?"):
            console.print(f"[green]Deleting config: {key}[/green]")
            # TODO: Implement actual config deletion
            console.print(f"[green]Configuration '{key}' deleted successfully[/green]")
        else:
            console.print("[yellow]Deletion cancelled[/yellow]")
    
    def _config_validate(self):
        """Validate configuration interactively."""
        console.print("[green]Validating configuration...[/green]")
        # TODO: Implement actual config validation
        console.print("[green]Configuration is valid[/green]")
    
    def _config_export(self):
        """Export configuration interactively."""
        output_file = Prompt.ask("Output file path", default="bunsui_config.yaml")
        console.print(f"[green]Exporting configuration to: {output_file}[/green]")
        # TODO: Implement actual config export
        console.print(f"[green]Configuration exported successfully[/green]")
    
    def _show_status(self):
        """Show current status."""
        console.print("[bold blue]Bunsui Status[/bold blue]")
        
        # TODO: Implement actual status retrieval
        status_data = {
            "version": "1.0.0",
            "aws_region": "us-east-1",
            "current_pipeline": self.current_pipeline or "None",
            "current_session": self.current_session or "None",
            "active_sessions": 2,
            "total_pipelines": 5
        }
        
        table = Table(title="System Status", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in status_data.items():
            table.add_row(key, str(value))
        
        console.print(table)


def start_interactive(ctx: click.Context):
    """Start interactive mode."""
    try:
        console.print(Panel.fit(
            "[bold blue]Welcome to Bunsui Interactive Mode[/bold blue]\n"
            "Type 'help' for available commands.\n"
            "Type 'exit' or 'quit' to exit.",
            title="Bunsui"
        ))
        
        shell = BunsuiInteractive(ctx)
        shell.cmdloop()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interactive mode interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Error in interactive mode: {e}[/red]")
        raise click.Abort() 