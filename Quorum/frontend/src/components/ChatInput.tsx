/**
 * ChatInput component for user message input.
 * Features auto-resize textarea and send button.
 */
import React, { useState, useRef, KeyboardEvent } from 'react';
import { Send, Square } from 'lucide-react';
import { useLogger } from '@/hooks/useLogger';
import { ModeSelector } from './ModeSelector';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isGenerating?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  disabled = false,
  isGenerating = false,
  placeholder = 'Ask the agents anything...',
}) => {
  const logger = useLogger({ component: 'ChatInput' });
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (input.trim() && !disabled && !isGenerating) {
      logger.info('Message sent', { 
        messageLength: input.trim().length,
        wordCount: input.trim().split(/\s+/).length,
      });
      onSend(input.trim());
      setInput('');
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };
  
  const handleStop = () => {
    if (onStop && isGenerating) {
      logger.info('Stop generation requested');
      onStop();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      logger.debug('Enter key pressed, sending message');
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <div className="flex gap-3 items-end">
      {/* Mode Selector on the left */}
      <ModeSelector />
      
      {/* Message Input */}
      <textarea
        ref={textareaRef}
        value={input}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isGenerating}
        rows={1}
        className="input-field-clean resize-none min-h-[52px] max-h-[160px] transition-all duration-200"
      />
      
      {/* Send/Stop Button */}
      {isGenerating ? (
        <button
          onClick={handleStop}
          className="btn-send bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 hover-lift press-effect animate-scale-in"
          aria-label="Stop generation"
          title="Stop generation"
        >
          <Square className="w-4 h-4 animate-pulse" fill="currentColor" />
        </button>
      ) : (
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="btn-send hover-lift press-effect transition-all duration-200"
          aria-label="Send message"
        >
          <Send className={`w-4 h-4 transition-transform duration-200 ${input.trim() ? 'translate-x-0.5 -translate-y-0.5' : ''}`} />
        </button>
      )}
    </div>
  );
};

