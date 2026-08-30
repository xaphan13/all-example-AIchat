/**
 * AgentPanel displays all active agents in a grid.
 * Shows real-time status updates for agent collaboration.
 */
import React, { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { AgentState } from '@/types';
import { AgentCard } from './AgentCard';
import { QuorumSettings } from './QuorumSettings';
import { Users, Settings } from 'lucide-react';
import { useLogger } from '@/hooks/useLogger';
import { useStore } from '@/store';

interface AgentPanelProps {
  agents: AgentState[];
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ agents }) => {
  const logger = useLogger({ component: 'AgentPanel' });
  const [showQuorumSettings, setShowQuorumSettings] = useState(false);
  const agentMode = useStore((state) => state.settings.agentMode);

  useEffect(() => {
    if (agents.length > 0) {
      logger.debug('Active agents updated', { 
        agentCount: agents.length,
        agentTypes: agents.map(a => a.agentType),
        statuses: agents.map(a => a.status),
      });
    }
  }, [agents, logger]);

  // Separate active and completed agents for better organization
  const activeAgents = agents.filter(
    (agent) => agent.status === 'thinking' || agent.status === 'responding'
  );
  const completedAgents = agents.filter(
    (agent) => agent.status === 'complete' || agent.status === 'error' || agent.status === 'idle'
  );
  
  // If settings are open, show settings instead of agents
  if (showQuorumSettings) {
    return <QuorumSettings onClose={() => setShowQuorumSettings(false)} />;
  }

  if (agents.length === 0) {
    return (
      <div className="relative h-full flex flex-col">
        <div className="agent-panel-empty animate-fade-in">
          <Users className="w-10 h-10 text-neutral-500 mx-auto mb-3 animate-pulse-slow" />
          <p className="text-neutral-200 text-sm font-semibold animate-fade-in-up">No active agents</p>
          <p className="text-neutral-400 text-xs mt-1.5 font-medium animate-fade-in-up animate-stagger-1">
            Agents will appear when processing
          </p>
        </div>

        {/* Quorum Settings Button (visible even with no agents) */}
        {agentMode === 'quorum' && (
          <button
            onClick={() => setShowQuorumSettings(true)}
            className="absolute bottom-4 right-4 w-9 h-9 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-400 hover:bg-neutral-750 hover:text-neutral-200 hover:border-neutral-600 transition-colors duration-200 flex items-center justify-center"
            title="Configure Quorum Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in relative h-full flex flex-col">
      {/* Agents Content - Scrollable */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Active Agents Section */}
        {activeAgents.length > 0 && (
          <div className="space-y-3">
            <div className="px-1">
              <h2 className="text-xs uppercase tracking-wider font-bold text-blue-600 flex items-center gap-2 animate-fade-in-up">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 pulse-ring" />
                Active · {activeAgents.length}
              </h2>
            </div>
            <div className="space-y-3">
              <AnimatePresence mode="popLayout">
                {activeAgents.map((agent) => (
                  <AgentCard key={agent.agentId} agent={agent} />
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}

        {/* Divider between active and completed */}
        {activeAgents.length > 0 && completedAgents.length > 0 && (
          <div className="agent-section-divider animate-fade-in" />
        )}

        {/* Completed Agents Section */}
        {completedAgents.length > 0 && (
          <div className="space-y-3">
            <div className="px-1">
              <h2 className="text-xs uppercase tracking-wider font-semibold text-neutral-400 flex items-center gap-2 animate-fade-in-up">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                Completed · {completedAgents.length}
              </h2>
            </div>
            <div className="space-y-3 opacity-60 transition-opacity duration-300">
              <AnimatePresence mode="popLayout">
                {completedAgents.map((agent) => (
                  <AgentCard key={agent.agentId} agent={agent} />
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}

        {/* Spacer for the floating button */}
        {agentMode === 'quorum' && <div className="h-20" />}
      </div>

      {/* Quorum Settings Button (bottom-right within panel, only in Quorum mode) */}
      {agentMode === 'quorum' && (
        <button
          onClick={() => setShowQuorumSettings(true)}
          className="absolute bottom-4 right-4 w-9 h-9 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-400 hover:bg-neutral-750 hover:text-neutral-200 hover:border-neutral-600 transition-colors duration-200 flex items-center justify-center"
          title="Configure Quorum Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

