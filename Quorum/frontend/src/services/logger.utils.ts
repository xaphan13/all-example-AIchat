/**
 * Logger Utility Functions
 * Common patterns and helpers for logging throughout the application
 */

import { logger } from './logger';
import { LogContext } from '@/types/logger';

/**
 * Log a fetch request with details
 */
export function logFetchRequest(
  url: string,
  options: RequestInit = {},
  context?: LogContext
): void {
  logger.info('Fetch request initiated', {
    url,
    method: options.method || 'GET',
    hasBody: !!options.body,
    ...context,
  });
}

/**
 * Log a fetch response
 */
export function logFetchResponse(
  url: string,
  response: Response,
  context?: LogContext
): void {
  if (response.ok) {
    logger.info('Fetch response received', {
      url,
      status: response.status,
      statusText: response.statusText,
      ...context,
    });
  } else {
    logger.warn('Fetch response error', {
      url,
      status: response.status,
      statusText: response.statusText,
      ...context,
    });
  }
}

/**
 * Log a user action (button click, form submission, etc.)
 */
export function logUserAction(
  action: string,
  details?: Record<string, unknown>,
  context?: LogContext
): void {
  logger.info(`User action: ${action}`, {
    action,
    ...details,
    ...context,
    userAction: true,
  });
}

/**
 * Log component render with performance tracking
 */
export function logComponentRender(
  componentName: string,
  props?: Record<string, unknown>,
  context?: LogContext
): void {
  logger.debug(`Component rendered: ${componentName}`, {
    component: componentName,
    props,
    ...context,
  });
}

/**
 * Log state changes
 */
export function logStateChange(
  stateName: string,
  oldValue: unknown,
  newValue: unknown,
  context?: LogContext
): void {
  logger.debug(`State changed: ${stateName}`, {
    stateName,
    oldValue,
    newValue,
    ...context,
  });
}

/**
 * Log navigation events
 */
export function logNavigation(
  from: string,
  to: string,
  context?: LogContext
): void {
  logger.info('Navigation', {
    from,
    to,
    ...context,
    navigation: true,
  });
}

/**
 * Log WebSocket events
 */
export function logWebSocketEvent(
  event: 'open' | 'close' | 'error' | 'message',
  details?: Record<string, unknown>,
  context?: LogContext
): void {
  const logLevel = event === 'error' ? 'error' : 'info';
  
  if (logLevel === 'error') {
    logger.error(`WebSocket ${event}`, details?.error as Error, {
      ...details,
      ...context,
      websocket: true,
    });
  } else {
    logger[logLevel](`WebSocket ${event}`, {
      event,
      ...details,
      ...context,
      websocket: true,
    });
  }
}

/**
 * Log form validation
 */
export function logFormValidation(
  formName: string,
  isValid: boolean,
  errors?: Record<string, string>,
  context?: LogContext
): void {
  if (isValid) {
    logger.debug(`Form valid: ${formName}`, {
      formName,
      isValid,
      ...context,
    });
  } else {
    logger.warn(`Form validation failed: ${formName}`, {
      formName,
      isValid,
      errors,
      ...context,
    });
  }
}

/**
 * Log data loading operations
 */
export function logDataLoading(
  dataType: string,
  status: 'start' | 'success' | 'error',
  details?: Record<string, unknown>,
  context?: LogContext
): void {
  const message = `Data loading ${status}: ${dataType}`;
  
  if (status === 'error') {
    logger.error(message, details?.error as Error, {
      dataType,
      status,
      ...details,
      ...context,
    });
  } else if (status === 'start') {
    logger.debug(message, {
      dataType,
      status,
      ...details,
      ...context,
    });
  } else {
    logger.info(message, {
      dataType,
      status,
      ...details,
      ...context,
    });
  }
}

/**
 * Log cache operations
 */
export function logCacheOperation(
  operation: 'hit' | 'miss' | 'set' | 'clear',
  key: string,
  details?: Record<string, unknown>,
  context?: LogContext
): void {
  logger.debug(`Cache ${operation}`, {
    operation,
    key,
    ...details,
    ...context,
    cache: true,
  });
}

/**
 * Wrap an async function with automatic logging
 */
export function withLogging<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T,
  name: string,
  context?: LogContext
): T {
  return (async (...args: unknown[]) => {
    logger.startPerformance(name, context);
    try {
      const result = await fn(...args);
      logger.endPerformance(name, { status: 'success', ...context });
      return result;
    } catch (error) {
      logger.endPerformance(name, { status: 'error', ...context });
      logger.error(`Error in ${name}`, error as Error, context);
      throw error;
    }
  }) as T;
}

/**
 * Create a scoped logger for a specific feature
 */
export function createFeatureLogger(featureName: string) {
  return {
    debug: (message: string, context?: LogContext) =>
      logger.debug(message, { feature: featureName, ...context }),
    info: (message: string, context?: LogContext) =>
      logger.info(message, { feature: featureName, ...context }),
    warn: (message: string, context?: LogContext) =>
      logger.warn(message, { feature: featureName, ...context }),
    error: (message: string, error?: Error, context?: LogContext) =>
      logger.error(message, error, { feature: featureName, ...context }),
    startPerformance: (name: string, context?: LogContext) =>
      logger.startPerformance(name, { feature: featureName, ...context }),
    endPerformance: (name: string, context?: LogContext) =>
      logger.endPerformance(name, { feature: featureName, ...context }),
  };
}

