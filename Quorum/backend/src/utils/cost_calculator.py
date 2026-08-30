"""
Standalone cost calculator utility for token usage.
Provides functions for calculating costs across different models and scenarios.
"""
from typing import Dict, List, Optional, Tuple
from src.core.token_models import MODEL_PRICING_CONFIG, ModelPricing


def calculate_single_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int
) -> Dict[str, any]:
    """
    Calculate cost for a single model and token counts.
    
    Args:
        model_id: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Dictionary with cost breakdown
    """
    pricing = MODEL_PRICING_CONFIG.get(model_id)
    if not pricing:
        return {
            "error": f"Unknown model: {model_id}",
            "model_id": model_id
        }
    
    input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
    output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
    total_cost = input_cost + output_cost
    
    return {
        "model_id": model_id,
        "provider": pricing.provider.value,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "costs": {
            "input": round(input_cost, 6),
            "output": round(output_cost, 6),
            "total": round(total_cost, 6)
        },
        "pricing": {
            "input_per_1k": pricing.input_cost_per_1k,
            "output_per_1k": pricing.output_cost_per_1k,
            "input_per_1m": pricing.input_cost_per_1m,
            "output_per_1m": pricing.output_cost_per_1m
        }
    }


def compare_models(
    input_tokens: int,
    output_tokens: int,
    model_ids: Optional[List[str]] = None
) -> List[Dict[str, any]]:
    """
    Compare costs across multiple models.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_ids: Optional list of specific models to compare (compares all if None)
        
    Returns:
        List of cost comparisons sorted by total cost
    """
    models_to_compare = model_ids if model_ids else list(MODEL_PRICING_CONFIG.keys())
    
    comparisons = []
    for model_id in models_to_compare:
        result = calculate_single_cost(model_id, input_tokens, output_tokens)
        if "error" not in result:
            comparisons.append(result)
    
    # Sort by total cost
    comparisons.sort(key=lambda x: x["costs"]["total"])
    
    return comparisons


def find_cheapest_model(
    input_tokens: int,
    output_tokens: int,
    min_context_window: Optional[int] = None
) -> Dict[str, any]:
    """
    Find the cheapest model for a given workload.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        min_context_window: Optional minimum context window requirement
        
    Returns:
        Information about the cheapest model
    """
    eligible_models = MODEL_PRICING_CONFIG
    
    if min_context_window:
        eligible_models = {
            k: v for k, v in MODEL_PRICING_CONFIG.items()
            if v.context_window >= min_context_window
        }
    
    if not eligible_models:
        return {"error": "No models meet the specified requirements"}
    
    cheapest = None
    min_cost = float('inf')
    
    for model_id, pricing in eligible_models.items():
        cost = pricing.calculate_cost(input_tokens, output_tokens)
        if cost < min_cost:
            min_cost = cost
            cheapest = (model_id, pricing)
    
    if not cheapest:
        return {"error": "Could not determine cheapest model"}
    
    model_id, pricing = cheapest
    result = calculate_single_cost(model_id, input_tokens, output_tokens)
    result["is_cheapest"] = True
    
    return result


def calculate_batch_cost(
    operations: List[Tuple[str, int, int]]
) -> Dict[str, any]:
    """
    Calculate total cost for a batch of operations.
    
    Args:
        operations: List of tuples (model_id, input_tokens, output_tokens)
        
    Returns:
        Aggregated cost breakdown
    """
    total_cost = 0.0
    by_model = {}
    operations_count = 0
    
    for model_id, input_tokens, output_tokens in operations:
        result = calculate_single_cost(model_id, input_tokens, output_tokens)
        
        if "error" in result:
            continue
        
        operations_count += 1
        total_cost += result["costs"]["total"]
        
        if model_id not in by_model:
            by_model[model_id] = {
                "provider": result["provider"],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "operation_count": 0
            }
        
        by_model[model_id]["total_input_tokens"] += input_tokens
        by_model[model_id]["total_output_tokens"] += output_tokens
        by_model[model_id]["total_cost"] += result["costs"]["total"]
        by_model[model_id]["operation_count"] += 1
    
    return {
        "operations_count": operations_count,
        "total_cost": round(total_cost, 6),
        "by_model": by_model
    }


def estimate_monthly_cost(
    daily_operations: List[Tuple[str, int, int]],
    days_per_month: int = 30
) -> Dict[str, any]:
    """
    Estimate monthly costs based on daily usage patterns.
    
    Args:
        daily_operations: List of daily operations (model_id, input_tokens, output_tokens)
        days_per_month: Number of days to project (default 30)
        
    Returns:
        Monthly cost projection
    """
    daily_cost_result = calculate_batch_cost(daily_operations)
    daily_cost = daily_cost_result["total_cost"]
    monthly_cost = daily_cost * days_per_month
    
    # Calculate by model projections
    monthly_by_model = {}
    for model_id, stats in daily_cost_result["by_model"].items():
        monthly_by_model[model_id] = {
            "provider": stats["provider"],
            "projected_input_tokens": stats["total_input_tokens"] * days_per_month,
            "projected_output_tokens": stats["total_output_tokens"] * days_per_month,
            "projected_cost": round(stats["total_cost"] * days_per_month, 2),
            "daily_average_operations": stats["operation_count"]
        }
    
    return {
        "projection_period_days": days_per_month,
        "daily_cost": round(daily_cost, 6),
        "monthly_cost": round(monthly_cost, 2),
        "yearly_cost": round(monthly_cost * 12, 2),
        "by_model": monthly_by_model
    }


def calculate_cost_savings(
    current_model: str,
    alternative_model: str,
    input_tokens: int,
    output_tokens: int
) -> Dict[str, any]:
    """
    Calculate potential cost savings by switching models.
    
    Args:
        current_model: Current model identifier
        alternative_model: Alternative model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Cost savings analysis
    """
    current = calculate_single_cost(current_model, input_tokens, output_tokens)
    alternative = calculate_single_cost(alternative_model, input_tokens, output_tokens)
    
    if "error" in current or "error" in alternative:
        return {
            "error": "One or both models not found",
            "current_model": current_model,
            "alternative_model": alternative_model
        }
    
    current_cost = current["costs"]["total"]
    alternative_cost = alternative["costs"]["total"]
    savings = current_cost - alternative_cost
    savings_percent = (savings / current_cost * 100) if current_cost > 0 else 0
    
    return {
        "current_model": {
            "model_id": current_model,
            "cost": current_cost,
            "provider": current["provider"]
        },
        "alternative_model": {
            "model_id": alternative_model,
            "cost": alternative_cost,
            "provider": alternative["provider"]
        },
        "savings": {
            "absolute": round(savings, 6),
            "percentage": round(savings_percent, 2),
            "is_cheaper": savings > 0
        },
        "recommendation": (
            f"Switch to {alternative_model} to save ${abs(savings):.4f} per operation"
            if savings > 0
            else f"Keep {current_model} - it's ${abs(savings):.4f} cheaper"
        )
    }


# Quick reference pricing summary
def get_pricing_summary() -> Dict[str, any]:
    """
    Get a summary of all model pricing for quick reference.
    
    Returns:
        Pricing summary organized by provider
    """
    by_provider = {}
    
    for model_id, pricing in MODEL_PRICING_CONFIG.items():
        provider = pricing.provider.value
        
        if provider not in by_provider:
            by_provider[provider] = []
        
        by_provider[provider].append({
            "model_id": model_id,
            "input_per_1k": pricing.input_cost_per_1k,
            "output_per_1k": pricing.output_cost_per_1k,
            "context_window": pricing.context_window
        })
    
    return {
        "providers": by_provider,
        "total_models": len(MODEL_PRICING_CONFIG)
    }

