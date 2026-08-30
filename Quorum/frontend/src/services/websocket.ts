/**
 * WebSocket service for real-time bidirectional communication.
 * Provides automatic reconnection, heartbeat, and message handling.
 */
import { TaskRequest, StreamEvent } from '@/types';
import { createLogger } from './logger';

const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000';
const logger = createLogger({ component: 'WebSocketService' });

type MessageHandler = (event: StreamEvent) => void;
type ErrorHandler = (error: Error) => void;
type ConnectionHandler = (connected: boolean) => void;

interface WebSocketConfig {
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private connectionId: string | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  
  private config: Required<WebSocketConfig> = {
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
    heartbeatInterval: 30000, // 30 seconds
  };
  
  private isIntentionallyClosed = false;
  private subscriptions: Set<string> = new Set();
  
  constructor(config?: WebSocketConfig) {
    if (config) {
      this.config = { ...this.config, ...config };
    }
  }
  
  /**
   * Connect to the WebSocket server.
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        logger.info('Already connected to WebSocket');
        resolve();
        return;
      }
      
      this.isIntentionallyClosed = false;
      
      try {
        logger.info('Connecting to WebSocket', { url: `${WS_BASE}/ws` });
        this.ws = new WebSocket(`${WS_BASE}/ws`);
        
        this.ws.onopen = () => {
          logger.info('WebSocket connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.notifyConnectionHandlers(true);
          resolve();
          
          // Resubscribe to conversations after reconnection
          this.resubscribe();
        };
        
        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            // Log all messages except ping/pong
            if (message.type !== 'pong' && message.type !== 'ping') {
              logger.info(`📨 WS Message received: ${message.type}`, {
                type: message.type,
                hasContent: !!message.content,
                hasFinalResponse: !!message.finalResponse,
              });
            }
            
            this.handleMessage(message);
          } catch (error) {
            logger.error('Failed to parse WebSocket message', error as Error, {
              data: event.data,
            });
          }
        };
        
        this.ws.onerror = (_event) => {
          logger.error('WebSocket error', new Error('WebSocket error occurred'));
          this.notifyErrorHandlers(new Error('WebSocket connection error'));
        };
        
        this.ws.onclose = (event) => {
          logger.info('WebSocket disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          });
          
          this.stopHeartbeat();
          this.notifyConnectionHandlers(false);
          
          if (!this.isIntentionallyClosed && this.config.autoReconnect) {
            this.attemptReconnect();
          }
        };
        
        // Set a timeout for connection
        setTimeout(() => {
          if (this.ws?.readyState !== WebSocket.OPEN) {
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);
        
      } catch (error) {
        logger.error('Failed to create WebSocket', error as Error);
        reject(error);
      }
    });
  }
  
  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    logger.info('Disconnecting WebSocket');
    this.isIntentionallyClosed = true;
    this.stopHeartbeat();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.connectionId = null;
    this.subscriptions.clear();
  }
  
  /**
   * Send a message to the server.
   */
  private send(message: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      logger.error('Cannot send message - WebSocket not connected', new Error('Not connected'));
      throw new Error('WebSocket not connected');
    }
    
    try {
      this.ws.send(JSON.stringify(message));
      logger.debug('WebSocket message sent', { type: message.type });
    } catch (error) {
      logger.error('Failed to send WebSocket message', error as Error);
      throw error;
    }
  }
  
  /**
   * Subscribe to a conversation.
   */
  subscribe(conversationId: string): void {
    logger.info('Subscribing to conversation', { conversationId });
    this.subscriptions.add(conversationId);
    
    this.send({
      type: 'subscribe',
      conversationId,
    });
  }
  
  /**
   * Unsubscribe from a conversation.
   */
  unsubscribe(conversationId: string): void {
    logger.info('Unsubscribing from conversation', { conversationId });
    this.subscriptions.delete(conversationId);
    
    this.send({
      type: 'unsubscribe',
      conversationId,
    });
  }
  
  /**
   * Send a task request.
   */
  sendTask(task: TaskRequest): void {
    logger.info('Sending task via WebSocket', {
      messageLength: task.message.length,
      conversationId: task.conversationId,
    });
    
    this.send({
      type: 'task',
      task,
    });
  }
  
  /**
   * Stop/cancel an active task.
   */
  stopGeneration(conversationId: string): void {
    logger.info('Stopping generation', { conversationId });
    
    this.send({
      type: 'stop',
      conversationId,
    });
  }
  
  /**
   * Register a message handler.
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.messageHandlers.delete(handler);
    };
  }
  
  /**
   * Register an error handler.
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    
    return () => {
      this.errorHandlers.delete(handler);
    };
  }
  
  /**
   * Register a connection state handler.
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    
    // Call immediately with current state
    handler(this.isConnected());
    
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }
  
  /**
   * Check if WebSocket is connected.
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
  
  /**
   * Get connection ID.
   */
  getConnectionId(): string | null {
    return this.connectionId;
  }
  
  /**
   * Handle incoming message.
   */
  private handleMessage(message: any): void {
    logger.debug('WebSocket message received', { type: message.type });
    
    switch (message.type) {
      case 'connected':
        this.connectionId = message.connectionId;
        logger.info('WebSocket connection established', {
          connectionId: this.connectionId,
        });
        break;
      
      case 'pong':
        // Heartbeat response
        logger.debug('Received heartbeat pong');
        break;
      
      case 'subscribed':
        logger.info('Subscribed to conversation', {
          conversationId: message.conversationId,
        });
        break;
      
      case 'unsubscribed':
        logger.info('Unsubscribed from conversation', {
          conversationId: message.conversationId,
        });
        break;
      
      case 'error':
        logger.error('Server error', new Error(message.error));
        this.notifyErrorHandlers(new Error(message.error));
        break;
      
      default:
        // Treat as stream event
        this.notifyMessageHandlers(message as StreamEvent);
        break;
    }
  }
  
  /**
   * Notify all message handlers.
   */
  private notifyMessageHandlers(event: StreamEvent): void {
    this.messageHandlers.forEach((handler) => {
      try {
        handler(event);
      } catch (error) {
        logger.error('Message handler error', error as Error);
      }
    });
  }
  
  /**
   * Notify all error handlers.
   */
  private notifyErrorHandlers(error: Error): void {
    this.errorHandlers.forEach((handler) => {
      try {
        handler(error);
      } catch (err) {
        logger.error('Error handler error', err as Error);
      }
    });
  }
  
  /**
   * Notify all connection handlers.
   */
  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach((handler) => {
      try {
        handler(connected);
      } catch (error) {
        logger.error('Connection handler error', error as Error);
      }
    });
  }
  
  /**
   * Attempt to reconnect.
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      logger.error(
        'Max reconnection attempts reached',
        new Error(`Failed after ${this.reconnectAttempts} attempts`)
      );
      this.notifyErrorHandlers(
        new Error('Max reconnection attempts reached')
      );
      return;
    }
    
    this.reconnectAttempts++;
    const delay = this.config.reconnectInterval * Math.min(this.reconnectAttempts, 3);
    
    logger.info('Attempting to reconnect', {
      attempt: this.reconnectAttempts,
      maxAttempts: this.config.maxReconnectAttempts,
      delay,
    });
    
    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        logger.error('Reconnection failed', error);
      });
    }, delay);
  }
  
  /**
   * Start heartbeat ping/pong.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        try {
          this.send({ type: 'ping' });
        } catch (error) {
          logger.error('Failed to send heartbeat', error as Error);
        }
      }
    }, this.config.heartbeatInterval);
  }
  
  /**
   * Stop heartbeat.
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
  
  /**
   * Resubscribe to conversations after reconnection.
   */
  private resubscribe(): void {
    if (this.subscriptions.size > 0) {
      logger.info('Resubscribing to conversations', {
        count: this.subscriptions.size,
      });
      
      this.subscriptions.forEach((conversationId) => {
        this.send({
          type: 'subscribe',
          conversationId,
        });
      });
    }
  }
}

// Singleton instance
let wsInstance: WebSocketService | null = null;

/**
 * Get the singleton WebSocket service instance.
 */
export function getWebSocketService(): WebSocketService {
  if (!wsInstance) {
    wsInstance = new WebSocketService();
  }
  return wsInstance;
}

/**
 * Create a new WebSocket service instance (for testing or multiple connections).
 */
export function createWebSocketService(config?: WebSocketConfig): WebSocketService {
  return new WebSocketService(config);
}

