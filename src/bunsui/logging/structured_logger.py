"""
Structured logging for Bunsui.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
import traceback
import os


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """構造化ログを出力するロガー"""
    
    def __init__(self, name: str = "bunsui", level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.value))
        
        # ハンドラーが設定されていない場合は追加
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
    
    def log(self, level: LogLevel, message: str, **context):
        """ログを出力"""
        if self._should_log(level):
            log_entry = self._create_log_entry(level, message, context)
            self._logger.log(getattr(logging, level.value), json.dumps(log_entry))
    
    def debug(self, message: str, **context):
        """DEBUGレベルのログを出力"""
        self.log(LogLevel.DEBUG, message, **context)
    
    def info(self, message: str, **context):
        """INFOレベルのログを出力"""
        self.log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context):
        """WARNINGレベルのログを出力"""
        self.log(LogLevel.WARNING, message, **context)
    
    def error(self, message: str, **context):
        """ERRORレベルのログを出力"""
        self.log(LogLevel.ERROR, message, **context)
    
    def critical(self, message: str, **context):
        """CRITICALレベルのログを出力"""
        self.log(LogLevel.CRITICAL, message, **context)
    
    def exception(self, message: str, exception: Exception, **context):
        """例外情報を含むログを出力"""
        context['exception_type'] = type(exception).__name__
        context['exception_message'] = str(exception)
        context['traceback'] = traceback.format_exc()
        
        self.error(message, **context)
    
    def _should_log(self, level: LogLevel) -> bool:
        """ログレベルをチェック"""
        current_level = getattr(logging, self.level.value)
        message_level = getattr(logging, level.value)
        return message_level >= current_level
    
    def _create_log_entry(self, level: LogLevel, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """ログエントリを作成"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.value,
            "logger": self.name,
            "message": message,
            "pid": os.getpid(),
            "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown"
        }
        
        # コンテキスト情報を追加
        if context:
            log_entry["context"] = context
        
        return log_entry
    
    def set_level(self, level: LogLevel):
        """ログレベルを設定"""
        self.level = level
        self._logger.setLevel(getattr(logging, level.value))
    
    def add_context(self, **context):
        """デフォルトコンテキストを追加"""
        # この実装では、各ログ呼び出しでコンテキストを明示的に渡す必要があります
        # より高度な実装では、ThreadLocalを使用してデフォルトコンテキストを管理できます
        pass


class LoggerFactory:
    """ロガーファクトリー"""
    
    _loggers: Dict[str, StructuredLogger] = {}
    
    @classmethod
    def get_logger(cls, name: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
        """ロガーを取得または作成"""
        if name not in cls._loggers:
            cls._loggers[name] = StructuredLogger(name, level)
        
        return cls._loggers[name]
    
    @classmethod
    def set_log_level(cls, name: str, level: LogLevel):
        """ロガーのレベルを設定"""
        if name in cls._loggers:
            cls._loggers[name].set_level(level)
    
    @classmethod
    def get_all_loggers(cls) -> Dict[str, StructuredLogger]:
        """全てのロガーを取得"""
        return cls._loggers.copy()


class PipelineLogger:
    """パイプライン専用ロガー"""
    
    def __init__(self, pipeline_id: str, session_id: Optional[str] = None):
        self.pipeline_id = pipeline_id
        self.session_id = session_id
        self.logger = LoggerFactory.get_logger(f"pipeline.{pipeline_id}")
    
    def log(self, level: LogLevel, message: str, **context):
        """パイプラインログを出力"""
        context['pipeline_id'] = self.pipeline_id
        if self.session_id:
            context['session_id'] = self.session_id
        
        self.logger.log(level, message, **context)
    
    def pipeline_start(self, **context):
        """パイプライン開始ログ"""
        self.info("Pipeline started", **context)
    
    def pipeline_complete(self, **context):
        """パイプライン完了ログ"""
        self.info("Pipeline completed", **context)
    
    def pipeline_failed(self, error: Exception, **context):
        """パイプライン失敗ログ"""
        self.exception("Pipeline failed", error, **context)
    
    def job_start(self, job_id: str, **context):
        """ジョブ開始ログ"""
        context['job_id'] = job_id
        self.info("Job started", **context)
    
    def job_complete(self, job_id: str, **context):
        """ジョブ完了ログ"""
        context['job_id'] = job_id
        self.info("Job completed", **context)
    
    def job_failed(self, job_id: str, error: Exception, **context):
        """ジョブ失敗ログ"""
        context['job_id'] = job_id
        self.exception("Job failed", error, **context)
    
    def info(self, message: str, **context):
        """INFOログ"""
        self.log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context):
        """WARNINGログ"""
        self.log(LogLevel.WARNING, message, **context)
    
    def error(self, message: str, **context):
        """ERRORログ"""
        self.log(LogLevel.ERROR, message, **context)
    
    def debug(self, message: str, **context):
        """DEBUGログ"""
        self.log(LogLevel.DEBUG, message, **context)

    def exception(self, message: str, exception: Exception, **context):
        """例外ログ"""
        self.logger.exception(message, exception, **context)


class SessionLogger:
    """セッション専用ロガー"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = LoggerFactory.get_logger(f"session.{session_id}")
    
    def log(self, level: LogLevel, message: str, **context):
        """セッションログを出力"""
        context['session_id'] = self.session_id
        self.logger.log(level, message, **context)
    
    def session_start(self, **context):
        """セッション開始ログ"""
        self.info("Session started", **context)
    
    def session_complete(self, **context):
        """セッション完了ログ"""
        self.info("Session completed", **context)
    
    def session_failed(self, error: Exception, **context):
        """セッション失敗ログ"""
        self.exception("Session failed", error, **context)
    
    def info(self, message: str, **context):
        """INFOログ"""
        self.log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context):
        """WARNINGログ"""
        self.log(LogLevel.WARNING, message, **context)
    
    def error(self, message: str, **context):
        """ERRORログ"""
        self.log(LogLevel.ERROR, message, **context)
    
    def debug(self, message: str, **context):
        """DEBUGログ"""
        self.log(LogLevel.DEBUG, message, **context)
    
    def exception(self, message: str, exception: Exception, **context):
        """例外ログ"""
        self.logger.exception(message, exception, **context) 