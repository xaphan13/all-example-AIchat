/**
 * useLogger Hook
 * React hook for accessing the logger with automatic component context
 */

import { useEffect, useMemo } from 'react';
import { createLogger, logger } from '@/services/logger';
import { LogContext } from '@/types/logger';

interface UseLoggerOptions {
  component?: string;
  context?: LogContext;
  trackMount?: boolean;
}

/**
 * Hook to get a logger instance with component context
 */
export function useLogger(options: UseLoggerOptions = {}) {
  const { component, context, trackMount = false } = options;

  const componentLogger = useMemo(() => {
    if (component || context) {
      return createLogger({
        component,
        ...context,
      });
    }
    return logger;
  }, [component, context]);

  useEffect(() => {
    if (trackMount && component) {
      componentLogger.debug(`Component mounted`, { lifecycle: 'mount' });

      return () => {
        componentLogger.debug(`Component unmounted`, { lifecycle: 'unmount' });
      };
    }
  }, [componentLogger, component, trackMount]);

  return componentLogger;
}

/**
 * Hook to automatically log component lifecycle events
 */
export function useLogLifecycle(componentName: string, context?: LogContext) {
  const componentLogger = useLogger({ component: componentName, context });

  useEffect(() => {
    componentLogger.debug(`Mounted`, { lifecycle: 'mount' });

    return () => {
      componentLogger.debug(`Unmounted`, { lifecycle: 'unmount' });
    };
  }, [componentLogger]);

  return componentLogger;
}

/**
 * Hook to track and log performance of effects
 */
export function useLogPerformance(
  name: string,
  fn: () => void | (() => void),
  deps: React.DependencyList,
  context?: LogContext
) {
  useEffect(() => {
    const perfName = `effect:${name}`;
    logger.startPerformance(perfName, context);
    
    const cleanup = fn();
    
    logger.endPerformance(perfName);
    
    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

