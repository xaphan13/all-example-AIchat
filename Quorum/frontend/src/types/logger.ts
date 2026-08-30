/**
 * Logger Types
 * Defines all type interfaces for the logging system
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

export interface LogContext {
  component?: string;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  [key: string]: unknown;
}

export interface LogMetadata {
  timestamp: string;
  level: LogLevel;
  context?: LogContext;
  tags?: string[];
  stack?: string;
  [key: string]: unknown;
}

export interface LogEntry {
  message: string;
  level: LogLevel;
  metadata: LogMetadata;
}

export interface LogTransport {
  name: string;
  log(entry: LogEntry): void | Promise<void>;
  flush?(): void | Promise<void>;
}

export interface LoggerConfig {
  level: LogLevel;
  enableConsole: boolean;
  enableRemote: boolean;
  remoteEndpoint?: string;
  contextDefaults?: LogContext;
  transports?: LogTransport[];
  enablePerformanceTracking?: boolean;
  batchSize?: number;
  flushInterval?: number;
}

export interface PerformanceMark {
  name: string;
  startTime: number;
  context?: LogContext;
}

