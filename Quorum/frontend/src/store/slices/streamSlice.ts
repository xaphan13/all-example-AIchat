/**
 * Stream slice - handles stream event processing with event sourcing pattern.
 * Decouples stream events from state mutations.
 */
import { StateCreator } from 'zustand';
import { StreamSlice, RootStore } from '../types';
import { StreamEvent } from '@/types';
import { createLogger } from '@/services/logger';

const logger = createLogger({ component: 'StreamSlice' });

export const createStreamSlice: StateCreator<
  RootStore,
  [],
  [],
  StreamSlice
> = (set, get) => ({
  // State
  currentStreamId: null,
  isStreaming: false,
  lastEventType: null,
  lastEventTime: null,
  streamingMessageId: null,

  // Actions
  startStream: (streamId: string) =>
    set({
      currentStreamId: streamId,
      isStreaming: true,
      streamingMessageId: null,
    }),

  endStream: () =>
    set({
      currentStreamId: null,
      isStreaming: false,
      streamingMessageId: null,
    }),

  /**
   * Central stream event handler - coordinates updates across slices.
   * This is the event sourcing pattern - events drive all state changes.
   */
  handleStreamEvent: (event: StreamEvent) => {
    const state = get();
    const currentProcessingState = state.isProcessing;
    
    logger.info(`🔄 Stream event: ${event.type}`, {
      type: event.type,
      agentId: event.agentId,
      currentlyProcessing: currentProcessingState,
      isStreaming: state.isStreaming,
      timestamp: new Date().toISOString(),
    });

    const timestamp = new Date().toISOString();

    // Update last event tracking
    set({
      lastEventType: event.type,
      lastEventTime: timestamp,
    });

    // Process event by type
    switch (event.type) {
      case 'init':
        logger.info('Stream initialized', {
          conversationId: event.conversationId,
        });
        
        state.initConversation(event.conversationId || '');
        state.setProcessing(true);
        state.clearError();
        set({ isStreaming: true });
        break;

      case 'agent_status':
        if (event.agentId && event.status) {
          // Don't update agent status if streaming has already ended
          // This prevents late-arriving status events from reverting completed agents
          if (!state.isStreaming && (event.status === 'thinking' || event.status === 'responding')) {
            logger.debug('Ignoring late agent_status event - stream already ended', {
              agentId: event.agentId,
              status: event.status,
            });
            break;
          }
          
          // Check if agent exists, if not create it
          const agent = state.agents.byId[event.agentId];
          
          if (agent) {
            // Don't update if agent is already complete/error and new status is active
            if ((agent.status === 'complete' || agent.status === 'error') && 
                (event.status === 'thinking' || event.status === 'responding')) {
              logger.debug('Ignoring agent_status - agent already finished', {
                agentId: event.agentId,
                currentStatus: agent.status,
                newStatus: event.status,
              });
              break;
            }
            
            state.updateAgent(event.agentId, {
              status: event.status,
              currentMessage: event.message,
            });
          } else if (event.agentType) {
            // Create new agent with backend's agentId
            state.addAgent({
              agentId: event.agentId,
              agentType: event.agentType,
              status: event.status,
              currentMessage: event.message,
              progress: 0,
            });
            
            logger.info('Registered new agent from agent_status', {
              agentId: event.agentId,
              agentType: event.agentType,
            });
          }
        }
        break;

      case 'delegation':
        if (event.queries) {
          logger.info('Creating sub-agents from delegation', {
            count: event.queries.length,
          });

          event.queries.forEach((query) => {
            state.addAgent({
              agentType: query.agentType,
              status: 'thinking',
              currentMessage: query.query,
              progress: 0,
            });
          });
        }
        break;

      case 'sub_agent_response':
        if (event.agentId) {
          logger.debug('Sub-agent completed', {
            agentId: event.agentId,
          });

          state.updateAgent(event.agentId, {
            status: 'complete',
            progress: 100,
          });
        }
        break;

      case 'stream':
        if (event.content) {
          const { streamingMessageId } = get();

          // Check if we should append to existing message or create new one
          if (streamingMessageId && state.messages.byId[streamingMessageId]) {
            // Append to existing streaming message
            state.appendToMessage(streamingMessageId, event.content);
            
            logger.debug('Appended stream chunk to message', {
              messageId: streamingMessageId,
              chunkLength: event.content.length,
              isFinal: event.isFinal,
            });
          } else {
            // Create new assistant message
            const newMessageId = state.addMessage({
              role: 'assistant',
              content: event.content,
              agentId: event.agentId,
            });
            
            // Track this as the current streaming message
            set({ streamingMessageId: newMessageId });
            
            logger.debug('Created new streaming message', {
              messageId: newMessageId,
              chunkLength: event.content.length,
            });
          }
        }
        break;

      case 'complete':
        logger.info('Stream completed - SETTING PROCESSING TO FALSE', {
          agentId: event.agentId,
          messageCount: state.messages.allIds.length,
          finalResponse: event.finalResponse?.length,
          timestamp: new Date().toISOString(),
        });

        // Persist streaming message to sessionStorage now that streaming is done
        const { streamingMessageId } = get();
        if (streamingMessageId && state.messages.byId[streamingMessageId]) {
          // Trigger a final update to persist to sessionStorage
          state.updateMessage(streamingMessageId, {});
        }

        // Set streaming states to false first
        set({ 
          isStreaming: false,
          streamingMessageId: null,
        });
        
        // Then set processing to false (important: do this after streaming state is cleared)
        state.setProcessing(false);
        
        logger.info('Processing state updated to false', {
          isProcessing: get().isProcessing,
        });

        // Mark all agents as complete (not just the primary agent)
        state.agents.allIds.forEach(agentId => {
          const agent = state.agents.byId[agentId];
          if (agent && agent.status !== 'complete' && agent.status !== 'error') {
            state.updateAgent(agentId, {
              status: 'complete',
              progress: 100,
            });
          }
        });

        // Save conversation to history (after all agents are marked complete)
        logger.info('Saving conversation to history');
        state.saveCurrentConversation();
        break;

      case 'stream_end':
        // Backend confirmation that stream is ending
        logger.info('Stream end signal received');
        
        // Set streaming states to false first
        set({ 
          isStreaming: false,
          streamingMessageId: null,
        });
        
        // Then set processing to false
        state.setProcessing(false);

        // Mark all active agents as complete
        state.agents.allIds.forEach(agentId => {
          const agent = state.agents.byId[agentId];
          if (agent && agent.status !== 'complete' && agent.status !== 'error') {
            state.updateAgent(agentId, {
              status: 'complete',
              progress: 100,
            });
          }
        });

        // Save conversation to history
        logger.info('Saving conversation to history');
        state.saveCurrentConversation();
        break;

      case 'cancelled':
        logger.info('Generation cancelled by user', {
          conversationId: event.conversationId,
          hadPartialResponse: !!event.partialResponse,
        });

        state.setProcessing(false);
        set({ 
          isStreaming: false,
          streamingMessageId: null,
        });

        // Mark all active agents as cancelled
        state.agents.allIds.forEach(agentId => {
          const agent = state.agents.byId[agentId];
          if (agent && agent.status !== 'complete') {
            state.updateAgent(agentId, {
              status: 'error',
              currentMessage: 'Cancelled',
            });
          }
        });
        break;

      case 'error':
        logger.error('Stream error', new Error(event.error || 'Unknown error'));

        state.setError(event.error || 'An error occurred');
        state.setProcessing(false);
        set({ 
          isStreaming: false,
          streamingMessageId: null,
        });
        break;

      case 'agent_thinking':
        // Agent is thinking in a conversation round
        if (event.agentId) {
          // Don't update if streaming has already ended
          if (!state.isStreaming) {
            logger.debug('Ignoring late agent_thinking event - stream already ended', {
              agentId: event.agentId,
              roundNumber: event.roundNumber,
            });
            break;
          }
          
          const agent = state.agents.byId[event.agentId];
          
          if (agent) {
            // Don't update if agent is already complete or error
            if (agent.status === 'complete' || agent.status === 'error') {
              logger.debug('Ignoring agent_thinking - agent already finished', {
                agentId: event.agentId,
                currentStatus: agent.status,
              });
              break;
            }
            
            state.updateAgent(event.agentId, {
              status: 'thinking',
              currentMessage: `Round ${event.roundNumber || 1}`,
            });
          } else if (event.agentType) {
            state.addAgent({
              agentId: event.agentId,
              agentType: event.agentType,
              status: 'thinking',
              currentMessage: `Round ${event.roundNumber || 1}`,
              progress: 0,
            });
            
            logger.info('Registered new agent from agent_thinking', {
              agentId: event.agentId,
              agentType: event.agentType,
              roundNumber: event.roundNumber,
            });
          }

          logger.debug('Agent thinking in conversation', {
            agentId: event.agentId,
            roundNumber: event.roundNumber,
          });
        }
        break;

      case 'agent_message_chunk':
        // Real-time streaming chunk from agent conversation
        if (event.messageId && event.agentId && event.content) {
          // Don't process if streaming has already ended
          if (!state.isStreaming) {
            logger.debug('Ignoring late agent_message_chunk - stream already ended', {
              agentId: event.agentId,
              messageId: event.messageId,
            });
            break;
          }
          
          // Ensure agent exists
          if (!state.agents.byId[event.agentId] && event.agentType) {
            state.addAgent({
              agentId: event.agentId,
              agentType: event.agentType,
              status: 'responding',
              currentMessage: `Round ${event.roundNumber || 1}`,
              progress: 50,
            });
            
            logger.info('Registered new agent from agent_message_chunk', {
              agentId: event.agentId,
              agentType: event.agentType,
            });
          }

          // Update agent status to responding only if not already complete
          const agent = state.agents.byId[event.agentId];
          if (agent && agent.status !== 'complete' && agent.status !== 'error') {
            state.updateAgent(event.agentId, {
              status: 'responding',
              currentMessage: `Round ${event.roundNumber || 1}`,
            });
          }

          // Check if message already exists in agent conversations
          let messageExists = false;
          for (const round of state.agentConversations) {
            if (round.messages.some(m => m.messageId === event.messageId)) {
              messageExists = true;
              break;
            }
          }
          
          if (messageExists) {
            // Append to existing agent message
            state.appendToAgentMessage(event.messageId, event.content);
          } else {
            // Create new agent message with this ID
            state.addAgentMessage({
              messageId: event.messageId,
              agentId: event.agentId,
              agentType: event.agentType!,
              content: event.content,
              roundNumber: event.roundNumber || 1,
              timestamp: event.timestamp || new Date().toISOString(),
            });
          }

          logger.debug('Agent message chunk processed', {
            messageId: event.messageId,
            agentId: event.agentId,
            chunkLength: event.content.length,
            wasAppended: messageExists,
          });
        }
        break;

      case 'agent_message':
        // Agent sent a complete message (or completion marker)
        if (event.messageId && event.agentId) {
          // Ensure agent exists before adding message
          if (!state.agents.byId[event.agentId] && event.agentType) {
            state.addAgent({
              agentId: event.agentId,
              agentType: event.agentType,
              status: 'responding',
              currentMessage: 'Responding...',
              progress: 50,
            });
            
            logger.info('Registered new agent from agent_message', {
              agentId: event.agentId,
              agentType: event.agentType,
            });
          }

          // If content is provided and message doesn't exist, create it
          // (for backward compatibility with non-streaming messages)
          if (event.content && !state.messages.byId[event.messageId]) {
            state.addAgentMessage({
              messageId: event.messageId,
              agentId: event.agentId,
              agentType: event.agentType!,
              content: event.content,
              roundNumber: event.roundNumber || 1,
              timestamp: event.timestamp || new Date().toISOString(),
            });
          }

          // Update agent status to complete
          if (state.agents.byId[event.agentId]) {
            state.updateAgent(event.agentId, {
              status: 'complete',
              currentMessage: undefined,
            });
          }

          logger.info('Agent message completed', {
            messageId: event.messageId,
            agentId: event.agentId,
            roundNumber: event.roundNumber,
          });
        }
        break;

      case 'conversation_round_complete':
        // A round of agent conversation completed
        logger.info('Conversation round complete', {
          roundNumber: event.roundNumber,
          messageCount: event.messageCount,
        });
        break;

      case 'tool_use':
        // Tool is being used (e.g., web search)
        if (event.toolName && event.toolQuery) {
          logger.info('Tool usage started', {
            toolName: event.toolName,
            query: event.toolQuery,
            provider: event.toolProvider,
          });

          const { streamingMessageId } = get();
          if (streamingMessageId) {
            // Add tool usage to the current message
            state.addToolUsage(streamingMessageId, {
              toolName: event.toolName,
              query: event.toolQuery,
              provider: event.toolProvider,
              timestamp: event.timestamp || new Date().toISOString(),
              status: 'pending',
            });
          }
        }
        break;

      case 'tool_result':
        // Tool execution completed with results
        if (event.toolName && event.toolResults) {
          logger.info('Tool usage completed', {
            toolName: event.toolName,
            resultsCount: event.toolResults.length,
            status: event.toolStatus,
          });

          const { streamingMessageId } = get();
          if (streamingMessageId) {
            const message = state.messages.byId[streamingMessageId];
            if (message && message.toolUsage) {
              // Find the most recent pending tool usage of this type
              const toolIndex = message.toolUsage.length - 1;
              
              if (toolIndex >= 0) {
                state.updateToolUsage(streamingMessageId, toolIndex, {
                  results: event.toolResults,
                  status: event.toolStatus || 'complete',
                });
              }
            }
          }
        }
        break;

      default:
        logger.warn('Unknown event type', { type: event.type });
    }
  },
});

