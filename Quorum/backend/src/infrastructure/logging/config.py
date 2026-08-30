"""
Advanced structured logging configuration using structlog.
Provides context-aware, correlation-tracked logging with JSON output for production.
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor
from pythonjsonlogger import jsonlogger


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application-level context to all log entries."""
    event_dict["app"] = "no-oversight"
    event_dict["service"] = "backend"
    return event_dict


def censor_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Censor sensitive data from logs (API keys, tokens, passwords)."""
    sensitive_keys = {"api_key", "token", "password", "secret", "authorization"}
    
    def _censor_dict(d: Dict) -> Dict:
        """Recursively censor sensitive keys in dictionaries."""
        censored = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                censored[key] = "***REDACTED***"
            elif isinstance(value, dict):
                censored[key] = _censor_dict(value)
            elif isinstance(value, list):
                censored[key] = [_censor_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                censored[key] = value
        return censored
    
    return _censor_dict(event_dict)


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    log_file: str = None
) -> None:
    """
    Configure structured logging with structlog.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON format (production). If False, use colored console (dev)
        log_file: Optional file path for file logging with rotation
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        stream=sys.stdout,
    )
    
    # Silence noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_app_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        censor_sensitive_data,
    ]
    
    if json_logs:
        # Production: JSON output for log aggregation systems
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console output for humans
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Optional: Add file handler with rotation
    if log_file:
        from logging.handlers import RotatingFileHandler
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        
        # JSON format for file logs
        json_formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            rename_fields={
                "levelname": "level",
                "name": "logger",
                "asctime": "timestamp"
            }
        )
        file_handler.setFormatter(json_formatter)
        
        # Add to root logger
        logging.root.addHandler(file_handler)


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Bound logger instance with context support
    """
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str) -> None:
    """
    Bind a correlation ID to the current context.
    All subsequent logs will include this ID.
    
    Args:
        correlation_id: Unique request/conversation identifier
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def unbind_correlation_id() -> None:
    """Remove correlation ID from context."""
    structlog.contextvars.unbind_contextvars("correlation_id")


def bind_context(**kwargs) -> None:
    """
    Bind arbitrary context to the current logger context.
    Useful for adding user_id, agent_type, conversation_id, etc.
    
    Example:
        bind_context(user_id="user123", agent_type="claude-sonnet")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys) -> None:
    """
    Remove specific keys from the logger context.
    
    Args:
        *keys: Context keys to remove
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()

