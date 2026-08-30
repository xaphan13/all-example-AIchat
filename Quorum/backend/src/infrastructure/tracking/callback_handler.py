"""
LangChain callback handler for tracking token usage across all LLM calls.
Supports OpenAI, Anthropic, and Google models with accurate token counting.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from src.core.token_models import TokenUsage
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class TokenTrackingCallback(AsyncCallbackHandler):
    """
    Async callback handler that tracks token usage for all LLM calls.
    
    This handler integrates with LangChain's callback system to capture
    token usage information from OpenAI, Anthropic, and Google models.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        on_usage_callback: Optional[callable] = None,
        is_streaming: bool = False
    ):
        """
        Initialize the token tracking callback.
        
        Args:
            agent_id: Optional agent identifier
            session_id: Optional session identifier
            on_usage_callback: Optional callback function to call when usage is tracked
            is_streaming: If True, suppress warnings for missing token usage (expected in streaming)
        """
        super().__init__()
        self.agent_id = agent_id
        self.session_id = session_id
        self.on_usage_callback = on_usage_callback
        self.is_streaming = is_streaming
        self.current_run_usage: Dict[str, TokenUsage] = {}
    
    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running."""
        logger.debug(
            "token_tracking_llm_start",
            run_id=str(run_id),
            agent_id=self.agent_id,
            prompt_count=len(prompts)
        )
    
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when LLM ends running.
        Extracts token usage information from the response.
        """
        try:
            # Extract token usage from LLM response
            usage_data = self._extract_usage_from_response(response)
            
            if usage_data:
                token_usage = TokenUsage(
                    model_id=usage_data["model_id"],
                    input_tokens=usage_data["input_tokens"],
                    output_tokens=usage_data["output_tokens"],
                    total_tokens=usage_data["total_tokens"],
                    timestamp=datetime.utcnow(),
                    agent_id=self.agent_id,
                    request_id=str(run_id)
                )
                
                # Store usage for this run
                self.current_run_usage[str(run_id)] = token_usage
                
                # Log the usage
                logger.info(
                    "token_usage_tracked",
                    run_id=str(run_id),
                    agent_id=self.agent_id,
                    model=token_usage.model_id,
                    input_tokens=token_usage.input_tokens,
                    output_tokens=token_usage.output_tokens,
                    total_tokens=token_usage.total_tokens,
                    cost=token_usage.cost,
                    cost_breakdown=token_usage.cost_breakdown
                )
                
                # Call the usage callback if provided
                if self.on_usage_callback:
                    await self.on_usage_callback(token_usage)
            else:
                # Only log warning for non-streaming calls (streaming calls don't have token usage)
                if not self.is_streaming:
                    logger.warning(
                        "token_usage_not_found",
                        run_id=str(run_id),
                        agent_id=self.agent_id,
                        message="Could not extract token usage from LLM response"
                    )
                else:
                    logger.debug(
                        "token_usage_not_available_streaming",
                        run_id=str(run_id),
                        agent_id=self.agent_id,
                        message="Token usage not available for streaming responses (expected)"
                    )
        
        except Exception as e:
            logger.error(
                "token_tracking_error",
                run_id=str(run_id),
                agent_id=self.agent_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
    
    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
        logger.warning(
            "token_tracking_llm_error",
            run_id=str(run_id),
            agent_id=self.agent_id,
            error=str(error),
            error_type=type(error).__name__
        )
    
    def _extract_usage_from_response(self, response: LLMResult) -> Optional[Dict[str, Any]]:
        """
        Extract token usage information from LangChain LLMResult.
        
        Different providers return usage information in different formats:
        - OpenAI: response.llm_output["token_usage"]
        - Anthropic: response.llm_output["usage"]
        - Google: response.llm_output["usage_metadata"]
        
        Args:
            response: LangChain LLMResult object
            
        Returns:
            Dictionary with usage information or None if not found
        """
        if not response.llm_output:
            return None
        
        llm_output = response.llm_output
        model_id = llm_output.get("model_name") or llm_output.get("model")
        
        # Try different provider formats
        usage = None
        
        # OpenAI format
        if "token_usage" in llm_output:
            usage = llm_output["token_usage"]
            return {
                "model_id": model_id,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
        
        # Anthropic format
        elif "usage" in llm_output:
            usage = llm_output["usage"]
            return {
                "model_id": model_id,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": (
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                )
            }
        
        # Google format
        elif "usage_metadata" in llm_output:
            usage = llm_output["usage_metadata"]
            return {
                "model_id": model_id,
                "input_tokens": usage.get("prompt_token_count", 0),
                "output_tokens": usage.get("candidates_token_count", 0),
                "total_tokens": usage.get("total_token_count", 0)
            }
        
        # Fallback: check for any common token fields
        else:
            input_tokens = (
                llm_output.get("prompt_tokens") or
                llm_output.get("input_tokens") or
                0
            )
            output_tokens = (
                llm_output.get("completion_tokens") or
                llm_output.get("output_tokens") or
                llm_output.get("generated_tokens") or
                0
            )
            total_tokens = (
                llm_output.get("total_tokens") or
                (input_tokens + output_tokens)
            )
            
            if input_tokens or output_tokens:
                return {
                    "model_id": model_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
        
        return None
    
    def get_usage_for_run(self, run_id: UUID) -> Optional[TokenUsage]:
        """Get token usage for a specific run."""
        return self.current_run_usage.get(str(run_id))
    
    def clear_usage(self):
        """Clear stored usage data."""
        self.current_run_usage.clear()

