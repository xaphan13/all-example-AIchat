/**
 * Remote Transport
 * Sends logs to a remote endpoint with batching and retry logic
 */

import { LogTransport, LogEntry } from '@/types/logger';

interface RemoteTransportConfig {
  endpoint: string;
  batchSize: number;
  flushInterval: number;
  maxRetries?: number;
  retryDelay?: number;
}

export class RemoteTransport implements LogTransport {
  name = 'remote';
  
  private batch: LogEntry[] = [];
  private flushTimer: number | null = null;
  private readonly config: Required<RemoteTransportConfig>;

  constructor(config: RemoteTransportConfig) {
    this.config = {
      maxRetries: 3,
      retryDelay: 1000,
      ...config,
    };

    // Setup periodic flush
    this.scheduleFlush();

    // Flush on page unload
    window.addEventListener('beforeunload', () => {
      this.flushSync();
    });
  }

  log(entry: LogEntry): void {
    this.batch.push(entry);

    if (this.batch.length >= this.config.batchSize) {
      this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.batch.length === 0) return;

    const logsToSend = [...this.batch];
    this.batch = [];

    try {
      await this.sendLogs(logsToSend);
    } catch (error) {
      // Re-add failed logs to batch for retry
      this.batch.unshift(...logsToSend);
      console.error('Failed to send logs to remote endpoint:', error);
    }
  }

  private async sendLogs(logs: LogEntry[], retryCount = 0): Promise<void> {
    try {
      const response = await fetch(this.config.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ logs }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      if (retryCount < this.config.maxRetries) {
        // Exponential backoff
        const delay = this.config.retryDelay * Math.pow(2, retryCount);
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.sendLogs(logs, retryCount + 1);
      }
      throw error;
    }
  }

  private scheduleFlush(): void {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
    }

    this.flushTimer = window.setTimeout(() => {
      this.flush();
      this.scheduleFlush();
    }, this.config.flushInterval);
  }

  private flushSync(): void {
    if (this.batch.length === 0) return;

    // Use sendBeacon for synchronous sending on unload
    const data = JSON.stringify({ logs: this.batch });
    navigator.sendBeacon(this.config.endpoint, data);
    this.batch = [];
  }
}

