"""
API endpoints for token usage tracking and cost analysis.
Provides real-time statistics, cost calculations, and usage analytics.
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.infrastructure.tracking.token_manager import get_token_manager
from src.core.token_models import MODEL_PRICING_CONFIG, get_model_pricing
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


# Request/Response Models
class CostCalculationRequest(BaseModel):
    """Request model for cost calculation."""
    model_id: str = Field(..., description="Model identifier")
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")


class CostComparisonRequest(BaseModel):
    """Request model for cost comparison across models."""
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")


# Endpoints
@router.get("/pricing")
async def get_all_pricing():
    """
    Get pricing information for all supported models.
    
    Returns:
        Dictionary with pricing for all models
    """
    pricing_info = {}
    for model_id, pricing in MODEL_PRICING_CONFIG.items():
        pricing_info[model_id] = {
            "model_id": model_id,
            "provider": pricing.provider.value,
            "input_cost_per_1k": pricing.input_cost_per_1k,
            "output_cost_per_1k": pricing.output_cost_per_1k,
            "input_cost_per_1m": pricing.input_cost_per_1m,
            "output_cost_per_1m": pricing.output_cost_per_1m,
            "context_window": pricing.context_window
        }
    
    return {
        "models": pricing_info,
        "count": len(pricing_info)
    }


@router.get("/pricing/{model_id}")
async def get_model_pricing_info(model_id: str):
    """
    Get pricing information for a specific model.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Pricing information for the model
    """
    pricing = get_model_pricing(model_id)
    if not pricing:
        raise HTTPException(status_code=404, detail=f"Pricing not found for model: {model_id}")
    
    return {
        "model_id": model_id,
        "provider": pricing.provider.value,
        "input_cost_per_1k": pricing.input_cost_per_1k,
        "output_cost_per_1k": pricing.output_cost_per_1k,
        "input_cost_per_1m": pricing.input_cost_per_1m,
        "output_cost_per_1m": pricing.output_cost_per_1m,
        "context_window": pricing.context_window
    }


@router.post("/calculate")
async def calculate_cost(request: CostCalculationRequest):
    """
    Calculate cost for a specific model and token counts.
    
    Args:
        request: Cost calculation request
        
    Returns:
        Detailed cost breakdown
    """
    manager = get_token_manager()
    result = await manager.calculate_projected_costs(
        model_id=request.model_id,
        estimated_input_tokens=request.input_tokens,
        estimated_output_tokens=request.output_tokens
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/compare")
async def compare_costs(request: CostComparisonRequest):
    """
    Compare costs across all available models for a given workload.
    
    Args:
        request: Cost comparison request
        
    Returns:
        Cost comparison across all models
    """
    manager = get_token_manager()
    result = await manager.get_cost_comparison(
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens
    )
    
    return result


@router.get("/stats/global")
async def get_global_stats():
    """
    Get global token usage statistics across all sessions.
    
    Returns:
        Global usage statistics
    """
    manager = get_token_manager()
    stats = await manager.get_global_stats()
    return stats


@router.get("/stats/session/{session_id}")
async def get_session_stats(session_id: str):
    """
    Get token usage statistics for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session usage statistics
    """
    manager = get_token_manager()
    stats = await manager.get_session_summary(session_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    return stats


@router.get("/usage/recent")
async def get_recent_usage(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID")
):
    """
    Get recent token usage records.
    
    Args:
        limit: Maximum number of records to return
        model_id: Optional filter by model
        agent_id: Optional filter by agent
        
    Returns:
        List of recent usage records
    """
    manager = get_token_manager()
    usage_records = await manager.get_recent_usage(
        limit=limit,
        model_id=model_id,
        agent_id=agent_id
    )
    
    return {
        "records": [
            {
                "model_id": record.model_id,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "total_tokens": record.total_tokens,
                "cost": record.cost,
                "cost_breakdown": record.cost_breakdown,
                "timestamp": record.timestamp.isoformat(),
                "agent_id": record.agent_id,
                "request_id": record.request_id
            }
            for record in usage_records
        ],
        "count": len(usage_records)
    }


@router.get("/usage/timerange")
async def get_usage_by_timerange(
    start_time: str = Query(..., description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format (defaults to now)")
):
    """
    Get token usage within a time range.
    
    Args:
        start_time: Start of time range (ISO format)
        end_time: End of time range (ISO format, optional)
        
    Returns:
        Usage records within the time range
    """
    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    
    manager = get_token_manager()
    usage_records = await manager.get_usage_by_time_range(start, end)
    
    # Calculate aggregate statistics
    total_input = sum(r.input_tokens for r in usage_records)
    total_output = sum(r.output_tokens for r in usage_records)
    total_cost = sum(r.cost for r in usage_records)
    
    return {
        "time_range": {
            "start": start.isoformat(),
            "end": end.isoformat() if end else datetime.utcnow().isoformat()
        },
        "summary": {
            "total_requests": len(usage_records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": round(total_cost, 6)
        },
        "records": [
            {
                "model_id": record.model_id,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "total_tokens": record.total_tokens,
                "cost": record.cost,
                "timestamp": record.timestamp.isoformat(),
                "agent_id": record.agent_id
            }
            for record in usage_records
        ]
    }


@router.post("/session/create/{session_id}")
async def create_session(session_id: str):
    """
    Create a new token tracking session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Created session information
    """
    manager = get_token_manager()
    session = await manager.create_session(session_id)
    
    return {
        "session_id": session.session_id,
        "start_time": session.start_time.isoformat(),
        "status": "created"
    }


@router.post("/session/close/{session_id}")
async def close_session(session_id: str):
    """
    Close a token tracking session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Final session statistics
    """
    manager = get_token_manager()
    
    # Get stats before closing
    stats = await manager.get_session_summary(session_id)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    # Close the session
    await manager.close_session(session_id)
    
    return {
        "session_id": session_id,
        "status": "closed",
        "final_stats": stats
    }


@router.delete("/cleanup")
async def cleanup_old_data(days: int = Query(7, ge=1, le=365, description="Days of data to retain")):
    """
    Clean up token usage data older than specified days.
    
    Args:
        days: Number of days to retain
        
    Returns:
        Cleanup status
    """
    manager = get_token_manager()
    await manager.clear_old_data(days)
    
    return {
        "status": "success",
        "message": f"Cleared data older than {days} days"
    }

