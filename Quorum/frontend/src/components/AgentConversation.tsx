/**
 * AgentConversation - Displays multi-agent conversation rounds
 * Shows agents communicating with each other in a collapsible timeline card stack
 */
import { memo, useState, useCallback, useEffect } from 'react';
import { ConversationRound, AgentType } from '@/types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { AgentToolDisplay } from './AgentToolDisplay';
import { parseToolUsage } from '@/utils/toolParser';

// Simple time formatter
const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
};

interface AgentConversationProps {
  rounds: ConversationRound[];
}

const agentColors: Record<AgentType, string> = {
  'claude-sonnet-4.5': 'text-purple-600',
  'claude-sonnet-3.5': 'text-blue-600',
  'gpt-5': 'text-green-600',
};

const agentBgColors: Record<AgentType, string> = {
  'claude-sonnet-4.5': 'bg-purple-100',
  'claude-sonnet-3.5': 'bg-blue-100',
  'gpt-5': 'bg-green-100',
};

const agentNames: Record<AgentType, string> = {
  'claude-sonnet-4.5': 'Claude Main',
  'claude-sonnet-3.5': 'Claude',
  'gpt-5': 'GPT',
};

function AgentConversationComponent({ rounds }: AgentConversationProps) {
  // Track which rounds are expanded (default: latest round expanded)
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(() => {
    if (rounds.length > 0) {
      return new Set([rounds[rounds.length - 1].roundNumber]);
    }
    return new Set();
  });

  // Auto-expand the latest round when new rounds are added
  useEffect(() => {
    if (rounds.length > 0) {
      const latestRound = rounds[rounds.length - 1].roundNumber;
      setExpandedRounds(prev => {
        // Only update if latest round isn't already expanded
        if (!prev.has(latestRound)) {
          return new Set([...prev, latestRound]);
        }
        return prev;
      });
    }
  }, [rounds.length]);

  // Auto-collapse rounds when they become complete
  useEffect(() => {
    rounds.forEach(round => {
      if (round.isComplete) {
        setExpandedRounds(prev => {
          // If this round is expanded and now complete, collapse it
          if (prev.has(round.roundNumber)) {
            const next = new Set(prev);
            next.delete(round.roundNumber);
            return next;
          }
          return prev;
        });
      }
    });
  }, [rounds]);

  const toggleRound = useCallback((roundNumber: number) => {
    setExpandedRounds(prev => {
      const next = new Set(prev);
      if (next.has(roundNumber)) {
        next.delete(roundNumber);
      } else {
        next.add(roundNumber);
      }
      return next;
    });
  }, []);

  const handleKeyPress = useCallback((e: React.KeyboardEvent, roundNumber: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleRound(roundNumber);
    }
  }, [toggleRound]);

  if (rounds.length === 0) {
    return null;
  }

  // Get preview text from first message
  const getRoundPreview = (round: ConversationRound): string => {
    if (round.messages.length === 0) return 'No messages yet...';
    const firstMessage = round.messages[0];
    const preview = firstMessage.content.substring(0, 80);
    return preview.length < firstMessage.content.length ? `${preview}...` : preview;
  };

  // Get unique agent types in round
  const getRoundAgentTypes = (round: ConversationRound): AgentType[] => {
    const types = new Set(round.messages.map(m => m.agentType));
    return Array.from(types);
  };

  return (
    <div className="agent-conversation animate-fade-in-up">
      <div className="agent-conversation-header">
        <h3 className="text-sm font-semibold text-neutral-200 animate-fade-in">Agent Discussion</h3>
        <span className="text-xs text-neutral-400 animate-fade-in animate-stagger-1">
          {rounds.length} round{rounds.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="timeline-container">
        {rounds.map((round, index) => {
          const isExpanded = expandedRounds.has(round.roundNumber);
          const isLatest = index === rounds.length - 1;
          const agentTypes = getRoundAgentTypes(round);
          const statusBadge = round.isComplete ? 'Complete' : isLatest ? 'Active' : 'Pending';
          const statusClass = round.isComplete ? 'status-complete' : isLatest ? 'status-active' : 'status-pending';

          return (
            <div key={round.roundNumber} className="timeline-item">
              {/* Timeline node */}
              <div className="timeline-node-container">
                <button
                  className={`timeline-node ${isLatest ? 'timeline-node-active' : ''} hover-scale press-effect transition-colors-smooth`}
                  onClick={() => toggleRound(round.roundNumber)}
                  aria-label={`Toggle round ${round.roundNumber}`}
                >
                  <span className="timeline-node-number">{round.roundNumber}</span>
                </button>
                {index < rounds.length - 1 && <div className="timeline-line" />}
              </div>

              {/* Round card */}
              <div className={`round-card ${isExpanded ? 'round-card-expanded' : 'round-card-collapsed'} hover-lift transition-colors-smooth`}>
                {/* Card header - always visible */}
                <button
                  className="round-card-header"
                  onClick={() => toggleRound(round.roundNumber)}
                  onKeyDown={(e) => handleKeyPress(e, round.roundNumber)}
                  aria-expanded={isExpanded}
                  aria-controls={`round-content-${round.roundNumber}`}
                >
                  <div className="round-card-header-left">
                    <div className="round-card-title">
                      <span className="round-number">Round {round.roundNumber}</span>
                      <span className={`round-status-badge ${statusClass}`}>{statusBadge}</span>
                    </div>
                    {!isExpanded && (
                      <div className="round-preview">{getRoundPreview(round)}</div>
                    )}
                  </div>
                  
                  <div className="round-card-header-right">
                    <div className="round-agent-avatars">
                      {agentTypes.map(type => (
                        <div
                          key={type}
                          className={`agent-avatar ${agentBgColors[type]}`}
                          title={agentNames[type]}
                        >
                          {agentNames[type].charAt(0)}
                        </div>
                      ))}
                    </div>
                    <div className="round-message-count">
                      {round.messages.length} msg{round.messages.length !== 1 ? 's' : ''}
                    </div>
                    <div className={`expand-icon ${isExpanded ? 'expand-icon-open' : ''}`}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M4 6L8 10L12 6"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>
                </button>

                {/* Card content - collapsible */}
                <div
                  id={`round-content-${round.roundNumber}`}
                  className={`round-card-content ${isExpanded ? 'round-card-content-visible' : ''}`}
                >
                  <div className="round-messages">
                    {round.messages.map((message, msgIndex) => {
                      const { cleanContent, toolUsages } = parseToolUsage(message.content);
                      
                      return (
                        <div key={`${message.messageId}-${msgIndex}`} className="agent-message">
                          <div className="agent-message-header">
                            <div className="agent-message-header-left">
                              <div className={`agent-avatar ${agentBgColors[message.agentType]}`}>
                                {agentNames[message.agentType].charAt(0)}
                              </div>
                              <span className={`agent-name ${agentColors[message.agentType]}`}>
                                {agentNames[message.agentType]}
                              </span>
                            </div>
                            <span className="message-time">
                              {formatTime(message.timestamp)}
                            </span>
                          </div>
                          <div className="agent-message-content">
                            <MarkdownRenderer content={cleanContent} />
                            {toolUsages.length > 0 && (
                              <AgentToolDisplay toolUsages={toolUsages} />
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Memoize to prevent unnecessary re-renders of large conversation trees
export const AgentConversation = memo(AgentConversationComponent, (prevProps, nextProps) => {
  // Only re-render if the rounds array changed (by reference or length)
  if (prevProps.rounds.length !== nextProps.rounds.length) {
    return false;
  }
  
  // If array reference is same, skip re-render
  if (prevProps.rounds === nextProps.rounds) {
    return true;
  }
  
  // Check if any round content changed (shallow comparison)
  for (let i = 0; i < prevProps.rounds.length; i++) {
    const prevRound = prevProps.rounds[i];
    const nextRound = nextProps.rounds[i];
    
    // Check if round itself changed by reference
    if (prevRound !== nextRound) {
      return false;
    }
    
    // Check key properties
    if (prevRound.roundNumber !== nextRound.roundNumber ||
        prevRound.messages.length !== nextRound.messages.length ||
        prevRound.isComplete !== nextRound.isComplete) {
      return false;
    }
    
    // Check if messages array changed by reference
    if (prevRound.messages !== nextRound.messages) {
      return false;
    }
  }
  
  return true; // Props are equal, skip re-render
});
