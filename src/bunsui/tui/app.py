"""
TUI application for bunsui.

This module provides the main TUI application using Textual framework
for pipeline management and monitoring.
"""

from typing import List, Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Tree,
    DataTable,
    Static,
    Button,
    Label,
)
from textual import work

from bunsui.core.models.session import Session, SessionStatus
from bunsui.core.models.pipeline import Pipeline, Job, Operation
from bunsui.core.session.manager import SessionManager
from bunsui.aws.dynamodb.repository import SessionRepository, PipelineRepository
from bunsui.aws.stepfunctions.client import StepFunctionsClient
from bunsui.aws.client import AWSClient


class PipelineTree(Tree):
    """Pipeline tree widget."""

    def __init__(self, id: str = "pipeline-tree"):
        """Initialize pipeline tree."""
        super().__init__("Pipelines", id=id)
        self.pipelines: List[Pipeline] = []

    def update_pipelines(self, pipelines: List[Pipeline]) -> None:
        """Update pipeline tree."""
        self.pipelines = pipelines
        self.clear()

        for pipeline in pipelines:
            pipeline_node = self.root.add(pipeline.name, data=pipeline)

            for job in pipeline.jobs:
                job_node = pipeline_node.add(
                    f"{job.name} ({job.status.value})", data=job
                )

                for operation in job.operations:
                    job_node.add(
                        f"{operation.name} ({operation.config.operation_type.value})",
                        data=operation,
                    )


class SessionTable(DataTable):
    """Session table widget."""

    def __init__(self, id: str = "session-table"):
        """Initialize session table."""
        super().__init__(id=id)
        self.add_columns(
            "Session ID", "Pipeline", "Status", "Created", "Duration", "Progress"
        )

    def update_sessions(self, sessions: List[Session]) -> None:
        """Update session table."""
        self.clear()

        for session in sessions:
            duration = session.get_duration() if session.get_duration() else "N/A"
            progress = f"{session.get_progress_percentage():.1f}%"

            self.add_row(
                session.session_id[:8],
                session.pipeline_id,
                session.status.value,
                session.created_at.strftime("%Y-%m-%d %H:%M"),
                str(duration) if isinstance(duration, (int, float)) else duration,
                progress,
            )


class LogViewer(Static):
    """Log viewer widget."""

    def __init__(self, id: str = "log-viewer"):
        """Initialize log viewer."""
        super().__init__("No session selected", id=id)
        self.current_session_id: Optional[str] = None

    def update_logs(self, session_id: str, logs: List[str]) -> None:
        """Update log viewer."""
        self.current_session_id = session_id
        if logs:
            self.update("\n".join(logs))
        else:
            self.update("No logs available")

    def clear_logs(self) -> None:
        """Clear log viewer."""
        self.current_session_id = None
        self.update("No session selected")


class ControlPanel(Container):
    """Control panel widget."""

    def __init__(self, id: str = "control-panel"):
        """Initialize control panel."""
        super().__init__(id=id)
        self.session_manager: Optional[SessionManager] = None

    def compose(self) -> ComposeResult:
        """Compose control panel."""
        yield Label("Control Panel", classes="title")
        yield Button("Start Pipeline", id="start-pipeline", variant="primary")
        yield Button("Stop Pipeline", id="stop-pipeline", variant="error")
        yield Button("Refresh", id="refresh", variant="default")
        yield Label("Status: Ready", id="status-label")


class BunsuiApp(App):
    """Main bunsui TUI application."""

    CSS = """
    #pipeline-tree {
        width: 30%;
        height: 100%;
        border: solid green;
    }

    #session-table {
        width: 70%;
        height: 50%;
        border: solid blue;
    }

    #log-viewer {
        width: 70%;
        height: 50%;
        border: solid red;
    }

    #control-panel {
        width: 100%;
        height: 10%;
        border: solid yellow;
    }

    .title {
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    Button {
        margin: 1;
    }
    """

    def __init__(self):
        """Initialize bunsui app."""
        super().__init__()
        self.session_repository: Optional[SessionRepository] = None
        self.pipeline_repository: Optional[PipelineRepository] = None
        self.step_functions_client: Optional[StepFunctionsClient] = None
        self.session_manager: Optional[SessionManager] = None

        # UI state
        self.current_pipeline: Optional[Pipeline] = None
        self.current_session: Optional[Session] = None
        self.sessions: List[Session] = []
        self.pipelines: List[Pipeline] = []

    def compose(self) -> ComposeResult:
        """Compose the app."""
        yield Header()

        with Container():
            with Horizontal():
                yield PipelineTree(id="pipeline-tree")

                with Vertical():
                    yield SessionTable(id="session-table")
                    yield LogViewer(id="log-viewer")

            yield ControlPanel(id="control-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = "Bunsui - Data Pipeline Management"
        self.sub_title = "AWS-based TUI Pipeline Orchestrator"

        # Initialize repositories and clients
        self.initialize_services()

        # Load initial data
        self.load_data()

    def initialize_services(self) -> None:
        """Initialize AWS services."""
        try:
            # Create AWS client for DynamoDB
            aws_client = AWSClient("dynamodb")
            
            self.session_repository = SessionRepository(region="us-east-1")
            self.pipeline_repository = PipelineRepository(region="us-east-1")
            self.step_functions_client = StepFunctionsClient(region="us-east-1")
            self.session_manager = SessionManager(aws_client)

            # Update status
            status_label = self.query_one("#status-label", Label)
            status_label.update("Status: Connected to AWS")
        except Exception as e:
            status_label = self.query_one("#status-label", Label)
            status_label.update(f"Status: Error - {str(e)}")

    def load_data(self) -> None:
        """Load initial data."""
        self.load_pipelines()
        self.load_sessions()

    @work(thread=True)
    def load_pipelines(self) -> None:
        """Load pipelines asynchronously."""
        try:
            if self.pipeline_repository:
                # For now, load from mock data
                # In real implementation, this would load from DynamoDB
                self.pipelines = self.get_mock_pipelines()
                
                # Update UI
                pipeline_tree = self.query_one("#pipeline-tree", PipelineTree)
                pipeline_tree.update_pipelines(self.pipelines)
        except Exception as e:
            self.notify(f"Error loading pipelines: {str(e)}", severity="error")

    @work(thread=True)
    def load_sessions(self) -> None:
        """Load sessions asynchronously."""
        try:
            if self.session_repository:
                # For now, load from mock data
                # In real implementation, this would load from DynamoDB
                self.sessions = self.get_mock_sessions()
                
                # Update UI
                session_table = self.query_one("#session-table", SessionTable)
                session_table.update_sessions(self.sessions)
        except Exception as e:
            self.notify(f"Error loading sessions: {str(e)}", severity="error")

    def get_mock_pipelines(self) -> List[Pipeline]:
        """Get mock pipeline data."""
        from bunsui.core.models.pipeline import (
            LambdaOperation,
            ECSOperation,
            OperationConfig,
            OperationType,
        )

        # Create mock operations
        lambda_op = LambdaOperation(
            operation_id="op-1",
            name="Data Processing",
            function_arn="arn:aws:lambda:us-east-1:123456789012:function:data-processor",
        )

        ecs_op = ECSOperation(
            operation_id="op-2",
            name="Model Training",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition:model-trainer",
            cluster_name="ml-cluster",
        )

        # Create mock jobs
        job1 = Job(
            job_id="job-1", 
            name="Data Ingestion", 
            operations=[lambda_op],
            description="Data ingestion job",
            started_at=None,
            completed_at=None,
            execution_arn=None,
            state_machine_arn=None,
            timeout_seconds=3600,
            retry_count=3,
            retry_delay_seconds=60,
            error_message=None,
            error_code=None
        )

        job2 = Job(
            job_id="job-2",
            name="Model Training",
            operations=[ecs_op],
            dependencies=["job-1"],
            description="Model training job",
            started_at=None,
            completed_at=None,
            execution_arn=None,
            state_machine_arn=None,
            timeout_seconds=3600,
            retry_count=3,
            retry_delay_seconds=60,
            error_message=None,
            error_code=None
        )

        # Create mock pipeline
        pipeline = Pipeline(
            pipeline_id="pipeline-1",
            name="ML Pipeline",
            description="Machine learning pipeline for data processing and model training",
            jobs=[job1, job2],
            version="1.0.0",
            timeout_seconds=3600,
            max_concurrent_jobs=10,
            user_id=None,
            user_name=None
        )

        return [pipeline]

    def get_mock_sessions(self) -> List[Session]:
        """Get mock session data."""
        session1 = Session.create(
            pipeline_id="pipeline-1", user_id="user-1", pipeline_name="ML Pipeline"
        )
        session1.status = SessionStatus.RUNNING
        session1.total_jobs = 2
        session1.completed_jobs = 1

        session2 = Session.create(
            pipeline_id="pipeline-1", user_id="user-1", pipeline_name="ML Pipeline"
        )
        session2.status = SessionStatus.COMPLETED
        session2.total_jobs = 2
        session2.completed_jobs = 2

        return [session1, session2]

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        data = node.data

        if isinstance(data, Pipeline):
            self.current_pipeline = data
            self.notify(f"Selected pipeline: {data.name}")
        elif isinstance(data, Job):
            self.notify(f"Selected job: {data.name}")
        elif isinstance(data, Operation):
            self.notify(f"Selected operation: {data.name}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle table row selection."""
        row_key = event.row_key
        if row_key:
            # Find session by ID
            session_id = str(row_key)
            for session in self.sessions:
                if session.session_id.startswith(session_id):
                    self.current_session = session
                    self.load_session_logs(session)
                    break

    def load_session_logs(self, session: Session) -> None:
        """Load logs for a session."""
        # Mock log data
        logs = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session {session.session_id} started",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pipeline {session.pipeline_id} initialized",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Job job-1 started",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Operation Data Processing completed",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Job job-1 completed",
        ]

        log_viewer = self.query_one("#log-viewer", LogViewer)
        log_viewer.update_logs(session.session_id, logs)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "start-pipeline":
            self.start_pipeline()
        elif button_id == "stop-pipeline":
            self.stop_pipeline()
        elif button_id == "refresh":
            self.refresh_data()

    def start_pipeline(self) -> None:
        """Start a pipeline."""
        if not self.current_pipeline:
            self.notify("No pipeline selected", severity="warning")
            return

        try:
            if self.session_manager:
                session = self.session_manager.create_session(
                    pipeline_id=self.current_pipeline.pipeline_id,
                    metadata={"user_id": "current-user"},
                )

                self.notify(f"Started pipeline: {self.current_pipeline.name}")
                self.load_sessions()  # Refresh sessions
        except Exception as e:
            self.notify(f"Error starting pipeline: {str(e)}", severity="error")

    def stop_pipeline(self) -> None:
        """Stop a pipeline."""
        if not self.current_session:
            self.notify("No session selected", severity="warning")
            return

        try:
            if self.session_manager:
                self.session_manager.cancel_session(self.current_session.session_id)
                self.notify(f"Stopped session: {self.current_session.session_id}")
                self.load_sessions()  # Refresh sessions
        except Exception as e:
            self.notify(f"Error stopping pipeline: {str(e)}", severity="error")

    def refresh_data(self) -> None:
        """Refresh all data."""
        self.load_pipelines()
        self.load_sessions()
        self.notify("Data refreshed")

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "r":
            self.refresh_data()
        elif event.key == "q":
            self.exit()


def main():
    """Main entry point."""
    app = BunsuiApp()
    app.run()


if __name__ == "__main__":
    main()
