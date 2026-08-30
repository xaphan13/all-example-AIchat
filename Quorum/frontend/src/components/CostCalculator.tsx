/**
 * Cost Calculator Component
 * Interactive tool for calculating and comparing costs across models
 */

import React, { useState, useEffect } from 'react';
import { tokenApi, ModelPricing, CostComparison, formatCost, formatTokens } from '../services/tokenApi';

export const CostCalculator: React.FC = () => {
  const [models, setModels] = useState<Record<string, ModelPricing>>({});
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [inputTokens, setInputTokens] = useState<number>(1000);
  const [outputTokens, setOutputTokens] = useState<number>(1000);
  const [comparison, setComparison] = useState<CostComparison | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const data = await tokenApi.getAllPricing();
        setModels(data.models);
        if (Object.keys(data.models).length > 0) {
          setSelectedModel(Object.keys(data.models)[0]);
        }
        setLoading(false);
      } catch (err) {
        console.error('Error loading pricing data:', err);
        setLoading(false);
      }
    };

    loadModels();
  }, []);

  useEffect(() => {
    if (inputTokens > 0 || outputTokens > 0) {
      handleCompare();
    }
  }, [inputTokens, outputTokens]);

  const handleCompare = async () => {
    try {
      const result = await tokenApi.compareCosts(inputTokens, outputTokens);
      setComparison(result);
    } catch (err) {
      console.error('Error comparing costs:', err);
    }
  };

  if (loading) {
    return <div className="cost-calculator-loading">Loading pricing data...</div>;
  }

  const selectedPricing = selectedModel ? models[selectedModel] : null;

  return (
    <div className="cost-calculator-container">
      <div className="cost-calculator-header">
        <h2>Cost Calculator</h2>
        <p>Compare costs across different AI models</p>
      </div>

      <div className="cost-calculator-inputs">
        <div className="input-group">
          <label htmlFor="model-select">Model</label>
          <select
            id="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="model-select"
          >
            {Object.keys(models).map((modelId) => (
              <option key={modelId} value={modelId}>
                {modelId} ({models[modelId].provider})
              </option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <label htmlFor="input-tokens">Input Tokens</label>
          <input
            id="input-tokens"
            type="number"
            min="0"
            value={inputTokens}
            onChange={(e) => setInputTokens(parseInt(e.target.value) || 0)}
            className="token-input"
          />
        </div>

        <div className="input-group">
          <label htmlFor="output-tokens">Output Tokens</label>
          <input
            id="output-tokens"
            type="number"
            min="0"
            value={outputTokens}
            onChange={(e) => setOutputTokens(parseInt(e.target.value) || 0)}
            className="token-input"
          />
        </div>
      </div>

      {selectedPricing && (
        <div className="selected-model-pricing">
          <h3>Selected Model: {selectedModel}</h3>
          <div className="pricing-details">
            <div className="pricing-item">
              <span className="pricing-label">Input Cost:</span>
              <span className="pricing-value">
                ${selectedPricing.input_cost_per_1k.toFixed(4)} per 1K tokens
              </span>
            </div>
            <div className="pricing-item">
              <span className="pricing-label">Output Cost:</span>
              <span className="pricing-value">
                ${selectedPricing.output_cost_per_1k.toFixed(4)} per 1K tokens
              </span>
            </div>
            <div className="pricing-item">
              <span className="pricing-label">Context Window:</span>
              <span className="pricing-value">
                {formatTokens(selectedPricing.context_window)} tokens
              </span>
            </div>
          </div>
        </div>
      )}

      {comparison && (
        <div className="cost-comparison">
          <h3>Cost Comparison</h3>
          <div className="comparison-summary">
            <div className="summary-item">
              <span>Total Tokens:</span>
              <strong>{formatTokens(comparison.total_tokens)}</strong>
            </div>
          </div>

          <div className="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Provider</th>
                  <th>Cost</th>
                  <th>Context Window</th>
                  <th>Ranking</th>
                </tr>
              </thead>
              <tbody>
                {comparison.models.map((model, index) => (
                  <tr
                    key={model.model_id}
                    className={model.model_id === selectedModel ? 'selected-row' : ''}
                  >
                    <td className="model-name">{model.model_id}</td>
                    <td className="provider-name">{model.provider}</td>
                    <td className="cost-cell">
                      <strong>{formatCost(model.cost)}</strong>
                    </td>
                    <td>{formatTokens(model.context_window)}</td>
                    <td className="ranking-cell">
                      {index === 0 ? (
                        <span className="badge cheapest">Cheapest</span>
                      ) : (
                        <span className="badge rank">#{index + 1}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {comparison.models.length > 1 && (
            <div className="comparison-insights">
              <h4>Insights</h4>
              <ul>
                <li>
                  Cheapest option: <strong>{comparison.models[0].model_id}</strong> at{' '}
                  <strong>{formatCost(comparison.models[0].cost)}</strong>
                </li>
                {comparison.models.length > 1 && (
                  <li>
                    Most expensive: <strong>{comparison.models[comparison.models.length - 1].model_id}</strong> at{' '}
                    <strong>{formatCost(comparison.models[comparison.models.length - 1].cost)}</strong>
                  </li>
                )}
                {comparison.models.length > 1 && (
                  <li>
                    Price difference:{' '}
                    <strong>
                      {formatCost(
                        comparison.models[comparison.models.length - 1].cost - comparison.models[0].cost
                      )}
                    </strong>
                    {' '}({(
                      ((comparison.models[comparison.models.length - 1].cost - comparison.models[0].cost) /
                        comparison.models[0].cost) *
                      100
                    ).toFixed(1)}% more)
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

