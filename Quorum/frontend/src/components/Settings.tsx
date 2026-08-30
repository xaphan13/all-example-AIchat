/**
 * Settings component - comprehensive settings page for managing environment variables
 * and user preferences with local storage persistence.
 */
import { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  Save, 
  RotateCcw, 
  Eye, 
  EyeOff,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  Key,
  Server,
  Users,
  Palette,
  Terminal
} from 'lucide-react';
import { useStore } from '@/store';
import { useLogger } from '@/hooks';
import type { Settings as SettingsType } from '@/store/types';
import { settingsApi } from '@/services/settingsApi';

interface SettingsProps {
  onClose?: () => void;
}

export function Settings({ onClose }: SettingsProps) {
  const logger = useLogger({ component: 'Settings' });
  
  // Store state and actions
  const settings = useStore((state) => state.settings);
  const updateSettings = useStore((state) => state.updateSettings);
  const resetSettings = useStore((state) => state.resetSettings);
  const validateApiKey = useStore((state) => state.validateApiKey);
  
  // Local form state
  const [formData, setFormData] = useState<SettingsType>(settings);
  const [showApiKey, setShowApiKey] = useState(false);
  const [validationState, setValidationState] = useState({
    openrouter: null as boolean | null,
  });
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [hasChanges, setHasChanges] = useState(false);

  // Load settings from database on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        logger.info('Loading settings from database');
        const dbSettings = await settingsApi.getSettings(false); // Get full API keys
        updateSettings(dbSettings);
        setFormData(dbSettings);
        logger.info('Settings loaded from database');
      } catch (error) {
        logger.error('Failed to load settings from database, using local storage', error as Error);
        setFormData(settings);
      }
    };
    
    loadSettings();
  }, []); // Only run on mount
  
  // Sync form data when store settings change
  useEffect(() => {
    setFormData(settings);
  }, [settings]);

  // Check for changes
  useEffect(() => {
    const changed = JSON.stringify(formData) !== JSON.stringify(settings);
    setHasChanges(changed);
  }, [formData, settings]);

  // Validate API keys on change
  useEffect(() => {
    setValidationState({
      openrouter: formData.openrouterApiKey ? validateApiKey('openrouter', formData.openrouterApiKey) : null,
    });
  }, [formData.openrouterApiKey, validateApiKey]);

  const handleInputChange = (field: keyof SettingsType, value: string | number | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      logger.info('Saving settings to database', { hasChanges });
      setSaveStatus('saving');
      
      // Save to database
      const updatedSettings = await settingsApi.updateSettings(formData);
      
      // Update local store
      updateSettings(updatedSettings);
      
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
      
      logger.info('Settings saved to database successfully');
    } catch (error) {
      logger.error('Failed to save settings to database', error as Error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleReset = () => {
    if (confirm('Are you sure you want to reset all settings to defaults? This cannot be undone.')) {
      logger.info('Resetting settings to defaults');
      resetSettings();
      setSaveStatus('idle');
    }
  };

  const handleCancel = () => {
    if (hasChanges) {
      if (confirm('You have unsaved changes. Are you sure you want to cancel?')) {
        setFormData(settings);
        onClose?.();
      }
    } else {
      onClose?.();
    }
  };

  const getValidationIcon = (state: boolean | null) => {
    if (state === null) return null;
    if (state) return <CheckCircle className="w-4 h-4 text-green-500" />;
    return <XCircle className="w-4 h-4 text-red-500" />;
  };

  return (
    <div className="settings-overlay animate-fade-in" onClick={handleCancel}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header with Close Button */}
        <div className="settings-header">
          <div className="settings-header-content">
            <div className="settings-icon-wrapper">
              <SettingsIcon className="settings-icon" />
            </div>
            <div>
              <h2 className="settings-title">Settings</h2>
              <p className="settings-subtitle">
                Configure your environment variables and preferences
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="settings-close-button hover-scale press-effect transition-colors-smooth"
            title="Close settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Area */}
        <div className="settings-content">
          {/* Warning Banner - Show at Top for Visibility */}
          {validationState.openrouter === false ? (
            <div className="settings-warning-banner">
              <AlertTriangle className="settings-warning-icon" />
              <div className="settings-warning-text">
                <strong className="font-semibold">Invalid API Key Format</strong>
                <p className="mt-0.5">The OpenRouter API key appears to be invalid. Please check the format and try again.</p>
              </div>
            </div>
          ) : null}

          {/* API Keys Section - Highest Priority */}
          <section className="settings-section settings-section-primary">
            <div className="settings-section-header">
              <div className="settings-section-icon-wrapper settings-section-icon-primary">
                <Key className="settings-section-icon" />
              </div>
              <div>
                <h3 className="settings-section-title">API Keys</h3>
                <p className="settings-section-description">Required for AI model access</p>
              </div>
            </div>
            
            <div className="settings-section-content">
              {/* OpenRouter API Key */}
              <div className="settings-field">
                <label className="settings-label settings-label-required">
                  OpenRouter API Key
                  <span className="settings-required-badge">Required</span>
                </label>
                <div className="settings-input-wrapper">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={formData.openrouterApiKey}
                    onChange={(e) => handleInputChange('openrouterApiKey', e.target.value)}
                    placeholder="sk-or-xxxxx"
                    className="settings-input"
                  />
                  <div className="settings-input-actions">
                    {getValidationIcon(validationState.openrouter)}
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="settings-input-button"
                    >
                      {showApiKey ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                <p className="settings-help-text">
                  API key for all AI models (Claude, GPT, Gemini). Get your key from{' '}
                  <a 
                    href="https://openrouter.ai/keys" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="settings-link"
                  >
                    openrouter.ai/keys
                  </a>
                </p>
              </div>
            </div>
          </section>

          {/* Two Column Grid for Secondary Sections */}
          <div className="settings-grid">
            {/* Server Configuration */}
            <section className="settings-section">
              <div className="settings-section-header">
                <div className="settings-section-icon-wrapper">
                  <Server className="settings-section-icon" />
                </div>
                <div>
                  <h3 className="settings-section-title">Server</h3>
                  <p className="settings-section-description">Backend connection</p>
                </div>
              </div>
              
              <div className="settings-section-content">
                <div className="settings-field">
                  <label className="settings-label">
                    Backend URL
                  </label>
                  <input
                    type="text"
                    value={formData.backendUrl}
                    onChange={(e) => handleInputChange('backendUrl', e.target.value)}
                    placeholder="http://localhost:8000"
                    className="settings-input"
                  />
                  <p className="settings-help-text">
                    URL of the Quorum backend server
                  </p>
                </div>
              </div>
            </section>

            {/* Agent Configuration */}
            <section className="settings-section">
              <div className="settings-section-header">
                <div className="settings-section-icon-wrapper">
                  <Users className="settings-section-icon" />
                </div>
                <div>
                  <h3 className="settings-section-title">Agents</h3>
                  <p className="settings-section-description">Agent behavior</p>
                </div>
              </div>
              
              <div className="settings-section-content">
                <div className="settings-field">
                  <label className="settings-label">
                    Max Concurrent Agents
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={formData.maxConcurrentAgents}
                    onChange={(e) => handleInputChange('maxConcurrentAgents', parseInt(e.target.value))}
                    className="settings-input"
                  />
                  <p className="settings-help-text">
                    Maximum number of agents that can run simultaneously
                  </p>
                </div>

                <div className="settings-field">
                  <label className="settings-label">
                    Agent Timeout (seconds)
                  </label>
                  <input
                    type="number"
                    min="30"
                    max="600"
                    value={formData.agentTimeout}
                    onChange={(e) => handleInputChange('agentTimeout', parseInt(e.target.value))}
                    className="settings-input"
                  />
                  <p className="settings-help-text">
                    Maximum time an agent can run before timing out
                  </p>
                </div>
              </div>
            </section>

            {/* UI Preferences */}
            <section className="settings-section">
              <div className="settings-section-header">
                <div className="settings-section-icon-wrapper">
                  <Palette className="settings-section-icon" />
                </div>
                <div>
                  <h3 className="settings-section-title">Interface</h3>
                  <p className="settings-section-description">UI preferences</p>
                </div>
              </div>
              
              <div className="settings-section-content">
                <div className="settings-field">
                  <label className="settings-label">
                    Theme
                  </label>
                  <select
                    value={formData.theme}
                    onChange={(e) => handleInputChange('theme', e.target.value as 'light' | 'dark' | 'system')}
                    className="settings-input"
                  >
                    <option value="system">System</option>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </select>
                </div>

                <div className="settings-toggle-field">
                  <div className="settings-toggle-content">
                    <label className="settings-label settings-label-inline">
                      Enable Notifications
                    </label>
                    <p className="settings-help-text">
                      Show browser notifications for agent updates
                    </p>
                  </div>
                  <label className="settings-toggle">
                    <input
                      type="checkbox"
                      checked={formData.enableNotifications}
                      onChange={(e) => handleInputChange('enableNotifications', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="settings-toggle-switch"></div>
                  </label>
                </div>

                <div className="settings-toggle-field">
                  <div className="settings-toggle-content">
                    <label className="settings-label settings-label-inline">
                      Auto Show Agent Panel
                    </label>
                    <p className="settings-help-text">
                      Automatically display agent panel when agents are active
                    </p>
                  </div>
                  <label className="settings-toggle">
                    <input
                      type="checkbox"
                      checked={formData.autoShowAgentPanel}
                      onChange={(e) => handleInputChange('autoShowAgentPanel', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="settings-toggle-switch"></div>
                  </label>
                </div>
              </div>
            </section>

            {/* Logging Configuration */}
            <section className="settings-section">
              <div className="settings-section-header">
                <div className="settings-section-icon-wrapper">
                  <Terminal className="settings-section-icon" />
                </div>
                <div>
                  <h3 className="settings-section-title">Logging</h3>
                  <p className="settings-section-description">Debug settings</p>
                </div>
              </div>
              
              <div className="settings-section-content">
                <div className="settings-field">
                  <label className="settings-label">
                    Log Level
                  </label>
                  <select
                    value={formData.logLevel}
                    onChange={(e) => handleInputChange('logLevel', e.target.value as 'debug' | 'info' | 'warn' | 'error')}
                    className="settings-input"
                  >
                    <option value="debug">Debug</option>
                    <option value="info">Info</option>
                    <option value="warn">Warning</option>
                    <option value="error">Error</option>
                  </select>
                  <p className="settings-help-text">
                    Minimum log level to display in the browser console
                  </p>
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* Sticky Footer with Actions */}
        <div className="settings-footer">
          <button
            onClick={handleReset}
            className="settings-reset-button hover-lift press-effect transition-colors-smooth"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Reset to Defaults</span>
          </button>

          <div className="settings-action-buttons">
            <button
              onClick={handleCancel}
              className="settings-cancel-button hover-lift press-effect transition-colors-smooth"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges || saveStatus === 'saving'}
              className="settings-save-button hover-lift press-effect transition-colors-smooth"
            >
              {saveStatus === 'saving' ? (
                <>
                  <div className="settings-spinner" />
                  <span>Saving...</span>
                </>
              ) : saveStatus === 'saved' ? (
                <>
                  <CheckCircle className="w-5 h-5 animate-scale-in" />
                  <span>Saved!</span>
                </>
              ) : saveStatus === 'error' ? (
                <>
                  <XCircle className="w-5 h-5 animate-shake" />
                  <span>Error</span>
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  <span>Save Settings</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

