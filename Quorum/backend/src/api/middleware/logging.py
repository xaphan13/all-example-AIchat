"""
FastAPI middleware for automatic request/response logging with correlation IDs.
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.infrastructure.logging.config import get_logger, bind_context, clear_context


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests and responses.
    Automatically adds correlation IDs and tracks request duration.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: set[str] = None
    ):
        """
        Initialize logging middleware.
        
        Args:
            app: ASGI application
            exclude_paths: Set of paths to exclude from logging (e.g., {"/health", "/metrics"})
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or {"/health"}
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process the request and log relevant information.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response object
        """
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generate or extract correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            request.headers.get("X-Request-ID", str(uuid.uuid4()))
        )
        
        # Bind correlation ID and request context
        bind_context(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        
        # Log incoming request
        logger.info(
            "request_started",
            query_params=dict(request.query_params) if request.query_params else None,
            user_agent=request.headers.get("user-agent"),
        )
        
        # Track request duration
        start_time = time.perf_counter()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log response
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log error
            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise
            
        finally:
            # Clean up context for this request
            clear_context()


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """
    Additional middleware for detailed performance metrics.
    Use this for monitoring slow endpoints and bottlenecks.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        slow_request_threshold_ms: float = 1000.0
    ):
        """
        Initialize performance logging middleware.
        
        Args:
            app: ASGI application
            slow_request_threshold_ms: Log warning if request takes longer than this
        """
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log performance metrics."""
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        if duration_ms > self.slow_request_threshold_ms:
            logger.warning(
                "slow_request_detected",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                threshold_ms=self.slow_request_threshold_ms,
            )
        
        return response

