/**
 * Messages slice - normalized message state for O(1) lookups.
 * Now with sessionStorage persistence for conversation continuity.
 */
import { StateCreator } from 'zustand';
import { MessagesSlice, RootStore } from '../types';
import { Message } from '@/types';

const generateMessageId = () => 
  `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// SessionStorage key for active conversation messages
const getConversationMessagesKey = (conversationId: string) => 
  `quorum-conversation-messages-${conversationId}`;

// Save messages to sessionStorage for the active conversation
const saveMessagesToSession = (conversationId: string, messages: { byId: Record<string, Message>, allIds: string[] }) => {
  if (!conversationId) return;
  try {
    sessionStorage.setItem(
      getConversationMessagesKey(conversationId),
      JSON.stringify(messages)
    );
  } catch (error) {
    console.error('Failed to save messages to sessionStorage:', error);
  }
};

// Clear messages from sessionStorage for a conversation
const clearMessagesFromSession = (conversationId: string) => {
  if (!conversationId) return;
  try {
    sessionStorage.removeItem(getConversationMessagesKey(conversationId));
  } catch (error) {
    console.error('Failed to clear messages from sessionStorage:', error);
  }
};

export const createMessagesSlice: StateCreator<
  RootStore,
  [],
  [],
  MessagesSlice
> = (set) => ({
  // State - normalized structure
  messages: {
    byId: {},
    allIds: [],
  },

  // Actions
  addMessage: (message) => {
    const id = generateMessageId();
    const newMessage: Message = {
      ...message,
      id,
      timestamp: new Date().toISOString(),
    };

    set((state) => {
      const updatedMessages = {
        byId: {
          ...state.messages.byId,
          [id]: newMessage,
        },
        allIds: [...state.messages.allIds, id],
      };

      // Persist to sessionStorage
      saveMessagesToSession(state.conversationId, updatedMessages);

      return { messages: updatedMessages };
    });

    return id;
  },

  updateMessage: (id, updates) => {
    set((state) => {
      if (!state.messages.byId[id]) {
        console.warn(`Message ${id} not found for update`);
        return state;
      }

      const updatedMessages = {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [id]: {
            ...state.messages.byId[id],
            ...updates,
          },
        },
      };

      // Persist to sessionStorage
      saveMessagesToSession(state.conversationId, updatedMessages);

      return { messages: updatedMessages };
    });
  },

  appendToMessage: (id, content) => {
    set((state) => {
      const message = state.messages.byId[id];
      if (!message) {
        console.warn(`Message ${id} not found for append`);
        return state;
      }

      const updatedMessages = {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [id]: {
            ...message,
            content: message.content + content,
          },
        },
      };

      // Don't persist to sessionStorage during streaming (too expensive)
      // Will be persisted on completion or update

      return { messages: updatedMessages };
    });
  },

  addToolUsage: (messageId, toolUsage) => {
    set((state) => {
      const message = state.messages.byId[messageId];
      if (!message) {
        console.warn(`Message ${messageId} not found for tool usage`);
        return state;
      }

      return {
        messages: {
          ...state.messages,
          byId: {
            ...state.messages.byId,
            [messageId]: {
              ...message,
              toolUsage: [...(message.toolUsage || []), toolUsage],
            },
          },
        },
      };
    });
  },

  updateToolUsage: (messageId, toolIndex, updates) => {
    set((state) => {
      const message = state.messages.byId[messageId];
      if (!message || !message.toolUsage || !message.toolUsage[toolIndex]) {
        console.warn(`Tool usage not found for message ${messageId} at index ${toolIndex}`);
        return state;
      }

      const updatedToolUsage = [...message.toolUsage];
      updatedToolUsage[toolIndex] = {
        ...updatedToolUsage[toolIndex],
        ...updates,
      };

      return {
        messages: {
          ...state.messages,
          byId: {
            ...state.messages.byId,
            [messageId]: {
              ...message,
              toolUsage: updatedToolUsage,
            },
          },
        },
      };
    });
  },

  deleteMessage: (id) => {
    set((state) => {
      const { [id]: removed, ...remainingById } = state.messages.byId;
      return {
        messages: {
          byId: remainingById,
          allIds: state.messages.allIds.filter((msgId) => msgId !== id),
        },
      };
    });
  },

  clearMessages: () =>
    set((state) => {
      // Clear from sessionStorage
      if (state.conversationId) {
        clearMessagesFromSession(state.conversationId);
      }

      return {
        messages: {
          byId: {},
          allIds: [],
        },
      };
    }),
});

