/**
 * Error Boundary Component
 * Catches React errors and logs them using the logger service
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { logger } from '@/services/logger';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log the error
    logger.error(
      'React Error Boundary caught an error',
      error,
      {
        component: 'ErrorBoundary',
        componentStack: errorInfo.componentStack,
        errorBoundary: true,
      }
    );

    this.setState({
      errorInfo,
    });

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);
  }

  handleReset = (): void => {
    logger.info('Error boundary reset', { component: 'ErrorBoundary' });
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-dark-50 p-6">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 border border-dark-200">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-red-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-dark-900 mb-1">
                  Something went wrong
                </h2>
                <p className="text-sm text-dark-600">
                  An unexpected error occurred. Please try refreshing the page.
                </p>
              </div>
            </div>

            {this.state.error && (
              <div className="mb-4 p-3 bg-dark-50 rounded border border-dark-200">
                <p className="text-xs font-mono text-red-600 mb-1">
                  {this.state.error.name}
                </p>
                <p className="text-xs font-mono text-dark-700">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={this.handleReset}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-dark-900 text-white rounded-lg hover:bg-dark-800 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 border border-dark-300 text-dark-700 rounded-lg hover:bg-dark-50 transition-colors"
              >
                Reload Page
              </button>
            </div>

            {import.meta.env.MODE === 'development' && this.state.errorInfo && (
              <details className="mt-4">
                <summary className="text-xs text-dark-500 cursor-pointer hover:text-dark-700">
                  Component Stack
                </summary>
                <pre className="mt-2 p-2 bg-dark-50 rounded text-xs overflow-auto max-h-40 border border-dark-200">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

