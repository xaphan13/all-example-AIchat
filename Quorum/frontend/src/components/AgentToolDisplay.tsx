/**
 * AgentToolDisplay - Professional tool usage display for agent conversations
 * Minimal, lightweight design with clear hierarchy
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { ParsedToolUsage, formatToolName, extractSearchQuery, parseToolResult } from '@/utils/toolParser';

interface AgentToolDisplayProps {
  toolUsages: ParsedToolUsage[];
}

export const AgentToolDisplay: React.FC<AgentToolDisplayProps> = ({ toolUsages }) => {
  if (toolUsages.length === 0) return null;

  return (
    <div className="agent-tool-container">
      {toolUsages.map((tool, index) => (
        <ToolUsageCard key={index} tool={tool} />
      ))}
    </div>
  );
};

interface ToolUsageCardProps {
  tool: ParsedToolUsage;
}

const ToolUsageCard: React.FC<ToolUsageCardProps> = ({ tool }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const searchQuery = extractSearchQuery(tool.parameters);
  const parsedResults = parseToolResult(tool.result);

  const getStatusText = () => {
    if (tool.isPartial) return 'Preparing...';
    if (tool.result) return 'Executed';
    if (tool.result === undefined) return 'Pending';
    return 'Failed';
  };

  const getStatusClass = () => {
    if (tool.isPartial) return 'tool-status-preparing';
    if (tool.result) return 'tool-status-executed';
    if (tool.result === undefined) return 'tool-status-pending';
    return 'tool-status-failed';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -3 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="agent-tool-card"
    >
      {/* Header */}
      <div className="agent-tool-header">
        <div className="agent-tool-title">
          <span className="tool-name-text">{formatToolName(tool.toolName)}</span>
          <div className="tool-metadata">
            <span className={`tool-status-badge ${getStatusClass()}`}>
              {tool.isPartial && (
                <span className="tool-status-spinner" aria-label="Loading">⋯</span>
              )}
              {getStatusText()}
            </span>
            {parsedResults && parsedResults.length > 0 && (
              <span className="tool-result-count">{parsedResults.length} results</span>
            )}
          </div>
        </div>
        
        {tool.result && !tool.isPartial && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="agent-tool-expand-btn"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        )}
      </div>

      {/* Query/Parameters */}
      {searchQuery && (
        <div className="agent-tool-query">
          <span className="query-label">Query:</span>
          <span className="query-text">{searchQuery}</span>
        </div>
      )}

      {/* Results - Collapsible */}
      <AnimatePresence>
        {isExpanded && tool.result && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="agent-tool-results"
          >
            {parsedResults && parsedResults.length > 0 ? (
              <div className="tool-results-list">
                <div className="results-header">Sources ({parsedResults.length})</div>
                <div className="results-grid">
                  {parsedResults.slice(0, 5).map((result, idx) => (
                    <motion.a
                      key={idx}
                      href={result.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="result-card"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: idx * 0.04 }}
                    >
                      <span className="result-number">{idx + 1}.</span>
                      <div className="result-content">
                        <span className="result-title">{result.title}</span>
                        <span className="result-url">{new URL(result.url).hostname}</span>
                      </div>
                    </motion.a>
                  ))}
                </div>
                {parsedResults.length > 5 && (
                  <div className="more-results">
                    +{parsedResults.length - 5} more
                  </div>
                )}
              </div>
            ) : (
              <div className="tool-result-text">
                {tool.result.substring(0, 300)}
                {tool.result.length > 300 && '...'}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quick preview when collapsed */}
      {!isExpanded && tool.result && parsedResults && parsedResults.length > 0 && (
        <div className="agent-tool-preview">
          {parsedResults.length} source{parsedResults.length !== 1 ? 's' : ''} • Click to view
        </div>
      )}
    </motion.div>
  );
};

