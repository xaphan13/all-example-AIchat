/**
 * History slice - manages conversation history with smart metadata.
 * Stores conversations in state and syncs to localStorage.
 */
import { StateCreator } from 'zustand';
import { HistorySlice, RootStore, ConversationHistory } from '../types';
import { AgentType } from '@/types';

const STORAGE_KEY = 'quorum-conversation-history';
const MAX_HISTORY_ITEMS = 50;

// Generate a smart title from the user's query
const generateTitle = (query: string): string => {
  const maxLength = 50;
  const cleaned = query.trim();
  if (cleaned.length <= maxLength) return cleaned;
  return cleaned.substring(0, maxLength - 3) + '...';
};

// Load history from localStorage
const loadHistoryFromStorage = (): ConversationHistory[] => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    return JSON.parse(stored);
  } catch (error) {
    console.error('Failed to load conversation history:', error);
    return [];
  }
};

// Save history to localStorage
const saveHistoryToStorage = (history: ConversationHistory[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch (error) {
    console.error('Failed to save conversation history:', error);
  }
};

export const createHistorySlice: StateCreator<
  RootStore,
  [],
  [],
  HistorySlice
> = (set, get) => ({
  // State
  conversationHistory: loadHistoryFromStorage(),
  showHistory: false,
  historySearchQuery: '',

  // Actions
  addToHistory: (conversation) => {
    set((state) => {
      // Check if this conversation already exists (update instead of duplicate)
      const existingIndex = state.conversationHistory.findIndex(
        (h) => h.id === conversation.id
      );

      let updatedHistory: ConversationHistory[];
      
      if (existingIndex >= 0) {
        // Update existing conversation
        updatedHistory = [...state.conversationHistory];
        updatedHistory[existingIndex] = {
          ...updatedHistory[existingIndex],
          ...conversation,
          lastUpdated: new Date().toISOString(),
        };
      } else {
        // Add new conversation at the beginning
        updatedHistory = [conversation, ...state.conversationHistory];
        
        // Limit history size (keep starred items though)
        if (updatedHistory.length > MAX_HISTORY_ITEMS) {
          updatedHistory = updatedHistory
            .sort((a, b) => {
              // Keep starred items
              if (a.isStarred && !b.isStarred) return -1;
              if (!a.isStarred && b.isStarred) return 1;
              // Sort by date
              return new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime();
            })
            .slice(0, MAX_HISTORY_ITEMS);
        }
      }

      saveHistoryToStorage(updatedHistory);
      
      return {
        conversationHistory: updatedHistory,
      };
    });
  },

  removeFromHistory: (conversationId) => {
    set((state) => {
      const updatedHistory = state.conversationHistory.filter(
        (h) => h.id !== conversationId
      );
      saveHistoryToStorage(updatedHistory);
      return {
        conversationHistory: updatedHistory,
      };
    });
  },

  toggleStarred: (conversationId) => {
    set((state) => {
      const updatedHistory = state.conversationHistory.map((h) =>
        h.id === conversationId ? { ...h, isStarred: !h.isStarred } : h
      );
      saveHistoryToStorage(updatedHistory);
      return {
        conversationHistory: updatedHistory,
      };
    });
  },

  clearHistory: () => {
    set({
      conversationHistory: [],
      historySearchQuery: '',
    });
    saveHistoryToStorage([]);
  },

  setShowHistory: (show) => {
    set({ showHistory: show });
  },

  setHistorySearchQuery: (query) => {
    set({ historySearchQuery: query });
  },

  // Load a conversation from history
  loadConversation: (conversationId) => {
    const conversation = get().conversationHistory.find(
      (h) => h.id === conversationId
    );
    
    if (!conversation) {
      console.warn('Conversation not found:', conversationId);
      return;
    }

    console.log('Loading conversation:', conversation.title);
    
    // Save current conversation before switching
    get().saveCurrentConversation();
    
    // Reset the current state
    get().clearMessages();
    get().clearAgents();
    get().endStream();
    get().setProcessing(false);
    get().clearError();
    
    // Initialize the conversation (this will restore messages from sessionStorage)
    get().initConversation(conversationId);
  },

  // Create a conversation snapshot from current state
  saveCurrentConversation: () => {
    const state = get();
    const messages = state.messages.allIds.map(id => state.messages.byId[id]);
    
    if (messages.length === 0) {
      return; // Nothing to save
    }

    const userMessages = messages.filter(m => m.role === 'user');
    const assistantMessages = messages.filter(m => m.role === 'assistant');
    
    if (userMessages.length === 0) {
      return; // Need at least one user message
    }

    const firstUserMsg = userMessages[0];
    const firstAssistantMsg = assistantMessages[0];
    
    // Collect unique agent types used
    const agentsUsed = Array.from(
      new Set(
        state.agentConversations.flatMap(round =>
          round.messages.map(m => m.agentType)
        )
      )
    );

    // Generate assistant preview - only show "Processing..." if no assistant message at all
    // If there's an assistant message, use it even if it's short
    let assistantPreview = 'Processing...';
    if (firstAssistantMsg) {
      const content = firstAssistantMsg.content.trim();
      if (content.length > 0) {
        assistantPreview = content.length > 120 
          ? content.substring(0, 120) + '...'
          : content;
      }
    }

    const conversationId = state.conversationId || `conv_${Date.now()}`;
    
    // Check if this conversation already exists in history
    const existingConv = state.conversationHistory.find(c => c.id === conversationId);
    
    const conversation: ConversationHistory = {
      id: conversationId,
      title: generateTitle(firstUserMsg.content),
      timestamp: firstUserMsg.timestamp,
      lastUpdated: new Date().toISOString(),
      userQuery: firstUserMsg.content,
      assistantPreview,
      messageCount: messages.length,
      agentsUsed: agentsUsed as AgentType[],
      conversationRounds: state.agentConversations.length,
      isStarred: existingConv?.isStarred ?? false, // Preserve starred status if exists
    };

    get().addToHistory(conversation);
  },
});

