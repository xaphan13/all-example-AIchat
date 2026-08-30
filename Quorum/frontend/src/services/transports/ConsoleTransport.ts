/**
 * Console Transport
 * Outputs logs to the browser console with beautiful formatting
 */

import { LogTransport, LogEntry, LogLevel } from '@/types/logger';

export class ConsoleTransport implements LogTransport {
  name = 'console';

  private readonly styles = {
    [LogLevel.DEBUG]: 'color: #6B7280; font-weight: normal',
    [LogLevel.INFO]: 'color: #3B82F6; font-weight: normal',
    [LogLevel.WARN]: 'color: #F59E0B; font-weight: bold',
    [LogLevel.ERROR]: 'color: #EF4444; font-weight: bold',
    [LogLevel.NONE]: 'color: #6B7280; font-weight: normal',
  };

  private readonly icons = {
    [LogLevel.DEBUG]: '🔍',
    [LogLevel.INFO]: 'ℹ️',
    [LogLevel.WARN]: '⚠️',
    [LogLevel.ERROR]: '❌',
    [LogLevel.NONE]: '📝',
  };

  log(entry: LogEntry): void {
    const { message, level, metadata } = entry;
    const style = this.styles[level] || '';
    const icon = this.icons[level] || '📝';
    
    // Format the log prefix
    const timestamp = new Date(metadata.timestamp).toLocaleTimeString();
    const levelName = LogLevel[level];
    const context = metadata.context?.component 
      ? `[${metadata.context.component}]` 
      : '';

    const prefix = `${icon} ${timestamp} ${levelName} ${context}`;

    // Choose the appropriate console method
    const consoleMethod = this.getConsoleMethod(level);

    // Log with styling
    consoleMethod(
      `%c${prefix}`,
      style,
      message,
      this.shouldShowMetadata(level) ? metadata : ''
    );

    // Log stack trace for errors
    if (level === LogLevel.ERROR && metadata.stack) {
      console.groupCollapsed('Stack Trace');
      console.error(metadata.stack);
      console.groupEnd();
    }
  }

  private getConsoleMethod(level: LogLevel): typeof console.log {
    switch (level) {
      case LogLevel.DEBUG:
        return console.debug.bind(console);
      case LogLevel.INFO:
        return console.info.bind(console);
      case LogLevel.WARN:
        return console.warn.bind(console);
      case LogLevel.ERROR:
        return console.error.bind(console);
      default:
        return console.log.bind(console);
    }
  }

  private shouldShowMetadata(level: LogLevel): boolean {
    // Show metadata for warnings and errors, or in debug mode
    return level >= LogLevel.WARN || level === LogLevel.DEBUG;
  }
}

