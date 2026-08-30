"""
Core orchestrator that manages multi-agent collaboration.
Coordinates the main agent and sub-agents to accomplish complex tasks.
"""
import asyncio
from typing import AsyncGenerator, List, Optional, Dict, Any
from datetime import datetime
import uuid
import json

from src.core.models import (
    AgentType, AgentState, AgentStatus, StreamChunk,
    TaskRequest, SubAgentQuery, AgentResponse, AgentMessage, ConversationRound
)
from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseAgent
from src.infrastructure.logging.config import get_logger, bind_context, unbind_context
from src.infrastructure.database import db_manager, ConversationService

logger = get_logger(__name__)


class TaskOrchestrator:
    """Orchestrates multi-agent task execution."""
    
    def __init__(self, websocket_mode: bool = False, connection_manager = None, session_id: Optional[str] = None):
        """
        Initialize the orchestrator.
        
        Args:
            websocket_mode: If True, events are sent via WebSocket instead of yielded
            connection_manager: Connection manager for WebSocket broadcasting
            session_id: Optional session ID for token tracking
        """
        self.main_agent: Optional[BaseAgent] = None
        self.active_sub_agents: Dict[str, BaseAgent] = {}
        self.conversation_id: Optional[str] = None
        self.conversation_rounds: List[ConversationRound] = []
        self.max_conversation_rounds: int = 3  # Limit rounds to prevent infinite loops
        self.websocket_mode = websocket_mode
        self.connection_manager = connection_manager
        self.session_id = session_id
        self.is_cancelled: bool = False
        # In-memory conversation history for fast access (avoids DB race conditions)
        self.in_memory_history: List[Dict[str, str]] = []
        self.history_loaded_from_db: bool = False
        
    async def _load_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        Load previous conversation messages from database.
        
        Args:
            conversation_id: The conversation ID (either UUID or conv_xxx format)
            
        Returns:
            List of message dicts in OpenAI format (role, content)
        """
        try:
            if not conversation_id:
                return []
            
            conv_uuid = None
            
            # Handle different conversation ID formats
            if conversation_id.startswith("conv_"):
                # For conv_xxx format, look up by task_id
                # The websocket handler stores conversations with task_id = conversation_id
                async with db_manager.session() as db_session:
                    from src.infrastructure.database.repository import ConversationRepository
                    conversations = await ConversationRepository.get_by_task_id(
                        db_session,
                        conversation_id
                    )
                    if conversations:
                        conv_uuid = conversations[0].id
                        logger.debug(
                            "conversation_found_by_task_id",
                            conversation_id=conversation_id,
                            conv_uuid=str(conv_uuid)
                        )
                    else:
                        logger.debug("no_conversation_found_by_task_id", conversation_id=conversation_id)
                        return []
            else:
                # Try to parse as UUID
                try:
                    conv_uuid = uuid.UUID(conversation_id)
                except (ValueError, AttributeError):
                    logger.debug("invalid_uuid_format", conversation_id=conversation_id)
                    return []
            
            if not conv_uuid:
                return []
            
            # Fetch conversation with messages from database
            async with db_manager.session() as db_session:
                conversation = await ConversationService.get_conversation_with_messages(
                    db_session,
                    conv_uuid
                )
                
                if not conversation or not conversation.messages:
                    logger.debug("no_previous_messages", conversation_id=conversation_id)
                    return []
                
                # Convert database messages to OpenAI format
                # Filter out agent_conversation messages (they're for synthesis, not main context)
                history = []
                for msg in sorted(conversation.messages, key=lambda m: m.created_at):
                    # Skip agent-to-agent conversation messages
                    if msg.metadata and msg.metadata.get("message_type") == "agent_conversation":
                        continue
                    
                    history.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                
                logger.info(
                    "conversation_history_loaded",
                    conversation_id=conversation_id,
                    message_count=len(history)
                )
                return history
                
        except Exception as e:
            logger.error(
                "failed_to_load_conversation_history",
                conversation_id=conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            # Return empty history on error - don't fail the request
            return []
    
    async def process_task(
        self,
        task: TaskRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a task using the main agent and sub-agents as needed.
        
        Args:
            task: The task request from the user
            
        Yields:
            Status updates and streaming responses
        """
        # Reset cancellation flag
        self.is_cancelled = False
        
        # Initialize conversation
        if task.conversation_id:
            self.conversation_id = task.conversation_id
        else:
            self.conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        # Bind conversation context for all logs in this task
        bind_context(conversation_id=self.conversation_id)
        
        logger.info(
            "task_orchestration_started",
            enable_collaboration=task.enable_collaboration,
            max_sub_agents=task.max_sub_agents
        )
        
        # Load conversation history from database ONCE on first initialization
        # After that, use in-memory history to avoid race conditions
        if not self.history_loaded_from_db:
            conversation_history = await self._load_conversation_history(self.conversation_id)
            self.in_memory_history = conversation_history
            self.history_loaded_from_db = True
            logger.info(
                "conversation_history_loaded_from_db",
                conversation_id=self.conversation_id,
                message_count=len(conversation_history)
            )
        else:
            conversation_history = self.in_memory_history
            logger.info(
                "using_in_memory_conversation_history",
                conversation_id=self.conversation_id,
                message_count=len(conversation_history)
            )
        
        # Create main agent if needed
        if not self.main_agent:
            self.main_agent = AgentFactory.create_main_agent(session_id=self.session_id)
            logger.debug("main_agent_created", agent_id=self.main_agent.config.agent_id, session_id=self.session_id)
        
        # Send initialization event
        yield {
            "type": "init",
            "conversationId": self.conversation_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Phase 1: Main agent analyzes task
        yield {
            "type": "agent_status",
            "agentId": "main_orchestrator",
            "agentType": AgentType.CLAUDE_MAIN.value,
            "status": AgentStatus.THINKING.value,
            "message": "Analyzing task..."
        }
        
        # Check for cancellation
        if self.is_cancelled:
            logger.info("task_cancelled_during_analysis")
            yield {
                "type": "cancelled",
                "conversationId": self.conversation_id,
                "timestamp": datetime.now().isoformat()
            }
            return
        
        # Prepare messages with conversation history
        messages = self._prepare_main_agent_messages(task.message, conversation_history)
        
        # Check if main agent wants to delegate to sub-agents
        if task.enable_collaboration and not self.is_cancelled:
            # First, let main agent decide on delegation
            logger.debug("requesting_delegation_plan")
            delegation_response = await self._get_delegation_plan(
                task.message,
                task.max_sub_agents,
                conversation_history
            )
            
            if delegation_response.get("delegate"):
                logger.info(
                    "delegation_approved",
                    reasoning=delegation_response.get("reasoning"),
                    num_sub_agents=len(delegation_response.get("sub_queries", []))
                )
                # Execute sub-agent queries and enable inter-agent communication
                sub_queries = delegation_response.get("sub_queries", [])
                
                yield {
                    "type": "delegation",
                    "subAgents": [q["agent_type"] for q in sub_queries],
                    "queries": sub_queries
                }
                
                # Create sub-agents
                logger.debug("creating_sub_agents", count=len(sub_queries))
                await self._create_sub_agents(sub_queries)
                
                # Start inter-agent conversation
                logger.info("starting_agent_conversation", num_agents=len(self.active_sub_agents))
                async for conv_event in self._run_agent_conversation(task.message):
                    yield conv_event
                
                # Synthesize final response from conversation
                messages = self._prepare_synthesis_from_conversation(task.message, conversation_history)
        
        # Phase 2: Main agent provides final response (streaming)
        yield {
            "type": "agent_status",
            "agentId": "main_orchestrator",
            "agentType": AgentType.CLAUDE_MAIN.value,
            "status": AgentStatus.RESPONDING.value,
            "message": "Generating response..."
        }
        
        logger.debug("streaming_final_response")
        accumulated_response = ""
        
        try:
            async for chunk in self.main_agent.stream_response(messages):
                # Check for cancellation during streaming
                if self.is_cancelled:
                    logger.info("task_cancelled_during_streaming", accumulated_length=len(accumulated_response))
                    yield {
                        "type": "cancelled",
                        "conversationId": self.conversation_id,
                        "partialResponse": accumulated_response,
                        "timestamp": datetime.now().isoformat()
                    }
                    return
                
                accumulated_response += chunk.content
                yield {
                    "type": "stream",
                    "agentId": chunk.agent_id,
                    "content": chunk.content,
                    "isFinal": chunk.is_final
                }
            
            logger.info(
                "task_orchestration_completed",
                response_length=len(accumulated_response)
            )
            
            # Add current exchange to in-memory history for next turn
            self.in_memory_history.append({"role": "user", "content": task.message})
            self.in_memory_history.append({"role": "assistant", "content": accumulated_response})
            logger.debug(
                "in_memory_history_updated",
                conversation_id=self.conversation_id,
                total_messages=len(self.in_memory_history)
            )
            
            # Final completion event
            yield {
                "type": "complete",
                "conversationId": self.conversation_id,
                "finalResponse": accumulated_response,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(
                "final_response_streaming_error",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            # Yield error event but don't crash
            yield {
                "type": "error",
                "error": str(e),
                "message": "Error during response generation",
                "timestamp": datetime.now().isoformat()
            }
        finally:
            # Always unbind conversation context
            unbind_context("conversation_id")
    
    async def _get_delegation_plan(
        self,
        user_message: str,
        max_sub_agents: int,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Ask main agent to create a delegation plan.
        
        Args:
            user_message: Current user message
            max_sub_agents: Maximum number of sub-agents
            conversation_history: Previous conversation messages
        
        Returns:
            Dictionary with delegation decision and sub-queries
        """
        delegation_prompt = f"""Analyze this user request and decide if you need help from other AI agents.

User request: {user_message}

Available agents (use EXACT agent_type values):
- "claude-sonnet-3.5": Detailed analysis and research (Claude sub-agent)
- "gpt-5": Creative thinking and problem-solving (GPT agent)

CRITICAL: You MUST use these exact agent_type values. Do NOT use "gpt-4", "gpt-4o", or any other variations.

Respond with JSON ONLY in this format:
{{
    "delegate": true/false,
    "reasoning": "why you're delegating or not",
    "sub_queries": [
        {{
            "agent_type": "claude-sonnet-3.5",
            "query": "specific question for this agent",
            "priority": 1
        }}
    ]
}}

Valid agent_type values: "claude-sonnet-3.5" or "gpt-5" ONLY.
Maximum {max_sub_agents} sub-agents. Only delegate if it will significantly improve the response."""
        
        # Include conversation history in delegation decision
        messages = [
            {"role": "system", "content": self.main_agent.config.system_prompt}
        ]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": delegation_prompt})
        
        try:
            response = await self.main_agent.get_complete_response(messages)
            # Parse JSON response
            # Extract JSON from markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            delegation_plan = json.loads(response)
            logger.debug(
                "delegation_plan_received",
                delegate=delegation_plan.get("delegate"),
                num_queries=len(delegation_plan.get("sub_queries", []))
            )
            return delegation_plan
        except Exception as e:
            logger.error(
                "delegation_parsing_error",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            return {"delegate": False, "reasoning": "Error in delegation"}
    
    async def _execute_sub_agents(
        self,
        sub_queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple sub-agent queries in parallel.
        
        Args:
            sub_queries: List of sub-agent query specifications
            
        Returns:
            List of sub-agent responses
        """
        tasks = []
        
        # Mapping for common agent type mistakes
        agent_type_aliases = {
            "gpt-4": AgentType.GPT5,  # Map gpt-4 to gpt-5 (our valid type)
            "gpt-4o": AgentType.GPT5,
            "gpt4": AgentType.GPT5,
            "gpt5": AgentType.GPT5,
        }
        
        for query_spec in sub_queries:
            agent_type_str = query_spec["agent_type"]
            
            # Try to parse agent type with fallback for common mistakes
            try:
                agent_type = AgentType(agent_type_str)
            except ValueError:
                # Check if there's an alias mapping
                if agent_type_str in agent_type_aliases:
                    agent_type = agent_type_aliases[agent_type_str]
                    logger.warning(
                        "agent_type_alias_used",
                        requested=agent_type_str,
                        mapped_to=agent_type.value
                    )
                else:
                    logger.error(
                        "invalid_agent_type",
                        agent_type=agent_type_str,
                        valid_types=[t.value for t in AgentType]
                    )
                    # Skip this invalid agent type
                    continue
            
            logger.debug(
                "creating_sub_agent",
                agent_type=agent_type.value,
                priority=query_spec.get("priority", 0)
            )
            agent = AgentFactory.create_sub_agent(
                agent_type=agent_type,
                task_description=query_spec["query"],
                session_id=self.session_id
            )
            
            self.active_sub_agents[agent.config.agent_id] = agent
            
            # Create task for this sub-agent
            task = self._execute_single_sub_agent(
                agent,
                query_spec["query"]
            )
            tasks.append(task)
        
        # Execute all in parallel
        logger.debug("gathering_sub_agent_results", count=len(tasks))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        responses = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "sub_agent_execution_error",
                    index=idx,
                    error=str(result),
                    error_type=type(result).__name__
                )
                continue
            responses.append(result)
        
        return responses
    
    async def _execute_single_sub_agent(
        self,
        agent: BaseAgent,
        query: str
    ) -> Dict[str, Any]:
        """Execute a single sub-agent query."""
        logger.debug(
            "sub_agent_query_started",
            agent_id=agent.config.agent_id,
            agent_type=agent.config.agent_type.value,
            query_length=len(query)
        )
        
        messages = [
            {"role": "system", "content": agent.config.system_prompt},
            {"role": "user", "content": query}
        ]
        
        response = await agent.get_complete_response(messages)
        
        logger.info(
            "sub_agent_query_completed",
            agent_id=agent.config.agent_id,
            agent_type=agent.config.agent_type.value,
            response_length=len(response)
        )
        
        return {
            "agent_id": agent.config.agent_id,
            "agent_type": agent.config.agent_type.value,
            "content": response
        }
    
    def _prepare_main_agent_messages(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Prepare messages for the main agent with conversation history.
        
        Args:
            user_message: Current user message
            conversation_history: Previous conversation messages
            
        Returns:
            List of messages including system prompt, history, and current message
        """
        messages = [
            {"role": "system", "content": self.main_agent.config.system_prompt}
        ]
        # Add conversation history
        messages.extend(conversation_history)
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def _prepare_synthesis_messages(
        self,
        user_message: str,
        sub_responses: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Prepare messages for synthesis with sub-agent responses."""
        synthesis_context = "Sub-agent responses:\n\n"
        
        for response in sub_responses:
            synthesis_context += f"[{response['agent_type']}]: {response['content']}\n\n"
        
        synthesis_prompt = f"""Original user request: {user_message}

{synthesis_context}

Now provide a comprehensive response that synthesizes the insights from the sub-agents above.
Focus on creating a coherent, well-organized answer that directly addresses the user's needs."""
        
        return [
            {"role": "system", "content": self.main_agent.config.system_prompt},
            {"role": "user", "content": synthesis_prompt}
        ]
    
    async def _create_sub_agents(self, sub_queries: List[Dict[str, Any]]):
        """Create sub-agents without immediately executing them."""
        # Mapping for common agent type mistakes
        agent_type_aliases = {
            "gpt-4": AgentType.GPT5,
            "gpt-4o": AgentType.GPT5,
            "gpt4": AgentType.GPT5,
            "gpt5": AgentType.GPT5,
        }
        
        for query_spec in sub_queries:
            agent_type_str = query_spec["agent_type"]
            
            # Try to parse agent type with fallback for common mistakes
            try:
                agent_type = AgentType(agent_type_str)
            except ValueError:
                # Check if there's an alias mapping
                if agent_type_str in agent_type_aliases:
                    agent_type = agent_type_aliases[agent_type_str]
                    logger.warning(
                        "agent_type_alias_used_in_conversation",
                        requested=agent_type_str,
                        mapped_to=agent_type.value
                    )
                else:
                    logger.error(
                        "invalid_agent_type_in_conversation",
                        agent_type=agent_type_str,
                        valid_types=[t.value for t in AgentType]
                    )
                    # Skip this invalid agent type
                    continue
            
            logger.debug(
                "creating_sub_agent_for_conversation",
                agent_type=agent_type.value,
                priority=query_spec.get("priority", 0)
            )
            agent = AgentFactory.create_sub_agent(
                agent_type=agent_type,
                task_description=query_spec["query"],
                session_id=self.session_id
            )
            self.active_sub_agents[agent.config.agent_id] = agent
    
    async def _run_agent_conversation(
        self,
        user_message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run a multi-round conversation between agents.
        Each agent responds to the previous round of messages.
        """
        logger.info("agent_conversation_started", num_agents=len(self.active_sub_agents))
        
        # Initialize first round with user's message as context
        current_round = 1
        conversation_context = f"User request: {user_message}\n\n"
        
        while current_round <= self.max_conversation_rounds:
            logger.debug("conversation_round_started", round=current_round)
            
            round_messages: List[AgentMessage] = []
            
            # Each agent contributes to this round
            for agent_id, agent in self.active_sub_agents.items():
                yield {
                    "type": "agent_thinking",
                    "agentId": agent_id,
                    "agentType": agent.config.agent_type.value,
                    "roundNumber": current_round,
                    "status": "thinking"
                }
                
                # Prepare context with previous round messages
                prompt = self._prepare_conversation_prompt(
                    conversation_context,
                    current_round,
                    agent
                )
                
                messages = [
                    {"role": "system", "content": agent.config.system_prompt},
                    {"role": "user", "content": prompt}
                ]
                
                # Stream agent's response token-by-token for real-time viewing
                logger.debug(
                    "agent_responding_in_round",
                    agent_id=agent_id,
                    agent_type=agent.config.agent_type.value,
                    round=current_round
                )
                
                response_content = ""
                
                # Generate a message ID for this streaming message
                message_id = f"msg_{uuid.uuid4().hex[:12]}"
                
                # Stream the response
                async for chunk in agent.stream_response(messages):
                    if chunk.content and not chunk.is_final:
                        response_content += chunk.content
                        
                        # Yield streaming chunk for real-time display
                        yield {
                            "type": "agent_message_chunk",
                            "messageId": message_id,
                            "agentId": agent_id,
                            "agentType": agent.config.agent_type.value,
                            "content": chunk.content,
                            "roundNumber": current_round,
                            "isComplete": False,
                            "timestamp": datetime.now().isoformat()
                        }
                
                # Create agent message
                agent_message = AgentMessage(
                    message_id=message_id,
                    from_agent_id=agent_id,
                    from_agent_type=agent.config.agent_type,
                    content=response_content,
                    round_number=current_round,
                    timestamp=datetime.now()
                )
                round_messages.append(agent_message)
                
                # Emit final complete message event
                yield {
                    "type": "agent_message",
                    "messageId": message_id,
                    "agentId": agent_id,
                    "agentType": agent.config.agent_type.value,
                    "content": response_content,
                    "roundNumber": current_round,
                    "isComplete": True,
                    "timestamp": agent_message.timestamp.isoformat()
                }
                
                logger.info(
                    "agent_message_sent",
                    agent_id=agent_id,
                    round=current_round,
                    content_length=len(response_content)
                )
            
            # Store round
            conv_round = ConversationRound(
                round_number=current_round,
                messages=round_messages,
                participating_agents=list(self.active_sub_agents.keys()),
                is_complete=True
            )
            self.conversation_rounds.append(conv_round)
            
            # Update context for next round
            conversation_context += f"\n--- Round {current_round} ---\n"
            for msg in round_messages:
                conversation_context += f"[{msg.from_agent_type.value}]: {msg.content}\n\n"
            
            # Emit round complete event
            yield {
                "type": "conversation_round_complete",
                "roundNumber": current_round,
                "messageCount": len(round_messages)
            }
            
            # Check if we should continue (simple heuristic: always run max rounds for now)
            current_round += 1
            
            # Small delay between rounds
            await asyncio.sleep(0.5)
        
        logger.info(
            "agent_conversation_complete",
            total_rounds=len(self.conversation_rounds),
            total_messages=sum(len(r.messages) for r in self.conversation_rounds)
        )
    
    def _prepare_conversation_prompt(
        self,
        conversation_context: str,
        round_number: int,
        agent: BaseAgent
    ) -> str:
        """Prepare prompt for an agent in a conversation round."""
        if round_number == 1:
            return f"""{conversation_context}
This is a collaborative discussion with other AI agents to solve the user's request.
Please share your initial analysis and insights. Be concise but insightful.
Other agents will also contribute, and you'll see their responses in the next round."""
        else:
            return f"""{conversation_context}

This is round {round_number} of the discussion. Review what other agents have said above.
Now provide your thoughts:
- Do you agree or disagree with the other agents?
- What additional insights can you add?
- What aspects need more clarification?

Be constructive and build on the conversation."""
    
    def _prepare_synthesis_from_conversation(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Prepare messages for final synthesis from the full conversation.
        
        Args:
            user_message: Current user message
            conversation_history: Previous conversation messages
            
        Returns:
            List of messages including history and agent discussion for synthesis
        """
        synthesis_context = "Agent Discussion:\n\n"
        
        for conv_round in self.conversation_rounds:
            synthesis_context += f"=== Round {conv_round.round_number} ===\n"
            for msg in conv_round.messages:
                synthesis_context += f"\n[{msg.from_agent_type.value}]:\n{msg.content}\n"
            synthesis_context += "\n"
        
        synthesis_prompt = f"""Original user request: {user_message}

The AI agents have had the following discussion:

{synthesis_context}

Now provide a comprehensive, well-structured response that:
1. Synthesizes all the insights from the agent discussion
2. Resolves any disagreements or conflicting viewpoints
3. Directly addresses the user's original request
4. Presents the information in a clear, organized manner

Focus on being helpful and thorough."""
        
        # Build messages with conversation history + synthesis prompt
        messages = [
            {"role": "system", "content": self.main_agent.config.system_prompt}
        ]
        # Add conversation history for context
        messages.extend(conversation_history)
        # Add synthesis prompt
        messages.append({"role": "user", "content": synthesis_prompt})
        return messages
    
    def cancel(self):
        """Cancel the current task execution."""
        logger.info("orchestrator_cancellation_requested", conversation_id=self.conversation_id)
        self.is_cancelled = True
    
    def reset(self):
        """Reset the orchestrator state."""
        logger.info(
            "orchestrator_reset",
            had_main_agent=self.main_agent is not None,
            active_sub_agents_count=len(self.active_sub_agents),
            in_memory_history_size=len(self.in_memory_history)
        )
        self.main_agent = None
        self.active_sub_agents.clear()
        self.conversation_id = None
        self.conversation_rounds.clear()
        self.is_cancelled = False
        self.in_memory_history.clear()
        self.history_loaded_from_db = False

