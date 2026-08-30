/**
 * Token tracking API service
 * Provides functions for accessing token usage statistics and cost calculations
 */

// TODO: apiClient needs to be exported from './api' for this to work
// import { apiClient } from './api';

// Temporary placeholder until apiClient is properly exported
const apiClient = {
  get: async (_url: string) => ({ data: {} as any }),
  post: async (_url: string, _data?: any) => ({ data: {} as any }),
};

export interface ModelPricing {
  model_id: string;
  provider: string;
  input_cost_per_1k: number;
  output_cost_per_1k: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  context_window: number;
}

export interface TokenUsageRecord {
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  cost_breakdown: {
    input: number;
    output: number;
    total: number;
  };
  timestamp: string;
  agent_id?: string;
  request_id?: string;
}

export interface GlobalStats {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  by_model: Record<string, {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    request_count: number;
  }>;
  by_agent: Record<string, {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    request_count: number;
  }>;
  session_count: number;
}

export interface SessionStats {
  session_id: string;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  total_requests: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  usage_by_model: Record<string, {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    request_count: number;
  }>;
  usage_by_agent: Record<string, {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    request_count: number;
  }>;
}

export interface CostCalculation {
  model_id: string;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  estimated_total_tokens: number;
  input_cost: number;
  output_cost: number;
  total_cost: number;
  pricing: {
    input_per_1k: number;
    output_per_1k: number;
    input_per_1m: number;
    output_per_1m: number;
  };
}

export interface CostComparison {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  models: Array<{
    model_id: string;
    provider: string;
    cost: number;
    context_window: number;
  }>;
}

/**
 * Token API client
 */
export const tokenApi = {
  /**
   * Get pricing information for all models
   */
  async getAllPricing(): Promise<{ models: Record<string, ModelPricing>; count: number }> {
    const response = await apiClient.get('/api/tokens/pricing');
    return response.data;
  },

  /**
   * Get pricing information for a specific model
   */
  async getModelPricing(modelId: string): Promise<ModelPricing> {
    const response = await apiClient.get(`/api/tokens/pricing/${modelId}`);
    return response.data;
  },

  /**
   * Calculate cost for specific model and token counts
   */
  async calculateCost(
    modelId: string,
    inputTokens: number,
    outputTokens: number
  ): Promise<CostCalculation> {
    const response = await apiClient.post('/api/tokens/calculate', {
      model_id: modelId,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
    });
    return response.data;
  },

  /**
   * Compare costs across all models
   */
  async compareCosts(inputTokens: number, outputTokens: number): Promise<CostComparison> {
    const response = await apiClient.post('/api/tokens/compare', {
      input_tokens: inputTokens,
      output_tokens: outputTokens,
    });
    return response.data;
  },

  /**
   * Get global token usage statistics
   */
  async getGlobalStats(): Promise<GlobalStats> {
    const response = await apiClient.get('/api/tokens/stats/global');
    return response.data;
  },

  /**
   * Get session-specific token usage statistics
   */
  async getSessionStats(sessionId: string): Promise<SessionStats> {
    const response = await apiClient.get(`/api/tokens/stats/session/${sessionId}`);
    return response.data;
  },

  /**
   * Get recent token usage records
   */
  async getRecentUsage(
    limit = 100,
    modelId?: string,
    agentId?: string
  ): Promise<{ records: TokenUsageRecord[]; count: number }> {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    if (modelId) params.append('model_id', modelId);
    if (agentId) params.append('agent_id', agentId);

    const response = await apiClient.get(`/api/tokens/usage/recent?${params.toString()}`);
    return response.data;
  },

  /**
   * Create a new token tracking session
   */
  async createSession(sessionId: string): Promise<{ session_id: string; start_time: string; status: string }> {
    const response = await apiClient.post(`/api/tokens/session/create/${sessionId}`);
    return response.data;
  },

  /**
   * Close a token tracking session
   */
  async closeSession(sessionId: string): Promise<{ session_id: string; status: string; final_stats: SessionStats }> {
    const response = await apiClient.post(`/api/tokens/session/close/${sessionId}`);
    return response.data;
  },
};

/**
 * Format cost as USD currency
 */
export const formatCost = (cost: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(cost);
};

/**
 * Format token count with thousands separator
 */
export const formatTokens = (tokens: number): string => {
  return new Intl.NumberFormat('en-US').format(tokens);
};

/**
 * Get provider color for UI display
 */
export const getProviderColor = (provider: string): string => {
  const colors: Record<string, string> = {
    openai: '#10a37f',
    anthropic: '#d97757',
    google: '#4285f4',
  };
  return colors[provider.toLowerCase()] || '#6b7280';
};

