/**
 * Logger Service
 * Main logging service with support for multiple transports, contexts, and performance tracking
 */

import {
  LogLevel,
  LogContext,
  LogEntry,
  LogTransport,
  PerformanceMark,
  LoggerConfig,
} from '@/types/logger';
import { loggerConfig, getLogLevel } from './logger.config';
import { ConsoleTransport } from './transports/ConsoleTransport';
import { RemoteTransport } from './transports/RemoteTransport';

class Logger {
  private config: LoggerConfig;
  private transports: LogTransport[] = [];
  private contextStack: LogContext[] = [];
  private performanceMarks = new Map<string, PerformanceMark>();
  private sessionId: string;

  constructor(config: LoggerConfig) {
    this.config = { ...config, level: getLogLevel() };
    this.sessionId = this.generateSessionId();
    this.initializeTransports();
  }

  private initializeTransports(): void {
    // Add console transport
    if (this.config.enableConsole) {
      this.transports.push(new ConsoleTransport());
    }

    // Add remote transport
    if (this.config.enableRemote && this.config.remoteEndpoint) {
      this.transports.push(
        new RemoteTransport({
          endpoint: this.config.remoteEndpoint,
          batchSize: this.config.batchSize || 10,
          flushInterval: this.config.flushInterval || 5000,
        })
      );
    }

    // Add custom transports
    if (this.config.transports) {
      this.transports.push(...this.config.transports);
    }
  }

  private generateSessionId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Create a child logger with additional context
   */
  createChild(context: LogContext): Logger {
    const child = new Logger(this.config);
    child.contextStack = [...this.contextStack, context];
    child.sessionId = this.sessionId;
    child.transports = this.transports;
    return child;
  }

  /**
   * Set context for subsequent log calls
   */
  setContext(context: LogContext): void {
    this.contextStack.push(context);
  }

  /**
   * Clear the most recent context
   */
  clearContext(): void {
    this.contextStack.pop();
  }

  /**
   * Get merged context from stack and defaults
   */
  private getMergedContext(): LogContext {
    return {
      ...this.config.contextDefaults,
      sessionId: this.sessionId,
      ...Object.assign({}, ...this.contextStack),
    };
  }

  /**
   * Core logging method
   */
  private log(
    level: LogLevel,
    message: string,
    context?: LogContext,
    error?: Error
  ): void {
    if (level < this.config.level) return;

    const mergedContext = {
      ...this.getMergedContext(),
      ...context,
    };

    const entry: LogEntry = {
      message,
      level,
      metadata: {
        timestamp: new Date().toISOString(),
        level,
        context: mergedContext,
        ...(error && {
          error: {
            name: error.name,
            message: error.message,
            stack: error.stack,
          },
          stack: error.stack,
        }),
      },
    };

    // Send to all transports
    this.transports.forEach(transport => {
      try {
        transport.log(entry);
      } catch (err) {
        console.error(`Transport ${transport.name} failed:`, err);
      }
    });
  }

  /**
   * Debug level logging
   */
  debug(message: string, context?: LogContext): void {
    this.log(LogLevel.DEBUG, message, context);
  }

  /**
   * Info level logging
   */
  info(message: string, context?: LogContext): void {
    this.log(LogLevel.INFO, message, context);
  }

  /**
   * Warning level logging
   */
  warn(message: string, context?: LogContext): void {
    this.log(LogLevel.WARN, message, context);
  }

  /**
   * Error level logging
   */
  error(message: string, error?: Error, context?: LogContext): void {
    this.log(LogLevel.ERROR, message, context, error);
  }

  /**
   * Start performance tracking
   */
  startPerformance(name: string, context?: LogContext): void {
    if (!this.config.enablePerformanceTracking) return;

    this.performanceMarks.set(name, {
      name,
      startTime: performance.now(),
      context,
    });
  }

  /**
   * End performance tracking and log duration
   */
  endPerformance(name: string, additionalContext?: LogContext): void {
    if (!this.config.enablePerformanceTracking) return;

    const mark = this.performanceMarks.get(name);
    if (!mark) {
      this.warn(`Performance mark "${name}" not found`);
      return;
    }

    const duration = performance.now() - mark.startTime;
    this.performanceMarks.delete(name);

    this.info(`Performance: ${name}`, {
      ...mark.context,
      ...additionalContext,
      duration: `${duration.toFixed(2)}ms`,
      performanceMark: name,
    });
  }

  /**
   * Measure a function's execution time
   */
  async measure<T>(
    name: string,
    fn: () => T | Promise<T>,
    context?: LogContext
  ): Promise<T> {
    this.startPerformance(name, context);
    try {
      const result = await fn();
      this.endPerformance(name, { status: 'success' });
      return result;
    } catch (error) {
      this.endPerformance(name, { status: 'error' });
      throw error;
    }
  }

  /**
   * Flush all transports
   */
  async flush(): Promise<void> {
    await Promise.all(
      this.transports
        .filter(t => t.flush)
        .map(t => t.flush!())
    );
  }

  /**
   * Update logger configuration
   */
  configure(config: Partial<LoggerConfig>): void {
    this.config = { ...this.config, ...config };
    
    // Reinitialize transports if needed
    if (config.transports || config.enableConsole !== undefined || config.enableRemote !== undefined) {
      this.transports = [];
      this.initializeTransports();
    }
  }
}

// Create and export singleton instance
export const logger = new Logger(loggerConfig);

// Export factory for creating child loggers
export const createLogger = (context: LogContext): Logger => {
  return logger.createChild(context);
};

// Export for testing or custom configurations
export { Logger };

