/**
 * UI slice - ephemeral UI state (not persisted).
 */
import { StateCreator } from 'zustand';
import { UISlice, RootStore } from '../types';
import { createLogger } from '@/services/logger';

const logger = createLogger({ component: 'UISlice' });

export const createUISlice: StateCreator<
  RootStore,
  [],
  [],
  UISlice
> = (set, get) => ({
  // State - ephemeral, not persisted
  showAgentPanel: true,
  isProcessing: false,
  error: null,
  inputValue: '',

  // Actions
  setShowAgentPanel: (show: boolean) =>
    set({ showAgentPanel: show }),

  setProcessing: (processing: boolean) => {
    const currentState = get().isProcessing;
    logger.info(`⚙️ setProcessing called: ${currentState} → ${processing}`, {
      from: currentState,
      to: processing,
      stackTrace: new Error().stack?.split('\n').slice(2, 5).join('\n'),
    });
    set({ isProcessing: processing });
  },

  setError: (error: string | null) =>
    set({ error }),

  setInputValue: (value: string) =>
    set({ inputValue: value }),

  clearError: () =>
    set({ error: null }),
});

