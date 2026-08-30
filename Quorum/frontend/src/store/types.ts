/**
 * Core store types for the multi-agent system.
 * Defines normalized state structure and action signatures.
 */
import { Message, AgentState, StreamEvent, AgentStatus, AgentMessage, ConversationRound, AgentType, ToolUsage } from '@/types';

// History types
export interface ConversationHistory {
  id: string;
  title: string;
  timestamp: string;
  lastUpdated: string;
  userQuery: string;
  assistantPreview: string;
  messageCount: number;
  agentsUsed: AgentType[];
  conversationRounds: number;
  isStarred: boolean;
}

// ============================================================================
// Normalized State Structure (for O(1) lookups)
// ============================================================================

export interface NormalizedMessages {
  byId: Record<string, Message>;
  allIds: string[];
}

export interface NormalizedAgents {
  byId: Record<string, AgentState>;
  allIds: string[];
}

// ============================================================================
// Slice States
// ============================================================================

export interface ConversationSlice {
  conversationId: string;
  startTime: string | null;
  enableCollaboration: boolean;
  maxSubAgents: number;
  agentConversations: ConversationRound[];
  
  // Actions
  initConversation: (id: string) => void;
  setCollaboration: (enabled: boolean) => void;
  setMaxSubAgents: (max: number) => void;
  addAgentMessage: (message: AgentMessage) => void;
  appendToAgentMessage: (messageId: string, content: string) => void;
  addConversationRound: (round: ConversationRound) => void;
  resetConversation: () => void;
}

export interface MessagesSlice {
  messages: NormalizedMessages;
  
  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => string;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  appendToMessage: (id: string, content: string) => void;
  addToolUsage: (messageId: string, toolUsage: ToolUsage) => void;
  updateToolUsage: (messageId: string, toolIndex: number, updates: Partial<ToolUsage>) => void;
  deleteMessage: (id: string) => void;
  clearMessages: () => void;
}

export interface AgentsSlice {
  agents: NormalizedAgents;
  
  // Actions
  // agentId is optional - if not provided, it will be generated
  addAgent: (agent: Partial<Pick<AgentState, 'agentId'>> & Omit<AgentState, 'agentId'>) => string;
  updateAgent: (id: string, updates: Partial<AgentState>) => void;
  removeAgent: (id: string) => void;
  clearAgents: () => void;
  setAgentStatus: (id: string, status: AgentStatus) => void;
}

export interface UISlice {
  // Ephemeral UI state
  showAgentPanel: boolean;
  isProcessing: boolean;
  error: string | null;
  
  // Input state
  inputValue: string;
  
  // Actions
  setShowAgentPanel: (show: boolean) => void;
  setProcessing: (processing: boolean) => void;
  setError: (error: string | null) => void;
  setInputValue: (value: string) => void;
  clearError: () => void;
}

export interface StreamSlice {
  // Stream processing state
  currentStreamId: string | null;
  isStreaming: boolean;
  lastEventType: StreamEvent['type'] | null;
  lastEventTime: string | null;
  
  // Streaming message buffer
  streamingMessageId: string | null;
  
  // Actions
  handleStreamEvent: (event: StreamEvent) => void;
  startStream: (streamId: string) => void;
  endStream: () => void;
}

export interface Settings {
  openrouterApiKey: string;
  backendUrl: string;
  maxConcurrentAgents: number;
  agentTimeout: number;
  theme: 'light' | 'dark' | 'system';
  enableNotifications: boolean;
  autoShowAgentPanel: boolean;
  agentMode: 'solo' | 'quorum'; // Solo = single agent, Quorum = multi-agent collaboration
  quorumModels: string[]; // Array of model IDs to use in Quorum mode
  quorumRounds: number; // Number of conversation rounds (1-5)
  logLevel: 'debug' | 'info' | 'warn' | 'error';
}

export interface SettingsSlice {
  settings: Settings;
  isSettingsLoaded: boolean;
  updateSettings: (updates: Partial<Settings>) => void;
  resetSettings: () => void;
  loadSettings: () => void;
  saveSettings: (settings: Settings) => void;
  validateApiKey: (provider: 'openrouter', key: string) => boolean;
}

export interface HistorySlice {
  conversationHistory: ConversationHistory[];
  showHistory: boolean;
  historySearchQuery: string;
  
  // Actions
  addToHistory: (conversation: ConversationHistory) => void;
  removeFromHistory: (conversationId: string) => void;
  toggleStarred: (conversationId: string) => void;
  clearHistory: () => void;
  setShowHistory: (show: boolean) => void;
  setHistorySearchQuery: (query: string) => void;
  loadConversation: (conversationId: string) => void;
  saveCurrentConversation: () => void;
}

// ============================================================================
// Combined Store
// ============================================================================

export interface RootStore 
  extends ConversationSlice,
          MessagesSlice,
          AgentsSlice,
          UISlice,
          StreamSlice,
          SettingsSlice,
          HistorySlice {
  // Global actions
  reset: () => void;
}

// ============================================================================
// Middleware Types
// ============================================================================

export interface PersistConfig {
  name: string;
  storage: Storage;
  partialize?: (state: any) => any;
  version: number;
  migrate?: (persistedState: any, version: number) => any;
}

export interface LoggerConfig {
  enabled: boolean;
  collapsed?: boolean;
  filter?: (action: string) => boolean;
}

