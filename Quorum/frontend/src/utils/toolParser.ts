/**
 * Tool Parser - Extracts and parses tool usage from agent message content
 * Handles <tool_use>, <tool_result> XML-like tags from Claude's responses
 * Intelligently handles partial/streaming tags during live generation
 */

export interface ParsedToolUsage {
  toolName: string;
  parameters: Record<string, string>;
  result?: string;
  rawContent: string;
  isPartial?: boolean;
}

export interface ParsedContent {
  cleanContent: string;
  toolUsages: ParsedToolUsage[];
}

/**
 * Parses content to extract tool usage tags and clean content.
 * Handles both complete and partial (streaming) tool blocks intelligently.
 */
export function parseToolUsage(content: string): ParsedContent {
  const toolUsages: ParsedToolUsage[] = [];
  let cleanContent = content;

  // First, try to match complete tool_use blocks with optional results
  const completeToolRegex = /<tool_use>\s*<tool_name>(.*?)<\/tool_name>\s*<tool_parameters>([\s\S]*?)<\/tool_parameters>\s*<\/tool_use>(?:\s*<tool_result>([\s\S]*?)<\/tool_result>)?/gi;

  let match;
  while ((match = completeToolRegex.exec(content)) !== null) {
    const [fullMatch, toolName, paramsStr, result] = match;
    
    const parameters = parseParameters(paramsStr);

    toolUsages.push({
      toolName: toolName.trim(),
      parameters,
      result: result?.trim(),
      rawContent: fullMatch,
      isPartial: false,
    });

    cleanContent = cleanContent.replace(fullMatch, '');
  }

  // Handle partial/incomplete tool blocks (during streaming)
  // Match any <tool_use> that hasn't been closed yet or is incomplete
  const partialToolRegex = /<tool_use>(?:(?!<\/tool_use>)[\s\S])*$/gi;
  const partialMatch = partialToolRegex.exec(cleanContent);
  
  if (partialMatch) {
    const partialContent = partialMatch[0];
    
    // Try to extract whatever we can from the partial block
    const nameMatch = /<tool_name>(.*?)(?:<\/tool_name>)?/i.exec(partialContent);
    const paramsMatch = /<tool_parameters>([\s\S]*?)(?:<\/tool_parameters>)?/i.exec(partialContent);
    
    if (nameMatch || paramsMatch) {
      const toolName = nameMatch?.[1]?.trim() || 'Tool';
      const paramsStr = paramsMatch?.[1] || '';
      const parameters = parseParameters(paramsStr);

      toolUsages.push({
        toolName,
        parameters,
        rawContent: partialContent,
        isPartial: true,
      });
    }
    
    // Remove the partial tool block from clean content
    cleanContent = cleanContent.replace(partialContent, '');
  }

  // Also clean up any stray tool-related tags that might appear
  cleanContent = cleanContent
    .replace(/<\/?tool_use>/gi, '')
    .replace(/<\/?tool_name>/gi, '')
    .replace(/<\/?tool_parameters>/gi, '')
    .replace(/<\/?tool_result>/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return {
    cleanContent,
    toolUsages,
  };
}

/**
 * Parse parameter string into key-value pairs
 * Handles JSON-like format and various edge cases
 */
function parseParameters(paramsStr: string): Record<string, string> {
  const parameters: Record<string, string> = {};
  
  if (!paramsStr || !paramsStr.trim()) {
    return parameters;
  }

  // Try JSON parsing first
  try {
    const parsed = JSON.parse(paramsStr);
    if (typeof parsed === 'object' && parsed !== null) {
      Object.entries(parsed).forEach(([key, value]) => {
        parameters[key] = String(value);
      });
      return parameters;
    }
  } catch {
    // Not valid JSON, continue with regex parsing
  }

  // Fallback to regex-based parsing for partial/malformed JSON
  const paramRegex = /"(\w+)"\s*:\s*"([^"]*?)"/g;
  let paramMatch;
  while ((paramMatch = paramRegex.exec(paramsStr)) !== null) {
    parameters[paramMatch[1]] = paramMatch[2];
  }

  // Also try single-quoted strings
  const singleQuoteRegex = /'(\w+)'\s*:\s*'([^']*?)'/g;
  while ((paramMatch = singleQuoteRegex.exec(paramsStr)) !== null) {
    parameters[paramMatch[1]] = paramMatch[2];
  }

  return parameters;
}

/**
 * Extracts search query from parameters
 */
export function extractSearchQuery(parameters: Record<string, string>): string | undefined {
  return parameters.query || parameters.search || parameters.q;
}

/**
 * Formats tool name for display
 */
export function formatToolName(toolName: string): string {
  return toolName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Parses tool result into structured data (if it's a web search)
 */
export function parseToolResult(result: string | undefined): Array<{title: string; url: string; snippet?: string}> | null {
  if (!result) return null;

  try {
    // Try to extract search result info from the result text
    const results: Array<{title: string; url: string; snippet?: string}> = [];
    
    // Look for patterns like "1. [Title](url)" or similar
    const urlRegex = /https?:\/\/[^\s]+/g;
    const urls = result.match(urlRegex);
    
    if (urls && urls.length > 0) {
      urls.forEach((url, idx) => {
        // Try to find title near this URL
        const urlIndex = result.indexOf(url);
        const beforeUrl = result.substring(Math.max(0, urlIndex - 100), urlIndex);
        const titleMatch = beforeUrl.match(/[A-Z][^.!?\n]*(?=[:\n]|$)/);
        
        results.push({
          title: titleMatch?.[0]?.trim() || `Result ${idx + 1}`,
          url: url.trim(),
        });
      });
    }
    
    return results.length > 0 ? results : null;
  } catch (error) {
    return null;
  }
}

