/**
 * ChatHistory - Redesigned sidebar with modern UX/UI principles
 * Features: Clean hierarchy, smooth interactions, enhanced accessibility
 */
import { memo, useMemo, useState, useEffect } from 'react';
import { Search, Clock, MessageSquare, Star, Trash2, X, MoreVertical, Archive, Plus } from 'lucide-react';
import { useStore } from '@/store';
import { ConversationHistory } from '@/store/types';
import { AgentType } from '@/types';
import '../styles/chatHistory.css';

// Agent color mappings with enhanced visual design
const agentColors: Record<AgentType, string> = {
  'claude-sonnet-4.5': 'agent-badge-purple',
  'claude-sonnet-3.5': 'agent-badge-blue',
  'gpt-5': 'agent-badge-green',
};

const agentInitials: Record<AgentType, string> = {
  'claude-sonnet-4.5': 'C+',
  'claude-sonnet-3.5': 'C',
  'gpt-5': 'G',
};

// Format timestamp for display
const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  // Format as date
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

// Determine if conversation is recent (for visual weight)
const isRecent = (timestamp: string): boolean => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffHours = (now.getTime() - date.getTime()) / 3600000;
  return diffHours < 24; // Less than 24 hours old
};

const isOlder = (timestamp: string): boolean => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = (now.getTime() - date.getTime()) / 86400000;
  return diffDays > 7; // More than 7 days old
};

interface ConversationCardProps {
  conversation: ConversationHistory;
  isActive: boolean;
  onToggleStar: (id: string) => void;
  onDelete: (id: string) => void;
  onLoad: (id: string) => void;
}

const ConversationCard = memo(({ conversation, isActive, onToggleStar, onDelete, onLoad }: ConversationCardProps) => {
  const [showMenu, setShowMenu] = useState(false);

  const cardClass = [
    'history-card',
    isActive && 'active',
    conversation.isStarred && 'starred',
    isRecent(conversation.lastUpdated) && 'recent',
    isOlder(conversation.lastUpdated) && 'older',
  ].filter(Boolean).join(' ');

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    if (confirm(`Delete "${conversation.title}"?`)) {
      onDelete(conversation.id);
    }
  };

  const handleToggleStar = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    onToggleStar(conversation.id);
  };

  const handleMenuToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(!showMenu);
  };

  return (
    <div
      className={cardClass}
      onClick={() => onLoad(conversation.id)}
      role="button"
      tabIndex={0}
      onKeyPress={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onLoad(conversation.id);
        }
      }}
      aria-label={`Load conversation: ${conversation.title}`}
      aria-current={isActive ? 'true' : 'false'}
    >
      {/* Active Indicator */}
      {isActive && <div className="history-card-active-indicator" />}

      <div className="history-card-content">
        <div className="history-card-header">
          <div className="history-card-title-section">
            <div className="history-card-title">{conversation.title}</div>
          </div>
          
          {/* Quick Actions */}
          <div className="history-card-quick-actions">
            <button
              className={`history-action-button star-button ${conversation.isStarred ? 'starred' : ''}`}
              onClick={handleToggleStar}
              aria-label={conversation.isStarred ? 'Unstar conversation' : 'Star conversation'}
            >
              <Star
                className="w-4 h-4"
                fill={conversation.isStarred ? 'currentColor' : 'none'}
              />
            </button>
            <button
              className="history-action-button menu-button"
              onClick={handleMenuToggle}
              aria-label="More options"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="history-card-footer">
          <div className="history-card-agents">
            {conversation.agentsUsed.slice(0, 3).map((agentType) => (
              <div
                key={agentType}
                className={`history-agent-badge ${agentColors[agentType]}`}
                title={agentType}
              >
                {agentInitials[agentType]}
              </div>
            ))}
            {conversation.agentsUsed.length > 3 && (
              <div className="history-agent-badge agent-badge-more">
                +{conversation.agentsUsed.length - 3}
              </div>
            )}
          </div>

          <div className="history-card-metadata">
            <div className="history-card-meta-item">
              <MessageSquare className="history-card-meta-icon" />
              <span>{conversation.messageCount}</span>
            </div>
            <div className="history-card-meta-item">
              <Clock className="history-card-meta-icon" />
              <span>{formatTimestamp(conversation.lastUpdated)}</span>
            </div>
          </div>
        </div>

        {/* Context Menu */}
        {showMenu && (
          <div className="history-card-menu" onClick={(e) => e.stopPropagation()}>
            <button
              className="history-menu-item"
              onClick={handleToggleStar}
            >
              <Star className="w-4 h-4" fill={conversation.isStarred ? 'currentColor' : 'none'} />
              <span>{conversation.isStarred ? 'Unstar' : 'Star'}</span>
            </button>
            <div className="history-menu-divider" />
            <button
              className="history-menu-item danger"
              onClick={handleDelete}
            >
              <Trash2 className="w-4 h-4" />
              <span>Delete</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

ConversationCard.displayName = 'ConversationCard';

function ChatHistoryComponent() {
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  
  const conversationHistory = useStore((state) => state.conversationHistory);
  const searchQuery = useStore((state) => state.historySearchQuery);
  const conversationId = useStore((state) => state.conversationId);
  
  const setSearchQuery = useStore((state) => state.setHistorySearchQuery);
  const toggleStarred = useStore((state) => state.toggleStarred);
  const removeFromHistory = useStore((state) => state.removeFromHistory);
  const loadConversation = useStore((state) => state.loadConversation);
  const clearHistory = useStore((state) => state.clearHistory);
  const reset = useStore((state) => state.reset);

  // Filter conversations based on search query
  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversationHistory;
    
    const query = searchQuery.toLowerCase();
    return conversationHistory.filter(
      (conv) =>
        conv.title.toLowerCase().includes(query) ||
        conv.userQuery.toLowerCase().includes(query) ||
        conv.assistantPreview.toLowerCase().includes(query)
    );
  }, [conversationHistory, searchQuery]);

  // Group conversations by time period
  const { starred, today, thisWeek, older } = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekStart = new Date(todayStart);
    weekStart.setDate(weekStart.getDate() - 7);

    return {
      starred: filteredConversations.filter((c) => c.isStarred),
      today: filteredConversations.filter((c) => {
        const date = new Date(c.lastUpdated);
        return !c.isStarred && date >= todayStart;
      }),
      thisWeek: filteredConversations.filter((c) => {
        const date = new Date(c.lastUpdated);
        return !c.isStarred && date < todayStart && date >= weekStart;
      }),
      older: filteredConversations.filter((c) => {
        const date = new Date(c.lastUpdated);
        return !c.isStarred && date < weekStart;
      }),
    };
  }, [filteredConversations]);

  const handleClearHistory = () => {
    if (confirm('Clear all conversation history? This cannot be undone.')) {
      clearHistory();
    }
  };

  const handleLoadConversation = (conversationId: string) => {
    loadConversation(conversationId);
  };

  const handleNewChat = () => {
    reset();
    setSearchQuery('');
  };

  // Keyboard shortcut: Cmd/Ctrl + K for new chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        handleNewChat();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const hasSearchQuery = searchQuery.trim().length > 0;

  return (
    <aside className="history-sidebar-permanent" role="complementary" aria-label="Conversation history">
      {/* Header */}
      <div className="history-header">
        {/* New Chat Button */}
        <button
          onClick={handleNewChat}
          className="w-full mb-2.5 px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-lg font-medium text-sm transition-all duration-150 flex items-center justify-center gap-2 border border-blue-500/30 hover:border-blue-500/40 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
          aria-label="Start new chat"
          title="New Chat (⌘K / Ctrl+K)"
        >
          <Plus className="w-4 h-4" strokeWidth={2} />
          <span>New Chat</span>
        </button>

        {/* Enhanced Search */}
        <div className={`history-search-container ${isSearchFocused ? 'focused' : ''} ${hasSearchQuery ? 'has-value' : ''}`}>
          <Search className="history-search-icon" />
          <input
            type="text"
            className="history-search-input"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setIsSearchFocused(false)}
            aria-label="Search conversations"
          />
          {hasSearchQuery && (
            <button
              className="history-search-clear"
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

        {/* Conversation List */}
        <div className="history-list-container">
          {filteredConversations.length === 0 ? (
            <div className="history-empty">
              <div className="history-empty-icon-wrapper">
                <MessageSquare className="history-empty-icon" />
              </div>
              <div className="history-empty-title">
                {searchQuery ? 'No conversations found' : 'No conversation history'}
              </div>
              <div className="history-empty-description">
                {searchQuery
                  ? 'Try a different search term'
                  : 'Your past conversations will appear here for easy access'}
              </div>
            </div>
          ) : (
            <>
              {/* Starred Conversations */}
              {starred.length > 0 && (
                <div className="history-section">
                  <div className="history-section-header">
                    <Star className="w-3.5 h-3.5" />
                    <span>Starred</span>
                    <span className="history-section-count">{starred.length}</span>
                  </div>
                  <div className="history-list">
                    {starred.map((conv) => (
                      <ConversationCard
                        key={conv.id}
                        conversation={conv}
                        isActive={conv.id === conversationId}
                        onToggleStar={toggleStarred}
                        onDelete={removeFromHistory}
                        onLoad={handleLoadConversation}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Today */}
              {today.length > 0 && (
                <div className="history-section">
                  <div className="history-section-header">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Today</span>
                    <span className="history-section-count">{today.length}</span>
                  </div>
                  <div className="history-list">
                    {today.map((conv) => (
                      <ConversationCard
                        key={conv.id}
                        conversation={conv}
                        isActive={conv.id === conversationId}
                        onToggleStar={toggleStarred}
                        onDelete={removeFromHistory}
                        onLoad={handleLoadConversation}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* This Week */}
              {thisWeek.length > 0 && (
                <div className="history-section">
                  <div className="history-section-header">
                    <Clock className="w-3.5 h-3.5" />
                    <span>This Week</span>
                    <span className="history-section-count">{thisWeek.length}</span>
                  </div>
                  <div className="history-list">
                    {thisWeek.map((conv) => (
                      <ConversationCard
                        key={conv.id}
                        conversation={conv}
                        isActive={conv.id === conversationId}
                        onToggleStar={toggleStarred}
                        onDelete={removeFromHistory}
                        onLoad={handleLoadConversation}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Older */}
              {older.length > 0 && (
                <div className="history-section">
                  <div className="history-section-header">
                    <Archive className="w-3.5 h-3.5" />
                    <span>Older</span>
                    <span className="history-section-count">{older.length}</span>
                  </div>
                  <div className="history-list">
                    {older.map((conv) => (
                      <ConversationCard
                        key={conv.id}
                        conversation={conv}
                        isActive={conv.id === conversationId}
                        onToggleStar={toggleStarred}
                        onDelete={removeFromHistory}
                        onLoad={handleLoadConversation}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {filteredConversations.length > 0 && (
          <div className="history-footer">
            <button
              className="history-clear-button"
              onClick={handleClearHistory}
              aria-label="Clear all history"
            >
              <Trash2 className="w-4 h-4" />
              <span>Clear All History</span>
            </button>
          </div>
        )}
      </aside>
  );
}

export const ChatHistory = memo(ChatHistoryComponent);

