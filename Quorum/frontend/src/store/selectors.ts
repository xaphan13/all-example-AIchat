/**
 * Memoized selectors for optimal performance.
 * 
 * DESIGN PRINCIPLES:
 * 1. Actions are accessed directly (stable references, never change)
 * 2. Selectors are ONLY for derived/computed state
 * 3. Use shallow equality for objects/arrays to prevent re-renders
 * 4. Keep selectors focused and composable
 */
import { RootStore } from './types';
import { Message, AgentState } from '@/types';

// ============================================================================
// Message Selectors
// ============================================================================

/**
 * Get all messages as an array (denormalized).
 * Memoized based on allIds array reference.
 */
export const selectMessages = (state: RootStore): Message[] => {
  return state.messages.allIds.map((id) => state.messages.byId[id]);
};

/**
 * Get message by ID.
 */
export const selectMessageById = (id: string) => (state: RootStore): Message | undefined => {
  return state.messages.byId[id];
};

/**
 * Get messages by agent ID.
 */
export const selectMessagesByAgent = (agentId: string) => (state: RootStore): Message[] => {
  return state.messages.allIds
    .map((id) => state.messages.byId[id])
    .filter((msg) => msg.agentId === agentId);
};

/**
 * Get the last message.
 */
export const selectLastMessage = (state: RootStore): Message | undefined => {
  const ids = state.messages.allIds;
  if (ids.length === 0) return undefined;
  return state.messages.byId[ids[ids.length - 1]];
};

/**
 * Get message count.
 */
export const selectMessageCount = (state: RootStore): number => {
  return state.messages.allIds.length;
};

/**
 * Get messages by role.
 */
export const selectMessagesByRole = (role: 'user' | 'assistant' | 'system') => 
  (state: RootStore): Message[] => {
    return state.messages.allIds
      .map((id) => state.messages.byId[id])
      .filter((msg) => msg.role === role);
  };

// ============================================================================
// Agent Selectors
// ============================================================================

/**
 * Get all agents as an array (denormalized).
 * Memoized based on allIds array reference.
 */
export const selectAgents = (state: RootStore): AgentState[] => {
  return state.agents.allIds.map((id) => state.agents.byId[id]);
};

/**
 * Get active agents (not complete or error).
 */
export const selectActiveAgents = (state: RootStore): AgentState[] => {
  return state.agents.allIds
    .map((id) => state.agents.byId[id])
    .filter((agent) => agent.status !== 'complete' && agent.status !== 'error');
};

/**
 * Get agent by ID.
 */
export const selectAgentById = (id: string) => (state: RootStore): AgentState | undefined => {
  return state.agents.byId[id];
};

/**
 * Get agents by type.
 */
export const selectAgentsByType = (type: string) => (state: RootStore): AgentState[] => {
  return state.agents.allIds
    .map((id) => state.agents.byId[id])
    .filter((agent) => agent.agentType === type);
};

/**
 * Get agent count.
 */
export const selectAgentCount = (state: RootStore): number => {
  return state.agents.allIds.length;
};

/**
 * Get active agent count.
 */
export const selectActiveAgentCount = (state: RootStore): number => {
  return state.agents.allIds
    .map((id) => state.agents.byId[id])
    .filter((agent) => agent.status !== 'complete' && agent.status !== 'error')
    .length;
};

/**
 * Check if any agent is currently working.
 */
export const selectHasActiveAgents = (state: RootStore): boolean => {
  return state.agents.allIds.some((id) => {
    const agent = state.agents.byId[id];
    return agent.status === 'thinking' || agent.status === 'responding';
  });
};

// ============================================================================
// Conversation Selectors
// ============================================================================

/**
 * Get conversation metadata.
 */
export const selectConversationMeta = (state: RootStore) => ({
  conversationId: state.conversationId,
  startTime: state.startTime,
  enableCollaboration: state.enableCollaboration,
  maxSubAgents: state.maxSubAgents,
});

/**
 * Check if conversation is active.
 */
export const selectIsConversationActive = (state: RootStore): boolean => {
  return state.conversationId !== '' && state.conversationId !== null;
};

// ============================================================================
// UI Selectors
// ============================================================================

/**
 * Check if UI is in error state.
 */
export const selectHasError = (state: RootStore): boolean => {
  return state.error !== null && state.error !== undefined;
};

// ============================================================================
// Stream Selectors
// ============================================================================

/**
 * Check if currently streaming.
 */
export const selectIsStreaming = (state: RootStore): boolean => {
  return state.isStreaming;
};

// ============================================================================
// Composite Selectors (combining multiple slices)
// ============================================================================

/**
 * Get conversation summary.
 */
export const selectConversationSummary = (state: RootStore) => ({
  conversationId: state.conversationId,
  messageCount: state.messages.allIds.length,
  agentCount: state.agents.allIds.length,
  activeAgentCount: selectActiveAgentCount(state),
  isProcessing: state.isProcessing,
  hasError: selectHasError(state),
  startTime: state.startTime,
});

/**
 * Get full conversation state for export/debugging.
 */
export const selectFullConversation = (state: RootStore) => ({
  metadata: selectConversationMeta(state),
  messages: selectMessages(state),
  agents: selectAgents(state),
  isProcessing: state.isProcessing,
  error: state.error,
  isStreaming: state.isStreaming,
});

/**
 * Check if system is busy (processing or streaming).
 */
export const selectIsBusy = (state: RootStore): boolean => {
  return state.isProcessing || state.isStreaming;
};

// ============================================================================
// NOTE: Actions are accessed directly, NOT through selectors
// ============================================================================
// 
// ❌ DON'T DO THIS:
//   const { addMessage } = useStore(selectMessageActions);  // Creates new object on every render!
//
// ✅ DO THIS INSTEAD:
//   const addMessage = useStore((state) => state.addMessage);  // Stable reference
//
// Actions in Zustand are stable references that never change, so wrapping them
// in selectors creates unnecessary object allocations and potential re-renders.
//

