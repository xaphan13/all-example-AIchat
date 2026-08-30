/**
 * Agents slice - normalized agent state for O(1) lookups.
 */
import { StateCreator } from 'zustand';
import { AgentsSlice, RootStore } from '../types';
import { AgentState } from '@/types';

const generateAgentId = (type: string) =>
  `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// SessionStorage key for agents
const getConversationAgentListKey = (conversationId: string) =>
  `quorum-conversation-agent-list-${conversationId}`;

// Save agents to sessionStorage
const saveAgentsToSession = (conversationId: string, agents: any) => {
  if (!conversationId) return;
  try {
    sessionStorage.setItem(
      getConversationAgentListKey(conversationId),
      JSON.stringify(agents)
    );
  } catch (error) {
    console.error('Failed to save agents to sessionStorage:', error);
  }
};

export const createAgentsSlice: StateCreator<
  RootStore,
  [],
  [],
  AgentsSlice
> = (set, get) => ({
  // State - normalized structure
  agents: {
    byId: {},
    allIds: [],
  },

  // Actions
  addAgent: (agent) => {
    // Use provided agentId if available (from backend), otherwise generate one
    const id = agent.agentId || generateAgentId(agent.agentType);
    
    // Check if agent already exists
    const existingAgent = get().agents.byId[id];
    if (existingAgent) {
      console.debug(`Agent ${id} already exists, skipping add`);
      return id;
    }

    const newAgent: AgentState = {
      ...agent,
      agentId: id,
      progress: agent.progress ?? 0,
      status: agent.status ?? 'idle',
      startTime: new Date().toISOString(),
    };

    set((state) => {
      const updatedAgents = {
        byId: {
          ...state.agents.byId,
          [id]: newAgent,
        },
        allIds: [...state.agents.allIds, id],
      };
      
      // Save to sessionStorage
      saveAgentsToSession(state.conversationId, updatedAgents);
      
      return { agents: updatedAgents };
    });

    return id;
  },

  updateAgent: (id, updates) => {
    set((state) => {
      const agent = state.agents.byId[id];
      if (!agent) {
        console.warn(`Agent ${id} not found for update`);
        return state;
      }

      // Set endTime if status is complete or error
      const updatedAgent: AgentState = {
        ...agent,
        ...updates,
        ...(updates.status === 'complete' || updates.status === 'error'
          ? { endTime: new Date().toISOString() }
          : {}),
      };

      const updatedAgents = {
        ...state.agents,
        byId: {
          ...state.agents.byId,
          [id]: updatedAgent,
        },
      };
      
      // Save to sessionStorage
      saveAgentsToSession(state.conversationId, updatedAgents);

      return { agents: updatedAgents };
    });
  },

  removeAgent: (id) => {
    set((state) => {
      const { [id]: removed, ...remainingById } = state.agents.byId;
      const updatedAgents = {
        byId: remainingById,
        allIds: state.agents.allIds.filter((agentId) => agentId !== id),
      };
      
      // Save to sessionStorage
      saveAgentsToSession(state.conversationId, updatedAgents);
      
      return { agents: updatedAgents };
    });
  },

  clearAgents: () =>
    set((state) => {
      // Clear from sessionStorage
      if (state.conversationId) {
        try {
          sessionStorage.removeItem(getConversationAgentListKey(state.conversationId));
        } catch (error) {
          console.error('Failed to clear agents from sessionStorage:', error);
        }
      }
      
      return {
        agents: {
          byId: {},
          allIds: [],
        },
      };
    }),

  setAgentStatus: (id, status) => {
    get().updateAgent(id, { status });
  },
});

