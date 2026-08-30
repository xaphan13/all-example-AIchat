/**
 * Root store - combines all slices with middleware.
 * Provides a single source of truth with normalized state.
 */
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { RootStore } from './types';
import { createConversationSlice } from './slices/conversationSlice';
import { createMessagesSlice } from './slices/messagesSlice';
import { createAgentsSlice } from './slices/agentsSlice';
import { createUISlice } from './slices/uiSlice';
import { createStreamSlice } from './slices/streamSlice';
import { createSettingsSlice } from './slices/settingsSlice';
import { createHistorySlice } from './slices/historySlice';
import { createLogger } from '@/services/logger';

const logger = createLogger({ component: 'RootStore' });

/**
 * Partialize function to exclude ephemeral state from persistence.
 */
const partialize = (state: RootStore) => ({
  // Persist conversation metadata
  conversationId: state.conversationId,
  startTime: state.startTime,
  enableCollaboration: state.enableCollaboration,
  maxSubAgents: state.maxSubAgents,
  agentConversations: state.agentConversations,
  
  // Persist messages (normalized)
  messages: state.messages,
  
  // Persist agents (normalized)
  agents: state.agents,
  
  // Persist settings (managed separately in localStorage, but include in store state)
  settings: state.settings,
  isSettingsLoaded: state.isSettingsLoaded,
  
  // Persist conversation history
  conversationHistory: state.conversationHistory,
  
  // Don't persist UI state (ephemeral)
  // Don't persist stream state (ephemeral)
  // Don't persist showHistory or historySearchQuery (ephemeral UI state)
});

/**
 * Main application store with all slices combined.
 */
export const useStore = create<RootStore>()(
  devtools(
    persist(
      (set, get, api) => ({
        // Combine all slices
        ...createConversationSlice(set, get, api),
        ...createMessagesSlice(set, get, api),
        ...createAgentsSlice(set, get, api),
        ...createUISlice(set, get, api),
        ...createStreamSlice(set, get, api),
        ...createSettingsSlice(set, get, api),
        ...createHistorySlice(set, get, api),

        // Global reset action
        reset: () => {
          logger.info('Global store reset');
          
          // Save current conversation before resetting
          get().saveCurrentConversation();
          
          // Reset all slices
          get().resetConversation();
          get().clearMessages();
          get().clearAgents();
          get().setProcessing(false);
          get().clearError();
          get().endStream();
          // Don't reset settings or history on conversation reset
          
          logger.info('Store reset complete');
        },
      }),
      {
        name: 'quorum-store',
        partialize,
        version: 1,
      }
    ),
    {
      name: 'Quorum Store',
      enabled: import.meta.env.DEV,
    }
  )
);

// Export store type for convenience
export type { RootStore } from './types';

