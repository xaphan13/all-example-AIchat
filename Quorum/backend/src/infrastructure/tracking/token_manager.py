"""
Token tracking manager for centralized token usage monitoring.
Manages sessions, aggregates usage statistics, and provides analytics.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from src.core.token_models import TokenUsage, SessionUsage, get_model_pricing
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class TokenTrackingManager:
    """
    Centralized manager for token usage tracking and analytics.
    
    Maintains session-based tracking, provides real-time statistics,
    and supports cost analysis across models and agents.
    """
    
    def __init__(self):
        """Initialize the token tracking manager."""
        self.sessions: Dict[str, SessionUsage] = {}
        self.global_usage: List[TokenUsage] = []
        self._lock = asyncio.Lock()
    
    async def record_usage(
        self,
        usage: TokenUsage,
        session_id: Optional[str] = None
    ):
        """
        Record a token usage event.
        
        Args:
            usage: TokenUsage object to record
            session_id: Optional session ID to associate usage with
        """
        async with self._lock:
            # Add to global usage
            self.global_usage.append(usage)
            
            # Add to session if session_id provided
            if session_id:
                if session_id not in self.sessions:
                    self.sessions[session_id] = SessionUsage(
                        session_id=session_id,
                        start_time=usage.timestamp
                    )
                self.sessions[session_id].add_usage(usage)
            
            logger.debug(
                "usage_recorded",
                session_id=session_id,
                agent_id=usage.agent_id,
                model=usage.model_id,
                tokens=usage.total_tokens,
                cost=usage.cost
            )
    
    async def create_session(self, session_id: str) -> SessionUsage:
        """
        Create a new tracking session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            SessionUsage object
        """
        async with self._lock:
            if session_id in self.sessions:
                logger.warning(
                    "session_already_exists",
                    session_id=session_id
                )
                return self.sessions[session_id]
            
            session = SessionUsage(
                session_id=session_id,
                start_time=datetime.utcnow()
            )
            self.sessions[session_id] = session
            
            logger.info(
                "session_created",
                session_id=session_id
            )
            
            return session
    
    async def get_session(self, session_id: str) -> Optional[SessionUsage]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionUsage object or None if not found
        """
        return self.sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """
        Close a session and finalize its statistics.
        
        Args:
            session_id: Session identifier
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.end_time = datetime.utcnow()
                logger.info(
                    "session_closed",
                    session_id=session_id,
                    total_cost=session.total_cost,
                    total_tokens=session.total_tokens
                )
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Get a summary of session usage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary dictionary or None if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        return session.get_summary()
    
    async def get_global_stats(self) -> Dict:
        """
        Get global usage statistics across all sessions.
        
        Returns:
            Dictionary with global statistics
        """
        async with self._lock:
            if not self.global_usage:
                return {
                    "total_requests": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "by_model": {},
                    "by_agent": {}
                }
            
            # Aggregate by model
            by_model = defaultdict(lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "request_count": 0
            })
            
            # Aggregate by agent
            by_agent = defaultdict(lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "request_count": 0
            })
            
            total_input = 0
            total_output = 0
            total_cost = 0.0
            
            for usage in self.global_usage:
                # Global totals
                total_input += usage.input_tokens
                total_output += usage.output_tokens
                total_cost += usage.cost
                
                # By model
                model_stats = by_model[usage.model_id]
                model_stats["input_tokens"] += usage.input_tokens
                model_stats["output_tokens"] += usage.output_tokens
                model_stats["total_tokens"] += usage.total_tokens
                model_stats["cost"] += usage.cost
                model_stats["request_count"] += 1
                
                # By agent
                agent_id = usage.agent_id or "unknown"
                agent_stats = by_agent[agent_id]
                agent_stats["input_tokens"] += usage.input_tokens
                agent_stats["output_tokens"] += usage.output_tokens
                agent_stats["total_tokens"] += usage.total_tokens
                agent_stats["cost"] += usage.cost
                agent_stats["request_count"] += 1
            
            return {
                "total_requests": len(self.global_usage),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "total_cost": round(total_cost, 6),
                "by_model": dict(by_model),
                "by_agent": dict(by_agent),
                "session_count": len(self.sessions)
            }
    
    async def get_recent_usage(
        self,
        limit: int = 100,
        model_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> List[TokenUsage]:
        """
        Get recent usage records with optional filtering.
        
        Args:
            limit: Maximum number of records to return
            model_id: Optional filter by model
            agent_id: Optional filter by agent
            
        Returns:
            List of TokenUsage objects
        """
        async with self._lock:
            filtered = self.global_usage
            
            if model_id:
                filtered = [u for u in filtered if u.model_id == model_id]
            
            if agent_id:
                filtered = [u for u in filtered if u.agent_id == agent_id]
            
            # Return most recent first
            return sorted(
                filtered,
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]
    
    async def get_usage_by_time_range(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> List[TokenUsage]:
        """
        Get usage records within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range (defaults to now)
            
        Returns:
            List of TokenUsage objects
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        async with self._lock:
            return [
                usage for usage in self.global_usage
                if start_time <= usage.timestamp <= end_time
            ]
    
    async def calculate_projected_costs(
        self,
        model_id: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> Dict:
        """
        Calculate projected costs for a given workload.
        
        Args:
            model_id: Model identifier
            estimated_input_tokens: Expected input tokens
            estimated_output_tokens: Expected output tokens
            
        Returns:
            Dictionary with cost projections
        """
        pricing = get_model_pricing(model_id)
        if not pricing:
            return {
                "error": f"Pricing not found for model: {model_id}",
                "model_id": model_id
            }
        
        input_cost = (estimated_input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (estimated_output_tokens / 1000) * pricing.output_cost_per_1k
        total_cost = input_cost + output_cost
        
        return {
            "model_id": model_id,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "pricing": {
                "input_per_1k": pricing.input_cost_per_1k,
                "output_per_1k": pricing.output_cost_per_1k,
                "input_per_1m": pricing.input_cost_per_1m,
                "output_per_1m": pricing.output_cost_per_1m,
            }
        }
    
    async def get_cost_comparison(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Dict:
        """
        Compare costs across all available models for a given workload.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dictionary with cost comparison across models
        """
        from src.core.token_models import MODEL_PRICING_CONFIG
        
        comparisons = []
        for model_id, pricing in MODEL_PRICING_CONFIG.items():
            cost = pricing.calculate_cost(input_tokens, output_tokens)
            comparisons.append({
                "model_id": model_id,
                "provider": pricing.provider.value,
                "cost": round(cost, 6),
                "context_window": pricing.context_window
            })
        
        # Sort by cost
        comparisons.sort(key=lambda x: x["cost"])
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "models": comparisons
        }
    
    async def clear_old_data(self, days: int = 7):
        """
        Clear usage data older than specified days.
        
        Args:
            days: Number of days to retain
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        async with self._lock:
            # Clear old global usage
            self.global_usage = [
                usage for usage in self.global_usage
                if usage.timestamp > cutoff
            ]
            
            # Clear old sessions
            old_sessions = [
                sid for sid, session in self.sessions.items()
                if session.end_time and session.end_time < cutoff
            ]
            
            for sid in old_sessions:
                del self.sessions[sid]
            
            logger.info(
                "old_data_cleared",
                cutoff_date=cutoff.isoformat(),
                sessions_removed=len(old_sessions),
                records_remaining=len(self.global_usage)
            )


# Global singleton instance
_token_manager: Optional[TokenTrackingManager] = None


def get_token_manager() -> TokenTrackingManager:
    """Get the global token tracking manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenTrackingManager()
    return _token_manager

