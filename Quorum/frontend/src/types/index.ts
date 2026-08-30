/**
 * Type definitions for the multi-agent system.
 * Matches backend models for type safety across the stack.
 */

export type AgentType = 
  | 'claude-sonnet-4.5'    // Main orchestrator (maps to claude-3-5-sonnet)
  | 'claude-sonnet-3.5'    // Sub-agent (maps to claude-3-5-sonnet)
  | 'gpt-5';               // GPT sub-agent (maps to gpt-4o)

export type AgentStatus = 
  | 'idle'
  | 'thinking'
  | 'responding'
  | 'complete'
  | 'error';

export type MessageRole = 'user' | 'assistant' | 'system';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  agentId?: string;
  toolUsage?: ToolUsage[];
}

export interface ToolUsage {
  toolName: string;
  query?: string;
  provider?: string;
  timestamp: string;
  results?: ToolResult[];
  status: 'pending' | 'complete' | 'error';
}

export interface ToolResult {
  title: string;
  url: string;
  snippet?: string;
  source?: string;
}

export interface AgentMessage {
  messageId: string;
  agentId: string;
  agentType: AgentType;
  content: string;
  roundNumber: number;
  timestamp: string;
  fromAgentId?: string;
  toAgentId?: string | null;
}

export interface ConversationRound {
  roundNumber: number;
  messages: AgentMessage[];
  participatingAgents: string[];
  isComplete: boolean;
}

export interface AgentState {
  agentId: string;
  agentType: AgentType;
  status: AgentStatus;
  currentMessage?: string;
  progress: number;
  startTime?: string;
  endTime?: string;
}

export interface SubAgentQuery {
  agentType: AgentType;
  query: string;
  priority: number;
}

export interface SubAgentResponse {
  agentId: string;
  agentType: AgentType;
  content: string;
}

export interface TaskRequest {
  message: string;
  conversationId?: string;
  maxSubAgents?: number;
  enableCollaboration?: boolean;
}

export interface StreamEvent {
  type: 
    | 'init' 
    | 'agent_status' 
    | 'delegation' 
    | 'sub_agent_response' 
    | 'stream' 
    | 'complete' 
    | 'stream_end' 
    | 'error' 
    | 'cancelled'       // Generation cancelled by user
    | 'agent_message' 
    | 'agent_message_chunk'  // Real-time streaming chunks
    | 'agent_thinking' 
    | 'conversation_round_complete'
    | 'connected'       // WebSocket connection established
    | 'pong'            // Heartbeat response
    | 'subscribed'      // Conversation subscription confirmed
    | 'unsubscribed'    // Conversation unsubscription confirmed
    | 'stop_acknowledged'  // Stop request acknowledged
    | 'stop_failed'     // Stop request failed
    | 'tool_use'        // Tool usage event
    | 'tool_result';    // Tool result event
  conversationId?: string;
  agentId?: string;
  status?: AgentStatus;
  message?: string;
  content?: string;
  isFinal?: boolean;
  isComplete?: boolean;  // For agent_message_chunk completion
  subAgents?: AgentType[];
  queries?: SubAgentQuery[];
  agentType?: AgentType;
  finalResponse?: string;
  partialResponse?: string;  // Partial response when cancelled
  timestamp?: string;
  error?: string;
  success?: boolean;  // For stop acknowledgement
  // Agent conversation fields
  messageId?: string;
  roundNumber?: number;
  messageCount?: number;
  // WebSocket fields
  connectionId?: string;
  // Tool usage fields
  toolName?: string;
  toolQuery?: string;
  toolProvider?: string;
  toolResults?: ToolResult[];
  toolStatus?: 'pending' | 'complete' | 'error';
}

export interface ConversationState {
  conversationId: string;
  messages: Message[];
  activeAgents: AgentState[];
  agentConversations: ConversationRound[];
  isProcessing: boolean;
  error?: string;
}

