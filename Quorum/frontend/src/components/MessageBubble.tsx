/**
 * MessageBubble component for displaying individual chat messages.
 * Supports user and assistant messages with markdown rendering.
 */
import React, { useState, memo } from 'react';
import { motion } from 'framer-motion';
import { User, Bot, Download } from 'lucide-react';
import { Message } from '@/types';
import { formatTimeAgo } from '@/utils/timeUtils';
import { useLogger } from '@/hooks/useLogger';
import { MarkdownRenderer } from './MarkdownRenderer';
import { exportToPDF, generatePDFFilename } from '@/utils/pdfExport';
import { ToolUsageDisplay } from './ToolUsageDisplay';

interface MessageBubbleProps {
  message: Message;
  isLatest?: boolean;
  isProcessing?: boolean;
}

const MessageBubbleComponent: React.FC<MessageBubbleProps> = ({ message, isLatest = false, isProcessing = false }) => {
  const logger = useLogger({ component: 'MessageBubble' });
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const [isExporting, setIsExporting] = useState(false);

  const handleExportPDF = async () => {
    try {
      setIsExporting(true);
      logger.info('Exporting message to PDF', { messageId: message.id });

      const filename = generatePDFFilename('executive-summary');
      exportToPDF(message.content, filename, {
        title: 'Executive Summary',
        author: 'Multi-Agent AI System',
        subject: 'AI-Generated Analysis',
      });

      logger.info('PDF exported successfully', { filename });
    } catch (error) {
      logger.error('Failed to export PDF', error as Error);
    } finally {
      setIsExporting(false);
    }
  };

  if (isSystem) {
    const SystemDiv = isLatest ? motion.div : 'div';
    const systemProps = isLatest ? {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
    } : {};

    return (
      <SystemDiv
        {...systemProps}
        className="flex justify-center my-4"
      >
        <div className="bg-neutral-100 text-neutral-600 text-xs px-4 py-2 rounded-full border border-neutral-200">
          {message.content}
        </div>
      </SystemDiv>
    );
  }

  // Only animate the latest message for performance
  const MessageDiv = isLatest ? motion.div : 'div';
  const messageProps = isLatest ? {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
  } : {};

  return (
    <MessageDiv
      {...messageProps}
      className={`flex gap-4 mb-6 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'avatar-user' : 'avatar-assistant'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4" />
        ) : (
          <Bot className="w-4 h-4" />
        )}
      </div>

      {/* Message Content */}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-2xl flex-1`}>
        <div className={isUser ? 'message-user' : 'message-assistant'}>
          {isUser ? (
            <div className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</div>
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>

        {/* Tool Usage Display */}
        {!isUser && !isSystem && message.toolUsage && message.toolUsage.length > 0 && (
          <div className="mt-3">
            <ToolUsageDisplay tools={message.toolUsage} isProcessing={isProcessing} />
          </div>
        )}

        {/* Export to PDF button for assistant messages when generation is complete */}
        {!isUser && !isSystem && !isProcessing && message.content.length > 100 && (
          <button
            onClick={handleExportPDF}
            disabled={isExporting}
            className="export-pdf-button mt-3 px-3 py-1.5 text-xs font-medium rounded-lg border flex items-center gap-1.5 hover-lift press-effect transition-colors-smooth animate-fade-in-up"
            title="Export to PDF"
          >
            <Download className={`w-3.5 h-3.5 ${isExporting ? 'animate-bounce' : ''}`} />
            <span>{isExporting ? 'Exporting...' : 'Export to PDF'}</span>
          </button>
        )}

        {/* Timestamp */}
        <span className="text-xs text-neutral-500 mt-1.5">
          {formatTimeAgo(message.timestamp)}
        </span>
      </div>
    </MessageDiv>
  );
};

// Memoize to prevent unnecessary re-renders, but not for latest streaming messages
export const MessageBubble = memo(MessageBubbleComponent, (prevProps, nextProps) => {
  // Always re-render the latest message during processing (for smooth streaming)
  if (nextProps.isLatest && nextProps.isProcessing) {
    return false; // Always re-render
  }
  
  // For non-streaming messages, only re-render if content/status changed
  return (
    prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.isLatest === nextProps.isLatest &&
    prevProps.isProcessing === nextProps.isProcessing &&
    prevProps.message.toolUsage === nextProps.message.toolUsage
  );
});

