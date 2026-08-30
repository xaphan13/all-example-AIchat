/**
 * Token Usage Display Component
 * Shows real-time token usage statistics and cost information
 */

import React, { useEffect, useState } from 'react';
import { tokenApi, GlobalStats, formatCost, formatTokens } from '../services/tokenApi';

export const TokenUsageDisplay: React.FC = () => {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchStats = async () => {
    try {
      const data = await tokenApi.getGlobalStats();
      setStats(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch token usage statistics');
      console.error('Error fetching token stats:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();

    if (autoRefresh) {
      const interval = setInterval(fetchStats, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  if (loading) {
    return (
      <div className="token-usage-loading">
        <div className="loading-spinner"></div>
        <p>Loading token usage statistics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="token-usage-error">
        <p>{error}</p>
        <button onClick={fetchStats}>Retry</button>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div className="token-usage-container">
      <div className="token-usage-header">
        <h2>Token Usage & Costs</h2>
        <div className="token-usage-controls">
          <button onClick={fetchStats} className="refresh-button">
            Refresh
          </button>
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Global Overview */}
      <div className="token-usage-overview">
        <div className="stat-card">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value">{formatTokens(stats.total_requests)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Tokens</div>
          <div className="stat-value">{formatTokens(stats.total_tokens)}</div>
          <div className="stat-breakdown">
            <span>In: {formatTokens(stats.total_input_tokens)}</span>
            <span>Out: {formatTokens(stats.total_output_tokens)}</span>
          </div>
        </div>
        <div className="stat-card cost-card">
          <div className="stat-label">Total Cost</div>
          <div className="stat-value cost-value">{formatCost(stats.total_cost)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sessions</div>
          <div className="stat-value">{stats.session_count}</div>
        </div>
      </div>

      {/* Usage by Model */}
      {Object.keys(stats.by_model).length > 0 && (
        <div className="token-usage-section">
          <h3>Usage by Model</h3>
          <div className="usage-table">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Requests</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_model)
                  .sort(([, a], [, b]) => b.cost - a.cost)
                  .map(([modelId, modelStats]) => (
                    <tr key={modelId}>
                      <td className="model-name">{modelId}</td>
                      <td>{formatTokens(modelStats.request_count)}</td>
                      <td>{formatTokens(modelStats.input_tokens)}</td>
                      <td>{formatTokens(modelStats.output_tokens)}</td>
                      <td>{formatTokens(modelStats.total_tokens)}</td>
                      <td className="cost-cell">{formatCost(modelStats.cost)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Usage by Agent */}
      {Object.keys(stats.by_agent).length > 0 && (
        <div className="token-usage-section">
          <h3>Usage by Agent</h3>
          <div className="usage-table">
            <table>
              <thead>
                <tr>
                  <th>Agent ID</th>
                  <th>Requests</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_agent)
                  .sort(([, a], [, b]) => b.cost - a.cost)
                  .map(([agentId, agentStats]) => (
                    <tr key={agentId}>
                      <td className="agent-name">{agentId}</td>
                      <td>{formatTokens(agentStats.request_count)}</td>
                      <td>{formatTokens(agentStats.input_tokens)}</td>
                      <td>{formatTokens(agentStats.output_tokens)}</td>
                      <td>{formatTokens(agentStats.total_tokens)}</td>
                      <td className="cost-cell">{formatCost(agentStats.cost)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

