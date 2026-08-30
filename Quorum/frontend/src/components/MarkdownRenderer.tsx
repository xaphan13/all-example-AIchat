/**
 * MarkdownRenderer - Shared component for rendering markdown content
 * with consistent styling across the application
 */
import React, { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRendererComponent: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({node, className, children, ...props}: any) => {
            const isInline = !className?.includes('language-');
            return isInline ? (
              <code className="inline-code" {...props}>
                {children}
              </code>
            ) : (
              <code className="block-code" {...props}>
                {children}
              </code>
            );
          },
          pre: ({node, children, ...props}) => (
            <pre {...props}>{children}</pre>
          ),
          a: ({node, children, ...props}) => (
            <a className="markdown-link" target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          ),
          p: ({node, children, ...props}) => (
            <p {...props}>{children}</p>
          ),
          ul: ({node, children, ...props}) => (
            <ul {...props}>{children}</ul>
          ),
          ol: ({node, children, ...props}) => (
            <ol {...props}>{children}</ol>
          ),
          li: ({node, children, ...props}) => (
            <li {...props}>{children}</li>
          ),
          h1: ({node, children, ...props}) => (
            <h1 {...props}>{children}</h1>
          ),
          h2: ({node, children, ...props}) => (
            <h2 {...props}>{children}</h2>
          ),
          h3: ({node, children, ...props}) => (
            <h3 {...props}>{children}</h3>
          ),
          blockquote: ({node, children, ...props}) => (
            <blockquote {...props}>{children}</blockquote>
          ),
          table: ({node, children, ...props}) => (
            <table {...props}>{children}</table>
          ),
          th: ({node, children, ...props}) => (
            <th {...props}>{children}</th>
          ),
          td: ({node, children, ...props}) => (
            <td {...props}>{children}</td>
          ),
          hr: ({node, ...props}) => (
            <hr {...props} />
          ),
          img: ({node, ...props}) => (
            <img {...props} alt={props.alt || ''} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

// Memoize to prevent re-parsing markdown on every parent re-render
// This is critical for performance with large markdown content
export const MarkdownRenderer = memo(MarkdownRendererComponent, (prevProps, nextProps) => {
  // Only re-render if content or className changes
  return prevProps.content === nextProps.content && prevProps.className === nextProps.className;
});

