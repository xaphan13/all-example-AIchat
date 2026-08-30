/**
 * ModeSelector component for switching between Solo and Quorum modes.
 * Solo = Single agent, Quorum = Multi-agent collaboration
 */
import React from 'react';
import { User, Users } from 'lucide-react';
import { useStore } from '@/store';
import { useLogger } from '@/hooks/useLogger';

export const ModeSelector: React.FC = () => {
  const logger = useLogger({ component: 'ModeSelector' });
  const agentMode = useStore((state) => state.settings.agentMode);
  const updateSettings = useStore((state) => state.updateSettings);

  const handleModeChange = (mode: 'solo' | 'quorum') => {
    if (mode !== agentMode) {
      logger.info('Agent mode changed', { from: agentMode, to: mode });
      updateSettings({ agentMode: mode });
    }
  };

  return (
    <div className="mode-selector-container">
      <div className="mode-selector">
        {/* Solo Mode Button */}
        <button
          onClick={() => handleModeChange('solo')}
          className={`mode-option ${agentMode === 'solo' ? 'active' : ''}`}
          aria-label="Solo Mode"
          title="Solo Mode - Single AI agent"
        >
          <User className="w-4 h-4" />
          <span className="mode-label">Solo</span>
        </button>

        {/* Quorum Mode Button */}
        <button
          onClick={() => handleModeChange('quorum')}
          className={`mode-option ${agentMode === 'quorum' ? 'active' : ''}`}
          aria-label="Quorum Mode"
          title="Quorum Mode - Multiple AI agents collaborate"
        >
          <Users className="w-4 h-4" />
          <span className="mode-label">Quorum</span>
        </button>

        {/* Sliding indicator */}
        <div 
          className={`mode-indicator ${agentMode === 'quorum' ? 'translate-to-right' : ''}`}
          aria-hidden="true"
        />
      </div>
    </div>
  );
};

