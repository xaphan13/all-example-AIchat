/**
 * API service for communicating with the backend.
 * Handles SSE streaming and regular HTTP requests.
 */
import { TaskRequest, StreamEvent } from '@/types';
import { createLogger } from './logger';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const logger = createLogger({ component: 'APIService' });

export class APIService {
  /**
   * Stream task processing with Server-Sent Events.
   */
  static async *streamTask(task: TaskRequest): AsyncGenerator<StreamEvent, void, unknown> {
    logger.info('Starting task stream', { 
      messageLength: task.message.length,
      enableCollaboration: task.enableCollaboration,
      maxSubAgents: task.maxSubAgents,
    });
    logger.startPerformance('streamTask');

    let eventCount = 0;

    try {
      const response = await fetch(`${API_BASE}/api/task/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(task),
      });

      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        logger.error('Stream request failed', error, { 
          status: response.status,
          statusText: response.statusText,
        });
        throw error;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        const error = new Error('Response body is not readable');
        logger.error('Stream reader creation failed', error);
        throw error;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          
          // Process complete SSE messages
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || ''; // Keep incomplete message in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                const event: StreamEvent = JSON.parse(data);
                eventCount++;
                logger.debug('Stream event received', { 
                  eventType: event.type,
                  eventCount,
                });
                yield event;
              } catch (e) {
                logger.error('Failed to parse SSE data', e as Error, { data });
              }
            }
          }
        }

        logger.endPerformance('streamTask', { 
          eventCount,
          status: 'success',
        });
        logger.info('Task stream completed', { eventCount });
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      logger.endPerformance('streamTask', { 
        eventCount,
        status: 'error',
      });
      throw error;
    }
  }

  /**
   * Process task without streaming (get complete result).
   */
  static async processTask(task: TaskRequest): Promise<any> {
    logger.info('Processing task', { messageLength: task.message.length });
    logger.startPerformance('processTask');

    try {
      const response = await fetch(`${API_BASE}/api/task`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(task),
      });

      if (!response.ok) {
        const error = await response.text();
        logger.error('Task processing failed', new Error(error), { 
          status: response.status,
        });
        throw new Error(error || `HTTP ${response.status}`);
      }

      const result = await response.json();
      logger.endPerformance('processTask', { status: 'success' });
      logger.info('Task processed successfully');
      
      return result;
    } catch (error) {
      logger.endPerformance('processTask', { status: 'error' });
      throw error;
    }
  }

  /**
   * Reset the conversation.
   */
  static async resetConversation(): Promise<void> {
    logger.info('Resetting conversation');

    try {
      const response = await fetch(`${API_BASE}/api/reset`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = new Error('Failed to reset conversation');
        logger.error('Reset failed', error, { status: response.status });
        throw error;
      }

      logger.info('Conversation reset successfully');
    } catch (error) {
      logger.error('Reset conversation error', error as Error);
      throw error;
    }
  }

  /**
   * Health check.
   */
  static async healthCheck(): Promise<any> {
    logger.debug('Performing health check');

    try {
      const response = await fetch(`${API_BASE}/health`);
      const result = await response.json();
      
      logger.debug('Health check completed', { healthy: response.ok });
      
      return result;
    } catch (error) {
      logger.error('Health check failed', error as Error);
      throw error;
    }
  }
}

