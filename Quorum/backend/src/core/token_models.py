"""
Token usage tracking models and pricing configuration.
Stores token counts, costs, and provides pricing data for all supported models.
"""
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class ModelProvider(str, Enum):
    """Supported model providers."""
    OPENROUTER = "openrouter"


class ModelPricing(BaseModel):
    """Pricing configuration for a specific model."""
    model_id: str
    provider: ModelProvider
    input_cost_per_1k: float  # Cost per 1,000 input tokens in USD
    output_cost_per_1k: float  # Cost per 1,000 output tokens in USD
    context_window: int  # Maximum context window size
    
    @property
    def input_cost_per_1m(self) -> float:
        """Cost per 1 million input tokens."""
        return self.input_cost_per_1k * 1000
    
    @property
    def output_cost_per_1m(self) -> float:
        """Cost per 1 million output tokens."""
        return self.output_cost_per_1k * 1000
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate total cost for given token counts.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k
        return input_cost + output_cost


# Current pricing as of November 2024
# Source: OpenRouter API documentation and pricing pages
# All models accessed via OpenRouter unified API
MODEL_PRICING_CONFIG: Dict[str, ModelPricing] = {
    # OpenAI Models via OpenRouter
    "openai/gpt-4o": ModelPricing(
        model_id="openai/gpt-4o",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.0025,  # $2.50 per 1M tokens
        output_cost_per_1k=0.010,  # $10.00 per 1M tokens
        context_window=128_000
    ),
    "openai/gpt-4o-mini": ModelPricing(
        model_id="openai/gpt-4o-mini",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.00015,  # $0.15 per 1M tokens
        output_cost_per_1k=0.0006,  # $0.60 per 1M tokens
        context_window=128_000
    ),
    "openai/gpt-4-turbo": ModelPricing(
        model_id="openai/gpt-4-turbo",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.01,  # $10.00 per 1M tokens
        output_cost_per_1k=0.03,  # $30.00 per 1M tokens
        context_window=128_000
    ),
    
    # Anthropic Models via OpenRouter
    "anthropic/claude-3.5-sonnet": ModelPricing(
        model_id="anthropic/claude-3.5-sonnet",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.003,  # $3.00 per 1M tokens
        output_cost_per_1k=0.015,  # $15.00 per 1M tokens
        context_window=200_000
    ),
    "anthropic/claude-3-5-haiku": ModelPricing(
        model_id="anthropic/claude-3-5-haiku",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.001,  # $1.00 per 1M tokens
        output_cost_per_1k=0.005,  # $5.00 per 1M tokens
        context_window=200_000
    ),
    "anthropic/claude-3-opus": ModelPricing(
        model_id="anthropic/claude-3-opus",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.015,  # $15.00 per 1M tokens
        output_cost_per_1k=0.075,  # $75.00 per 1M tokens
        context_window=200_000
    ),
    
    # Google Models via OpenRouter
    "google/gemini-pro": ModelPricing(
        model_id="google/gemini-pro",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.000125,  # $0.125 per 1M tokens
        output_cost_per_1k=0.000375,  # $0.375 per 1M tokens
        context_window=128_000
    ),
    "google/gemini-2.0-flash-exp": ModelPricing(
        model_id="google/gemini-2.0-flash-exp",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.0,  # Free during experimental phase
        output_cost_per_1k=0.0,  # Free during experimental phase
        context_window=1_000_000
    ),
    
    # X.AI Models via OpenRouter
    "x-ai/grok-beta": ModelPricing(
        model_id="x-ai/grok-beta",
        provider=ModelProvider.OPENROUTER,
        input_cost_per_1k=0.005,  # $5.00 per 1M tokens (estimated)
        output_cost_per_1k=0.015,  # $15.00 per 1M tokens (estimated)
        context_window=128_000
    ),
}


class TokenUsage(BaseModel):
    """Token usage information for a single API call."""
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: Optional[str] = None
    request_id: Optional[str] = None
    
    @property
    def cost(self) -> float:
        """Calculate cost based on token usage."""
        pricing = MODEL_PRICING_CONFIG.get(self.model_id)
        if not pricing:
            return 0.0
        return pricing.calculate_cost(self.input_tokens, self.output_tokens)
    
    @property
    def cost_breakdown(self) -> Dict[str, float]:
        """Get detailed cost breakdown."""
        pricing = MODEL_PRICING_CONFIG.get(self.model_id)
        if not pricing:
            return {"input": 0.0, "output": 0.0, "total": 0.0}
        
        input_cost = (self.input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (self.output_tokens / 1000) * pricing.output_cost_per_1k
        
        return {
            "input": round(input_cost, 6),
            "output": round(output_cost, 6),
            "total": round(input_cost + output_cost, 6)
        }


class SessionUsage(BaseModel):
    """Aggregated token usage for a session or time period."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    usage_records: List[TokenUsage] = Field(default_factory=list)
    
    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all records."""
        return sum(record.input_tokens for record in self.usage_records)
    
    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all records."""
        return sum(record.output_tokens for record in self.usage_records)
    
    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output) across all records."""
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def total_cost(self) -> float:
        """Total cost across all records."""
        return sum(record.cost for record in self.usage_records)
    
    @property
    def usage_by_model(self) -> Dict[str, Dict[str, any]]:
        """Aggregate usage statistics by model."""
        model_stats = {}
        
        for record in self.usage_records:
            if record.model_id not in model_stats:
                model_stats[record.model_id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "request_count": 0
                }
            
            stats = model_stats[record.model_id]
            stats["input_tokens"] += record.input_tokens
            stats["output_tokens"] += record.output_tokens
            stats["total_tokens"] += record.total_tokens
            stats["cost"] += record.cost
            stats["request_count"] += 1
        
        return model_stats
    
    @property
    def usage_by_agent(self) -> Dict[str, Dict[str, any]]:
        """Aggregate usage statistics by agent."""
        agent_stats = {}
        
        for record in self.usage_records:
            agent_id = record.agent_id or "unknown"
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "request_count": 0
                }
            
            stats = agent_stats[agent_id]
            stats["input_tokens"] += record.input_tokens
            stats["output_tokens"] += record.output_tokens
            stats["total_tokens"] += record.total_tokens
            stats["cost"] += record.cost
            stats["request_count"] += 1
        
        return agent_stats
    
    def add_usage(self, usage: TokenUsage):
        """Add a token usage record to the session."""
        self.usage_records.append(usage)
        if not self.end_time or usage.timestamp > self.end_time:
            self.end_time = usage.timestamp
    
    def get_summary(self) -> Dict[str, any]:
        """Get a comprehensive summary of usage statistics."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds() 
                if self.end_time else 0
            ),
            "total_requests": len(self.usage_records),
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 6),
            "usage_by_model": self.usage_by_model,
            "usage_by_agent": self.usage_by_agent,
        }


def get_model_pricing(model_id: str) -> Optional[ModelPricing]:
    """
    Get pricing information for a model.
    
    Args:
        model_id: The model identifier
        
    Returns:
        ModelPricing object or None if model not found
    """
    return MODEL_PRICING_CONFIG.get(model_id)


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for a given model and token counts.
    
    Args:
        model_id: The model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Total cost in USD
    """
    pricing = get_model_pricing(model_id)
    if not pricing:
        return 0.0
    return pricing.calculate_cost(input_tokens, output_tokens)

