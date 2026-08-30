/**
 * QuorumSettings component - Configure Quorum mode settings
 * Allows users to select which AI models participate in Quorum conversations
 * and configure the number of conversation rounds.
 */
import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Settings as SettingsIcon, 
  X, 
  Users, 
  MessageCircle, 
  CheckCircle2, 
  Circle,
  Info,
  Sparkles
} from 'lucide-react';
import { useStore } from '@/store';
import { useLogger } from '@/hooks';

interface QuorumSettingsProps {
  onClose: () => void;
}

// Available models for Quorum delegation
export interface QuorumModel {
  id: string;
  name: string;
  displayName: string;
  description: string;
  icon: string;
  color: string;
}

export const AVAILABLE_QUORUM_MODELS: QuorumModel[] = [
  {
    id: 'anthropic/claude-3-5-haiku',
    name: 'claude-haiku-3.5',
    displayName: 'Claude 3.5 Haiku',
    description: 'Fast and efficient, great for quick analysis',
    icon: '⚡',
    color: 'from-orange-500 to-amber-500',
  },
  {
    id: 'google/gemini-2.0-flash-exp',
    name: 'gemini-2.0-flash',
    displayName: 'Gemini 2.0 Flash',
    description: 'Multimodal and creative thinking',
    icon: '✨',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    id: 'x-ai/grok-beta',
    name: 'grok-beta',
    displayName: 'Grok Beta',
    description: 'Real-time data and unique perspectives',
    icon: '🚀',
    color: 'from-purple-500 to-pink-500',
  },
  {
    id: 'openai/gpt-4o',
    name: 'gpt-4o',
    displayName: 'GPT-4o',
    description: 'Balanced reasoning and creativity',
    icon: '🎯',
    color: 'from-green-500 to-emerald-500',
  },
];

export const QuorumSettings: React.FC<QuorumSettingsProps> = ({ onClose }) => {
  const logger = useLogger({ component: 'QuorumSettings' });
  const settings = useStore((state) => state.settings);
  const updateSettings = useStore((state) => state.updateSettings);

  // Local state
  const [selectedModels, setSelectedModels] = useState<string[]>(
    settings.quorumModels || []
  );
  const [rounds, setRounds] = useState<number>(settings.quorumRounds || 2);
  const [hasChanges, setHasChanges] = useState(false);

  // Track changes
  useEffect(() => {
    const modelsChanged = JSON.stringify(selectedModels) !== JSON.stringify(settings.quorumModels || []);
    const roundsChanged = rounds !== settings.quorumRounds;
    setHasChanges(modelsChanged || roundsChanged);
  }, [selectedModels, rounds, settings.quorumModels, settings.quorumRounds]);

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(modelId)) {
        // Don't allow deselecting if it's the only one
        if (prev.length === 1) {
          logger.warn('Cannot deselect the only active model');
          return prev;
        }
        return prev.filter((id) => id !== modelId);
      } else {
        return [...prev, modelId];
      }
    });
  };

  const handleSave = () => {
    logger.info('Saving Quorum settings', { selectedModels, rounds });
    updateSettings({
      quorumModels: selectedModels,
      quorumRounds: rounds,
    });
    onClose();
  };

  const handleCancel = () => {
    if (hasChanges) {
      if (confirm('You have unsaved changes. Are you sure you want to cancel?')) {
        onClose();
      }
    } else {
      onClose();
    }
  };

  return (
    <div className="h-full flex flex-col">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 10 }}
        transition={{ duration: 0.2 }}
        className="h-full flex flex-col"
      >
        {/* Header */}
        <div className="quorum-settings-header">
          <div className="flex items-center gap-3">
            <div className="quorum-settings-icon-wrapper">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="quorum-settings-title">Quorum Configuration</h2>
              <p className="quorum-settings-subtitle">
                Configure AI models and conversation rounds
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="quorum-close-button hover-scale press-effect"
            title="Close settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="quorum-settings-content">
          {/* Info Banner */}
          <div className="quorum-info-banner">
            <Info className="w-4 h-4 flex-shrink-0" />
            <p>
              Multiple AI models collaborate in rounds to provide comprehensive, well-reasoned answers.
            </p>
          </div>

          {/* Model Selection */}
          <section className="quorum-section">
            <div className="quorum-section-header">
              <Users className="w-5 h-5 text-blue-400" />
              <div>
                <h3 className="quorum-section-title">Active Models</h3>
                <p className="quorum-section-description">
                  Select which AI models participate in Quorum discussions
                </p>
              </div>
            </div>

            <div className="quorum-models-grid">
              {AVAILABLE_QUORUM_MODELS.map((model) => {
                const isSelected = selectedModels.includes(model.id);
                return (
                  <motion.button
                    key={model.id}
                    onClick={() => toggleModel(model.id)}
                    className={`quorum-model-card ${isSelected ? 'quorum-model-card-selected' : ''}`}
                    whileTap={{ scale: 0.98 }}
                    whileHover={{ scale: 1.02 }}
                  >
                    <div className="quorum-model-card-header">
                      <div className="flex items-center gap-3 flex-1">
                        <div className={`quorum-model-icon bg-gradient-to-br ${model.color}`}>
                          <span className="text-lg">{model.icon}</span>
                        </div>
                        <div className="text-left flex-1">
                          <h4 className="quorum-model-name">{model.displayName}</h4>
                          <p className="quorum-model-description">{model.description}</p>
                        </div>
                      </div>
                      <div className="quorum-model-checkbox">
                        {isSelected ? (
                          <CheckCircle2 className="w-5 h-5 text-blue-500" />
                        ) : (
                          <Circle className="w-5 h-5 text-neutral-500" />
                        )}
                      </div>
                    </div>
                  </motion.button>
                );
              })}
            </div>

            <p className="quorum-selected-count">
              {selectedModels.length} {selectedModels.length === 1 ? 'model' : 'models'} selected
            </p>
          </section>

          {/* Rounds Configuration */}
          <section className="quorum-section">
            <div className="quorum-section-header">
              <MessageCircle className="w-5 h-5 text-purple-400" />
              <div>
                <h3 className="quorum-section-title">Conversation Rounds</h3>
                <p className="quorum-section-description">
                  Number of discussion rounds between AI models (1-5)
                </p>
              </div>
            </div>

            <div className="quorum-rounds-container">
              <div className="quorum-rounds-display">
                <span className="quorum-rounds-number">{rounds}</span>
                <span className="quorum-rounds-label">
                  {rounds === 1 ? 'Round' : 'Rounds'}
                </span>
              </div>

              <div className="quorum-slider-wrapper">
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={rounds}
                  onChange={(e) => setRounds(parseInt(e.target.value))}
                  className="quorum-slider"
                />
                <div className="quorum-slider-labels">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <span
                      key={n}
                      className={`quorum-slider-label ${rounds === n ? 'active' : ''}`}
                    >
                      {n}
                    </span>
                  ))}
                </div>
              </div>

              <p className="quorum-rounds-hint">
                More rounds provide deeper analysis but take longer to complete
              </p>
            </div>
          </section>
        </div>

        {/* Footer Actions */}
        <div className="quorum-settings-footer">
          <button
            onClick={handleCancel}
            className="quorum-btn-cancel hover-lift press-effect"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || selectedModels.length === 0}
            className="quorum-btn-save hover-lift press-effect"
          >
            <SettingsIcon className="w-4 h-4" />
            <span>Save Configuration</span>
          </button>
        </div>
      </motion.div>
    </div>
  );
};

