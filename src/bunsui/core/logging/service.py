"""
Log service for managing log retrieval and processing.
"""

import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Iterator, Union
from dataclasses import dataclass
from enum import Enum

from ...aws.s3.client import S3StorageManager
from ...core.session.manager import SessionManager
from ...core.exceptions import ValidationError
from ...logging.structured_logger import LogLevel


class LogFormat(Enum):
    """Log output format enumeration."""
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"


@dataclass
class LogEntry:
    """Log entry data structure."""
    timestamp: datetime
    level: str
    message: str
    logger: str
    pid: int
    hostname: str
    context: Dict[str, Any]
    raw_data: Dict[str, Any]

    @classmethod
    def from_json_line(cls, json_line: str) -> 'LogEntry':
        """Create LogEntry from JSON line."""
        try:
            data = json.loads(json_line.strip())
            
            # Parse timestamp
            timestamp_str = data.get('timestamp', '')
            if timestamp_str:
                # Handle both ISO format and datetime objects
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)
            
            return cls(
                timestamp=timestamp,
                level=data.get('level', 'INFO'),
                message=data.get('message', ''),
                logger=data.get('logger', 'unknown'),
                pid=data.get('pid', 0),
                hostname=data.get('hostname', 'unknown'),
                context=data.get('context', {}),
                raw_data=data
            )
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback for malformed entries
            return cls(
                timestamp=datetime.now(timezone.utc),
                level='ERROR',
                message=f'Failed to parse log entry: {json_line}',
                logger='log_parser',
                pid=0,
                hostname='unknown',
                context={'parse_error': str(e)},
                raw_data={}
            )


@dataclass
class LogFilter:
    """Log filtering criteria."""
    level: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    pattern: Optional[str] = None
    case_sensitive: bool = False
    job_id: Optional[str] = None
    pipeline_id: Optional[str] = None


@dataclass
class LogSummary:
    """Log summary statistics."""
    session_id: str
    total_entries: int
    levels: Dict[str, int]
    time_range: Dict[str, Optional[str]]
    jobs: Dict[str, Dict[str, int]]
    first_entry: Optional[datetime]
    last_entry: Optional[datetime]


class LogService:
    """Service for log retrieval and management."""
    
    def __init__(self, s3_storage_manager: S3StorageManager, session_manager: SessionManager):
        """
        Initialize log service.
        
        Args:
            s3_storage_manager: S3 storage manager instance
            session_manager: Session manager instance
        """
        self.s3_storage = s3_storage_manager
        self.session_manager = session_manager
    
    def get_session_logs(
        self,
        session_id: str,
        log_filter: Optional[LogFilter] = None,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Get logs for a session.
        
        Args:
            session_id: Session ID
            log_filter: Optional filtering criteria
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries
            
        Raises:
            ValidationError: If session is not found
        """
        # Validate session exists
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError(f"Session {session_id} not found")
        
        # Get log files from S3
        log_objects = self.s3_storage.list_session_logs(session_id)
        
        entries = []
        
        # Process each log file
        for log_obj in log_objects:
            log_content = self._get_log_file_content(log_obj['Key'])
            if log_content:
                file_entries = self._parse_log_content(log_content)
                entries.extend(file_entries)
        
        # Apply filters
        if log_filter:
            entries = self._apply_filter(entries, log_filter)
        
        # Sort by timestamp
        entries.sort(key=lambda x: x.timestamp)
        
        # Apply limit
        if limit:
            entries = entries[-limit:]
        
        return entries
    
    def tail_session_logs(
        self,
        session_id: str,
        log_filter: Optional[LogFilter] = None,
        lines: int = 50
    ) -> Iterator[LogEntry]:
        """
        Tail logs for a session in real-time.
        
        Args:
            session_id: Session ID
            log_filter: Optional filtering criteria
            lines: Number of recent lines to show initially
            
        Yields:
            Log entries as they arrive
        """
        # Get initial logs
        initial_logs = self.get_session_logs(session_id, log_filter, lines)
        
        # Yield initial logs
        for entry in initial_logs:
            yield entry
        
        # Keep track of last seen timestamp
        last_timestamp = initial_logs[-1].timestamp if initial_logs else datetime.min.replace(tzinfo=timezone.utc)
        
        # TODO: Implement real-time log tailing
        # This would require polling S3 or using S3 event notifications
        # For now, we'll just return the initial logs
        
    def download_session_logs(
        self,
        session_id: str,
        output_format: LogFormat = LogFormat.JSON,
        log_filter: Optional[LogFilter] = None
    ) -> str:
        """
        Download and format session logs.
        
        Args:
            session_id: Session ID
            output_format: Output format
            log_filter: Optional filtering criteria
            
        Returns:
            Formatted log content
        """
        entries = self.get_session_logs(session_id, log_filter)
        
        if output_format == LogFormat.JSON:
            return json.dumps([entry.raw_data for entry in entries], indent=2, ensure_ascii=False)
        elif output_format == LogFormat.YAML:
            import yaml
            return yaml.dump([entry.raw_data for entry in entries], default_flow_style=False, allow_unicode=True)
        elif output_format == LogFormat.CSV:
            import csv
            import io
            output = io.StringIO()
            
            if entries:
                fieldnames = ['timestamp', 'level', 'message', 'logger', 'pid', 'hostname']
                # Add context fields
                context_fields = set()
                for entry in entries:
                    context_fields.update(entry.context.keys())
                fieldnames.extend(sorted(context_fields))
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for entry in entries:
                    row = {
                        'timestamp': entry.timestamp.isoformat(),
                        'level': entry.level,
                        'message': entry.message,
                        'logger': entry.logger,
                        'pid': entry.pid,
                        'hostname': entry.hostname,
                    }
                    row.update(entry.context)
                    writer.writerow(row)
            
            return output.getvalue()
        else:  # TEXT format
            lines = []
            for entry in entries:
                timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f"{entry.level} {timestamp_str} - {entry.message}")
            return '\n'.join(lines)
    
    def get_log_summary(self, session_id: str) -> LogSummary:
        """
        Get log summary for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Log summary
        """
        entries = self.get_session_logs(session_id)
        
        # Calculate statistics
        levels = {}
        jobs = {}
        first_entry = None
        last_entry = None
        
        for entry in entries:
            # Count levels
            level = entry.level
            levels[level] = levels.get(level, 0) + 1
            
            # Count by job
            job_id = entry.context.get('job_id', 'unknown')
            if job_id not in jobs:
                jobs[job_id] = {'entries': 0, 'errors': 0}
            jobs[job_id]['entries'] += 1
            
            if level in ['ERROR', 'CRITICAL']:
                jobs[job_id]['errors'] += 1
            
            # Track time range
            if first_entry is None or entry.timestamp < first_entry:
                first_entry = entry.timestamp
            if last_entry is None or entry.timestamp > last_entry:
                last_entry = entry.timestamp
        
        time_range = {
            'start': first_entry.isoformat() if first_entry else None,
            'end': last_entry.isoformat() if last_entry else None
        }
        
        return LogSummary(
            session_id=session_id,
            total_entries=len(entries),
            levels=levels,
            time_range=time_range,
            jobs=jobs,
            first_entry=first_entry,
            last_entry=last_entry
        )
    
    def _get_log_file_content(self, s3_key: str) -> Optional[str]:
        """Get content of a log file from S3."""
        try:
            response = self.s3_storage.client.get_object(
                self.s3_storage.bucket_name,
                s3_key
            )
            if response and 'Body' in response:
                return response['Body'].read().decode('utf-8')
        except Exception:
            # Log file might not exist or be accessible
            pass
        return None
    
    def _parse_log_content(self, content: str) -> List[LogEntry]:
        """Parse log content into LogEntry objects."""
        entries = []
        
        for line in content.strip().split('\n'):
            if line.strip():
                entry = LogEntry.from_json_line(line)
                entries.append(entry)
        
        return entries
    
    def _apply_filter(self, entries: List[LogEntry], log_filter: LogFilter) -> List[LogEntry]:
        """Apply filtering criteria to log entries."""
        filtered_entries = entries
        
        # Filter by level
        if log_filter.level:
            filtered_entries = [e for e in filtered_entries if e.level == log_filter.level]
        
        # Filter by time range
        if log_filter.since:
            filtered_entries = [e for e in filtered_entries if e.timestamp >= log_filter.since]
        
        if log_filter.until:
            filtered_entries = [e for e in filtered_entries if e.timestamp <= log_filter.until]
        
        # Filter by pattern
        if log_filter.pattern:
            flags = 0 if log_filter.case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(log_filter.pattern, flags)
                filtered_entries = [e for e in filtered_entries if regex.search(e.message)]
            except re.error:
                # Invalid regex, skip pattern filtering
                pass
        
        # Filter by job ID
        if log_filter.job_id:
            filtered_entries = [e for e in filtered_entries 
                             if e.context.get('job_id') == log_filter.job_id]
        
        # Filter by pipeline ID
        if log_filter.pipeline_id:
            filtered_entries = [e for e in filtered_entries 
                             if e.context.get('pipeline_id') == log_filter.pipeline_id]
        
        return filtered_entries 