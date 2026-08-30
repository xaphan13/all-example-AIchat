/**
 * Main App component - orchestrates the entire UI.
 * Manages streaming communication with the backend via WebSocket.
 */
import { useEffect, useState } from 'react';
import { AlertCircle, Wifi, WifiOff, Settings as SettingsIcon } from 'lucide-react';
import { useStore } from '@/store';
import { selectMessages, selectAgents } from '@/store/selectors';
import { ChatWindow } from '@/components/ChatWindow';
import { ChatInput } from '@/components/ChatInput';
import { AgentPanel } from '@/components/AgentPanel';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Logo } from '@/components/Logo';
import { Settings } from '@/components/Settings';
import { ChatHistory } from '@/components/ChatHistory';
import { useLogger, useWebSocket } from '@/hooks';

function App() {
  const logger = useLogger({ component: 'App', trackMount: true });
  
  // Local state for settings modal
  const [showSettings, setShowSettings] = useState(false);
  
  // WebSocket connection
  const { isConnected, error: wsError, sendTask, stopGeneration } = useWebSocket({ autoConnect: true });
  
  // === DERIVED STATE (using selectors) ===
  // These compute/transform state, so we use selectors
  const messages = useStore(selectMessages);
  const agents = useStore(selectAgents);
  
  // === PRIMITIVE STATE (direct access) ===
  // Primitives (string, number, boolean) are cheap to compare
  const showAgentPanel = useStore((state) => state.showAgentPanel);
  const isProcessing = useStore((state) => state.isProcessing);
  const error = useStore((state) => state.error);
  const autoShowAgentPanel = useStore((state) => state.settings.autoShowAgentPanel);
  const agentMode = useStore((state) => state.settings.agentMode);
  const conversationId = useStore((state) => state.conversationId);
  
  // === ACTIONS (direct access - stable references) ===
  // Actions never change, so direct access is optimal
  const setShowAgentPanel = useStore((state) => state.setShowAgentPanel);
  const setProcessing = useStore((state) => state.setProcessing);
  const setError = useStore((state) => state.setError);
  const clearError = useStore((state) => state.clearError);
  const addMessage = useStore((state) => state.addMessage);
  const loadSettings = useStore((state) => state.loadSettings);
  
  // Load settings on mount
  useEffect(() => {
    logger.info('Loading settings from localStorage');
    loadSettings();
  }, [loadSettings, logger]);

  // Handle WebSocket errors
  useEffect(() => {
    if (wsError) {
      logger.error('WebSocket error', wsError);
      setError(wsError.message);
    }
  }, [wsError, logger, setError]);

  // Automatically show agent panel when agents are active (if enabled in settings)
  useEffect(() => {
    if (autoShowAgentPanel && agents.length > 0 && !showAgentPanel) {
      logger.debug('Auto-showing agent panel due to active agents', { agentCount: agents.length });
      setShowAgentPanel(true);
    }
  }, [agents.length, showAgentPanel, setShowAgentPanel, autoShowAgentPanel, logger]);

  const handleSendMessage = async (message: string) => {
    const perfId = 'send-message';
    logger.startPerformance(perfId, { messageLength: message.length });

    try {
      clearError();

      if (!isConnected) {
        throw new Error('WebSocket not connected. Please refresh the page.');
      }

      logger.info('Sending user message via WebSocket', { 
        messageLength: message.length,
        isConnected 
      });

      // Add user message
      addMessage({
        role: 'user',
        content: message,
      });

      setProcessing(true);

      // Send task via WebSocket (responses come through the WebSocket hook)
      // enableCollaboration is controlled by agentMode: 'quorum' = true, 'solo' = false
      const enableCollaboration = agentMode === 'quorum';
      
      const taskRequest = {
        message,
        enableCollaboration,
        maxSubAgents: 3,
      };

      logger.info('Task request prepared', { 
        agentMode, 
        enableCollaboration,
        maxSubAgents: taskRequest.maxSubAgents 
      });

      sendTask(taskRequest);

      logger.endPerformance(perfId, { status: 'success' });
    } catch (err) {
      logger.error('Error processing task', err as Error, {
        messageLength: message.length,
      });
      logger.endPerformance(perfId, { status: 'error' });
      
      setError(err instanceof Error ? err.message : 'An error occurred');
      setProcessing(false);
    }
  };

  const handleStopGeneration = () => {
    try {
      logger.info('Stopping generation', { conversationId });
      if (conversationId) {
        stopGeneration(conversationId);
      }
    } catch (err) {
      logger.error('Error stopping generation', err as Error);
      setError(err instanceof Error ? err.message : 'Failed to stop generation');
    }
  };

  return (
    <ErrorBoundary>
      <div className="h-screen flex flex-col overflow-hidden">
        {/* Header */}
        <header className="header-clean flex-shrink-0">
          <div className="w-full flex items-center justify-between">
            <Logo size="md" showTagline={false} />

            <div className="flex items-center gap-2.5">
              {/* WebSocket Status Indicator */}
              <div 
                className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs ${
                  isConnected 
                    ? 'bg-green-500/10 text-green-600 dark:text-green-400' 
                    : 'bg-red-500/10 text-red-600 dark:text-red-400'
                }`}
                title={isConnected ? 'Connected' : 'Disconnected'}
              >
                {isConnected ? (
                  <Wifi className="w-3 h-3" />
                ) : (
                  <WifiOff className="w-3 h-3" />
                )}
                <span className="font-medium">
                  {isConnected ? 'Live' : 'Offline'}
                </span>
              </div>
              
              <button
                onClick={() => {
                  logger.debug('Opening settings');
                  setShowSettings(true);
                }}
                className="btn-minimal flex items-center gap-2 hover-lift"
                title="Settings"
              >
                <SettingsIcon className="w-3.5 h-3.5" />
                <span>Settings</span>
              </button>
            </div>
          </div>
        </header>

        {/* Main Content - Three Panel Layout */}
        <main className="flex-1 flex overflow-hidden">
          {/* Left Panel - Chat History (Always Visible) */}
          <div className="history-panel-permanent animate-slide-in-right">
            <ChatHistory />
          </div>

          {/* Center Panel - Chat Window */}
          <div className="flex-1 flex flex-col chat-container-center min-h-0 animate-fade-in">
            <ChatWindow messages={messages} isProcessing={isProcessing} />
            
            {/* Error Display */}
            {error && (
              <div className="error-banner flex-shrink-0 animate-shake">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span className="text-sm">{error}</span>
              </div>
            )}

            {/* Input */}
            <div className="chat-input-wrapper flex-shrink-0">
              <ChatInput
                onSend={handleSendMessage}
                onStop={handleStopGeneration}
                disabled={false}
                isGenerating={isProcessing}
                placeholder="Ask a question..."
              />
            </div>
          </div>

          {/* Right Panel - Agent Panel (Conditional) */}
          {showAgentPanel && (
            <div className="agent-panel-permanent animate-slide-in-left">
              <AgentPanel agents={agents} />
            </div>
          )}
        </main>

        {/* Settings Modal */}
        {showSettings && (
          <Settings onClose={() => setShowSettings(false)} />
        )}
      </div>
    </ErrorBoundary>
  );
}

export default App;

