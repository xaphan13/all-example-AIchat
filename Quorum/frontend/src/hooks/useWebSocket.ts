/**
 * React hook for WebSocket connection management.
 * Handles connection lifecycle, automatic reconnection, and message handling.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { getWebSocketService } from '@/services';
import { useStore } from '@/store';
import { TaskRequest } from '@/types';
import { createLogger } from '@/services/logger';

const logger = createLogger({ component: 'useWebSocket' });

interface UseWebSocketOptions {
  autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { autoConnect = true } = options;
  
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const wsService = useRef(getWebSocketService());
  const handleStreamEvent = useStore((state) => state.handleStreamEvent);
  
  // Connect to WebSocket
  const connect = useCallback(async () => {
    try {
      logger.info('Connecting to WebSocket');
      await wsService.current.connect();
      setError(null);
    } catch (err) {
      logger.error('Failed to connect to WebSocket', err as Error);
      setError(err as Error);
    }
  }, []);
  
  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    logger.info('Disconnecting from WebSocket');
    wsService.current.disconnect();
  }, []);
  
  // Send a task
  const sendTask = useCallback((task: TaskRequest) => {
    try {
      wsService.current.sendTask(task);
    } catch (err) {
      logger.error('Failed to send task', err as Error);
      setError(err as Error);
      throw err;
    }
  }, []);
  
  // Subscribe to a conversation
  const subscribe = useCallback((conversationId: string) => {
    try {
      wsService.current.subscribe(conversationId);
    } catch (err) {
      logger.error('Failed to subscribe', err as Error);
      setError(err as Error);
    }
  }, []);
  
  // Unsubscribe from a conversation
  const unsubscribe = useCallback((conversationId: string) => {
    try {
      wsService.current.unsubscribe(conversationId);
    } catch (err) {
      logger.error('Failed to unsubscribe', err as Error);
      setError(err as Error);
    }
  }, []);
  
  // Stop generation
  const stopGeneration = useCallback((conversationId: string) => {
    try {
      wsService.current.stopGeneration(conversationId);
    } catch (err) {
      logger.error('Failed to stop generation', err as Error);
      setError(err as Error);
      throw err;
    }
  }, []);
  
  // Set up WebSocket event handlers
  useEffect(() => {
    const ws = wsService.current;
    
    // Handle messages - forward to Redux store
    const unsubscribeMessage = ws.onMessage((event) => {
      handleStreamEvent(event);
    });
    
    // Handle errors
    const unsubscribeError = ws.onError((err) => {
      logger.error('WebSocket error', err);
      setError(err);
    });
    
    // Handle connection state changes
    const unsubscribeConnection = ws.onConnectionChange((connected) => {
      setIsConnected(connected);
      if (connected) {
        setError(null);
      }
    });
    
    // Auto-connect if enabled
    if (autoConnect) {
      connect();
    }
    
    // Cleanup on unmount
    return () => {
      unsubscribeMessage();
      unsubscribeError();
      unsubscribeConnection();
      
      if (!autoConnect) {
        disconnect();
      }
    };
  }, [autoConnect, connect, disconnect, handleStreamEvent]);
  
  return {
    isConnected,
    error,
    connect,
    disconnect,
    sendTask,
    subscribe,
    unsubscribe,
    stopGeneration,
  };
}

