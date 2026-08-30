/**
 * Logger Configuration
 * Central configuration for the logging system
 */

import { LoggerConfig, LogLevel } from '@/types/logger';

const isDevelopment = import.meta.env.MODE === 'development';
const isProduction = import.meta.env.MODE === 'production';

export const loggerConfig: LoggerConfig = {
  // Set log level based on environment
  level: isDevelopment ? LogLevel.DEBUG : LogLevel.INFO,

  // Enable console logging in development, limited in production
  enableConsole: isDevelopment || import.meta.env.VITE_ENABLE_CONSOLE_LOGS === 'true',

  // Enable remote logging in production
  enableRemote: isProduction && import.meta.env.VITE_ENABLE_REMOTE_LOGS !== 'false',

  // Remote logging endpoint (configure as needed)
  remoteEndpoint: import.meta.env.VITE_LOG_ENDPOINT || '/api/logs',

  // Default context shared across all logs
  contextDefaults: {
    environment: import.meta.env.MODE,
    appVersion: import.meta.env.VITE_APP_VERSION || '1.0.0',
    platform: navigator.platform,
    userAgent: navigator.userAgent,
  },

  // Enable performance tracking
  enablePerformanceTracking: true,

  // Batch size for remote logging (number of logs before sending)
  batchSize: 10,

  // Flush interval in milliseconds
  flushInterval: 5000,
};

// Environment-specific log level overrides
export const getLogLevel = (): LogLevel => {
  const envLevel = import.meta.env.VITE_LOG_LEVEL;
  
  if (envLevel) {
    switch (envLevel.toUpperCase()) {
      case 'DEBUG':
        return LogLevel.DEBUG;
      case 'INFO':
        return LogLevel.INFO;
      case 'WARN':
        return LogLevel.WARN;
      case 'ERROR':
        return LogLevel.ERROR;
      case 'NONE':
        return LogLevel.NONE;
    }
  }

  return loggerConfig.level;
};

