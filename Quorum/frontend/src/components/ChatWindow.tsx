/**
 * ChatWindow component - main chat interface.
 * Displays messages and handles scrolling.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Message } from '@/types';
import { MessageBubble } from './MessageBubble';
import { AgentConversation } from './AgentConversation';
import { Loader, ArrowDown } from 'lucide-react';
import { useLogger } from '@/hooks/useLogger';
import { useStore } from '@/store';

interface ChatWindowProps {
  messages: Message[];
  isProcessing: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isProcessing }) => {
  const handleExampleClick = (query: string) => {
    // Find the chat input and set its value
    const chatInput = document.querySelector('textarea') as HTMLTextAreaElement;
    if (chatInput) {
      chatInput.value = query;
      chatInput.dispatchEvent(new Event('input', { bubbles: true }));
      chatInput.focus();
    }
  };
  const logger = useLogger({ component: 'ChatWindow' });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const agentConversations = useStore((state) => state.agentConversations);
  const [isUserScrolledUp, setIsUserScrolledUp] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Check if user is near bottom of scroll
  const isNearBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return true;
    
    const threshold = 150; // pixels from bottom
    const position = container.scrollTop + container.clientHeight;
    const bottom = container.scrollHeight;
    
    return bottom - position < threshold;
  }, []);

  // Handle scroll events to detect manual scrolling
  const handleScroll = useCallback(() => {
    const nearBottom = isNearBottom();
    setIsUserScrolledUp(!nearBottom);
    setShowScrollButton(!nearBottom && messages.length > 0);
  }, [isNearBottom, messages.length]);

  // Scroll to bottom (instant or smooth)
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
    setIsUserScrolledUp(false);
    setShowScrollButton(false);
  }, []);

  // Auto-scroll only if user hasn't manually scrolled up
  useEffect(() => {
    if (!isUserScrolledUp && (messages.length > 0 || agentConversations.length > 0)) {
      logger.debug('Content updated, auto-scrolling to bottom', { 
        messageCount: messages.length,
        conversationRounds: agentConversations.length,
      });
      scrollToBottom('auto');
    }
  }, [messages, agentConversations, isUserScrolledUp, logger, scrollToBottom]);

  return (
    <div 
      ref={scrollContainerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto scrollbar-thin px-6 py-8 relative"
    >
      {messages.length === 0 && !isProcessing ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-center max-w-lg px-4">
            <div className="mb-5 inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 backdrop-blur">
              <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h2 className="text-3xl font-semibold text-neutral-100 mb-3 tracking-tight">
              Ask anything
            </h2>
            <p className="text-neutral-400 text-base leading-relaxed mb-2">
              Multiple AI agents will collaborate to provide comprehensive, 
              well-reasoned answers to your questions.
            </p>
            <div className="mt-10 space-y-3">
              <p className="text-xs uppercase tracking-wider text-neutral-400 font-semibold mb-4 animate-fade-in">Example queries</p>
              <div className="space-y-2.5">
                <button 
                  className="example-query w-full animate-fade-in-up animate-stagger-1 opacity-0 hover-lift press-effect"
                  onClick={() => handleExampleClick("Explain quantum computing")}
                >
                  Explain quantum computing
                </button>
                <button 
                  className="example-query w-full animate-fade-in-up animate-stagger-2 opacity-0 hover-lift press-effect"
                  onClick={() => handleExampleClick("Help me plan a trip to Japan")}
                >
                  Help me plan a trip to Japan
                </button>
                <button 
                  className="example-query w-full animate-fade-in-up animate-stagger-3 opacity-0 hover-lift press-effect"
                  onClick={() => handleExampleClick("Analyze this business idea: AI-powered meal planning")}
                >
                  Analyze this business idea: AI-powered meal planning
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <React.Fragment key={message.id}>
              <MessageBubble 
                message={message} 
                isLatest={index === messages.length - 1}
                isProcessing={isProcessing}
              />
              
              {/* Show agent conversations after user messages */}
              {message.role === 'user' && 
               index === messages.filter(m => m.role === 'user').length - 1 && 
               agentConversations.length > 0 && (
                <AgentConversation rounds={agentConversations} />
              )}
            </React.Fragment>
          ))}
          
          {isProcessing && messages.length > 0 && (
            <div className="processing-indicator animate-fade-in-up">
              <Loader className="w-4 h-4 animate-spin" />
              <span className="text-sm">Processing</span>
            </div>
          )}
        </>
      )}
      <div ref={messagesEndRef} />
      
      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          onClick={() => scrollToBottom('smooth')}
          className="fixed bottom-36 right-6 z-50 p-3 bg-gradient-to-br from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-full shadow-lg transition-all duration-200 hover:scale-110 hover-lift press-effect animate-bounce-subtle focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
        >
          <ArrowDown className="w-5 h-5" />
        </button>
      )}
    </div>
  );
};
