/**
 * API client for settings management
 */
import axios from 'axios';
import type { Settings } from '@/store/types';
import { logger } from './logger';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface SettingsResponse {
  id: string;
  openrouterApiKey: string;
  backendUrl: string | null;
  maxConcurrentAgents: number;
  agentTimeout: number;
  embeddingModel: string;
  embeddingDimension: number;
  vectorSimilarityThreshold: number;
  theme: string;
  enableNotifications: boolean;
  autoShowAgentPanel: boolean;
  logLevel: string;
  createdAt: string;
  updatedAt: string;
}

export interface UpdateSettingsRequest {
  openrouterApiKey?: string;
  backendUrl?: string;
  maxConcurrentAgents?: number;
  agentTimeout?: number;
  embeddingModel?: string;
  embeddingDimension?: number;
  vectorSimilarityThreshold?: number;
  theme?: string;
  enableNotifications?: boolean;
  autoShowAgentPanel?: boolean;
  logLevel?: string;
}

export interface ApiKeysValidation {
  configured: {
    openrouter: boolean;
  };
  allConfigured: boolean;
}

/**
 * Convert snake_case API response to camelCase for frontend
 */
function toCamelCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(toCamelCase);
  }
  
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((acc, key) => {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      acc[camelKey] = toCamelCase(obj[key]);
      return acc;
    }, {} as any);
  }
  
  return obj;
}

/**
 * Convert camelCase to snake_case for API requests
 */
function toSnakeCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(toSnakeCase);
  }
  
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((acc, key) => {
      const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
      acc[snakeKey] = toSnakeCase(obj[key]);
      return acc;
    }, {} as any);
  }
  
  return obj;
}

/**
 * Map API response to Settings type
 */
function mapToSettings(response: SettingsResponse): Settings {
  return {
    openrouterApiKey: response.openrouterApiKey || '',
    backendUrl: response.backendUrl || 'http://localhost:8000',
    maxConcurrentAgents: response.maxConcurrentAgents,
    agentTimeout: response.agentTimeout,
    theme: response.theme as 'light' | 'dark' | 'system',
    enableNotifications: response.enableNotifications,
    autoShowAgentPanel: response.autoShowAgentPanel,
    agentMode: (response as any).agentMode || 'quorum', // Default to quorum mode
    quorumModels: (response as any).quorumModels || [
      'anthropic/claude-3-5-haiku',
      'google/gemini-2.0-flash-exp',
      'x-ai/grok-beta',
      'openai/gpt-4o',
    ], // Default to all models enabled
    quorumRounds: (response as any).quorumRounds || 2, // Default to 2 rounds
    logLevel: response.logLevel as 'debug' | 'info' | 'warn' | 'error',
  };
}

class SettingsApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get current settings from the database
   */
  async getSettings(maskKeys: boolean = true): Promise<Settings> {
    try {
      const response = await axios.get<SettingsResponse>(
        `${this.baseUrl}/api/settings`,
        { params: { mask_keys: maskKeys } }
      );
      
      const camelCased = toCamelCase(response.data) as SettingsResponse;
      return mapToSettings(camelCased);
    } catch (error) {
      logger.error('Failed to fetch settings from API', error as Error);
      throw error;
    }
  }

  /**
   * Update settings in the database
   */
  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    try {
      const snakeCased = toSnakeCase(settings);
      
      const response = await axios.put<SettingsResponse>(
        `${this.baseUrl}/api/settings`,
        snakeCased
      );
      
      const camelCased = toCamelCase(response.data) as SettingsResponse;
      return mapToSettings(camelCased);
    } catch (error) {
      logger.error('Failed to update settings', error as Error);
      throw error;
    }
  }

  /**
   * Validate which API keys are configured
   */
  async validateApiKeys(): Promise<ApiKeysValidation> {
    try {
      const response = await axios.get<ApiKeysValidation>(
        `${this.baseUrl}/api/settings/api-keys/validate`
      );
      
      return toCamelCase(response.data) as ApiKeysValidation;
    } catch (error) {
      logger.error('Failed to validate API keys', error as Error);
      throw error;
    }
  }
}

// Export singleton instance
export const settingsApi = new SettingsApiClient();

