# Logging System Documentation

## Overview

This project uses a comprehensive, modular logging system built with TypeScript and designed for modern web applications. The system provides structured logging, multiple log levels, performance tracking, and production-ready features.

## Features

- ✨ **Multiple Log Levels**: DEBUG, INFO, WARN, ERROR
- 🎯 **Contextual Logging**: Attach metadata and context to all logs
- 📊 **Performance Tracking**: Built-in performance monitoring
- 🚀 **Multiple Transports**: Console, Remote, and custom transports
- 🎨 **Beautiful Console Output**: Styled and formatted console logs for development
- 📦 **Batching & Retry**: Efficient remote logging with automatic retry
- ⚡ **React Integration**: Custom hooks for component logging
- 🛡️ **Error Boundary**: Automatic error catching and logging
- 🔧 **Environment-Aware**: Different behavior for dev/prod

## Architecture

```
src/
├── types/
│   └── logger.ts              # TypeScript interfaces
├── services/
│   ├── logger.ts              # Main logger service
│   ├── logger.config.ts       # Configuration
│   └── transports/
│       ├── ConsoleTransport.ts  # Console output
│       └── RemoteTransport.ts   # Remote logging
├── hooks/
│   └── useLogger.ts           # React hooks
└── components/
    └── ErrorBoundary.tsx      # Error handling
```

## Quick Start

### Basic Usage

```typescript
import { logger } from '@/services/logger';

// Simple logging
logger.info('Application started');
logger.warn('Low memory warning');
logger.error('Failed to load data', error);
logger.debug('Debug information', { userId: 123 });
```

### React Component Usage

```typescript
import { useLogger } from '@/hooks/useLogger';

function MyComponent() {
  const logger = useLogger({ 
    component: 'MyComponent',
    trackMount: true // Automatically log mount/unmount
  });

  const handleClick = () => {
    logger.info('Button clicked', { buttonId: 'submit' });
  };

  return <button onClick={handleClick}>Click me</button>;
}
```

### Performance Tracking

```typescript
import { logger } from '@/services/logger';

// Manual tracking
logger.startPerformance('data-load');
await loadData();
logger.endPerformance('data-load');

// Automatic tracking with measure
const result = await logger.measure('api-call', async () => {
  return await fetch('/api/data');
});
```

### Child Loggers with Context

```typescript
import { createLogger } from '@/services/logger';

// Create a logger with specific context
const apiLogger = createLogger({ 
  component: 'APIService',
  service: 'backend' 
});

apiLogger.info('Request sent', { endpoint: '/users' });
// All logs from this logger will include the component and service context
```

## Configuration

### Environment Variables

Create a `.env` file with these optional variables:

```bash
# Log level (DEBUG, INFO, WARN, ERROR, NONE)
VITE_LOG_LEVEL=INFO

# Enable console logs in production
VITE_ENABLE_CONSOLE_LOGS=false

# Enable remote logging
VITE_ENABLE_REMOTE_LOGS=true

# Remote logging endpoint
VITE_LOG_ENDPOINT=/api/logs

# App version (included in all logs)
VITE_APP_VERSION=1.0.0
```

### Programmatic Configuration

```typescript
import { logger } from '@/services/logger';
import { LogLevel } from '@/types/logger';

// Update configuration at runtime
logger.configure({
  level: LogLevel.DEBUG,
  enableConsole: true,
  enableRemote: false,
});
```

## Log Levels

| Level | When to Use | Example |
|-------|------------|---------|
| `DEBUG` | Development debugging, verbose information | Variable values, flow control |
| `INFO` | General informational messages | User actions, state changes |
| `WARN` | Warning conditions, potential issues | Deprecated API usage, slow operations |
| `ERROR` | Error conditions, failures | API errors, exceptions |

## Contexts and Metadata

Every log can include contextual information:

```typescript
logger.info('User logged in', {
  userId: '123',
  email: 'user@example.com',
  loginMethod: 'oauth',
  timestamp: Date.now(),
});
```

### Default Context

The following context is automatically added to all logs:

- `environment` - dev/production
- `appVersion` - from VITE_APP_VERSION
- `platform` - OS platform
- `userAgent` - Browser user agent
- `sessionId` - Unique session ID

## Transports

### Console Transport

Outputs logs to browser console with:
- Colored output by log level
- Timestamp formatting
- Component names
- Expandable metadata
- Stack traces for errors

### Remote Transport

Sends logs to a backend endpoint with:
- **Batching**: Groups logs to reduce requests
- **Retry Logic**: Exponential backoff on failure
- **Flush on Exit**: Uses sendBeacon for page unload
- **Configurable**: Batch size and intervals

### Custom Transports

Create custom transports by implementing the `LogTransport` interface:

```typescript
import { LogTransport, LogEntry } from '@/types/logger';

class CustomTransport implements LogTransport {
  name = 'custom';

  log(entry: LogEntry): void {
    // Your custom logic
    console.log('Custom transport:', entry);
  }

  async flush(): Promise<void> {
    // Optional: flush pending logs
  }
}

// Add to logger
logger.configure({
  transports: [new CustomTransport()],
});
```

## React Hooks

### useLogger

Get a logger instance with automatic component context:

```typescript
const logger = useLogger({
  component: 'MyComponent',
  context: { userId: '123' },
  trackMount: true,
});
```

### useLogLifecycle

Automatically log mount/unmount:

```typescript
const logger = useLogLifecycle('MyComponent', { 
  view: 'dashboard' 
});
```

### useLogPerformance

Track effect performance:

```typescript
useLogPerformance(
  'data-fetch',
  () => {
    // Effect logic
    fetchData();
  },
  [dependencies],
  { endpoint: '/api/data' }
);
```

## Error Boundary

Wrap your app with `ErrorBoundary` to catch and log React errors:

```typescript
import { ErrorBoundary } from '@/components/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      <YourApp />
    </ErrorBoundary>
  );
}
```

Custom error handling:

```typescript
<ErrorBoundary
  onError={(error, errorInfo) => {
    // Custom error handling
    console.log('Custom handler:', error);
  }}
  fallback={<CustomErrorUI />}
>
  <YourApp />
</ErrorBoundary>
```

## Best Practices

### 1. Use Appropriate Log Levels

```typescript
// ✅ Good
logger.debug('Rendering component', { props });
logger.info('User action completed', { action: 'save' });
logger.warn('API response slow', { duration: '5s' });
logger.error('Failed to save', error, { userId });

// ❌ Bad
logger.info('x = 5'); // Too verbose for INFO
logger.error('User clicked button'); // Not an error
```

### 2. Add Meaningful Context

```typescript
// ✅ Good
logger.info('Form submitted', {
  formType: 'registration',
  fieldCount: 5,
  validationPassed: true,
});

// ❌ Bad
logger.info('Form submitted');
```

### 3. Use Child Loggers for Modules

```typescript
// ✅ Good - Each module has its own logger
const apiLogger = createLogger({ component: 'APIService' });
const authLogger = createLogger({ component: 'AuthService' });

// ❌ Bad - Using global logger everywhere
import { logger } from '@/services/logger';
```

### 4. Track Performance for Critical Operations

```typescript
// ✅ Good
const data = await logger.measure('critical-query', async () => {
  return await database.query();
});

// ✅ Also good
logger.startPerformance('render-list');
renderLargeList();
logger.endPerformance('render-list');
```

### 5. Handle Errors Properly

```typescript
// ✅ Good
try {
  await riskyOperation();
} catch (error) {
  logger.error('Operation failed', error as Error, {
    operation: 'riskyOperation',
    attemptCount: 3,
  });
  throw error; // Re-throw if needed
}

// ❌ Bad
try {
  await riskyOperation();
} catch (error) {
  console.log('Error:', error); // Don't use console.log
}
```

## Production Considerations

### Remote Logging Setup

To enable remote logging in production, set up a backend endpoint:

```typescript
// Backend endpoint (example with Express)
app.post('/api/logs', async (req, res) => {
  const { logs } = req.body;
  
  // Process logs (store in database, send to monitoring service, etc.)
  await saveLogsToDatabase(logs);
  
  res.status(200).json({ success: true });
});
```

### Log Levels in Production

- Set `VITE_LOG_LEVEL=ERROR` to only log errors
- Or `VITE_LOG_LEVEL=WARN` for warnings and errors
- Disable console logs with `VITE_ENABLE_CONSOLE_LOGS=false`

### Performance Impact

The logger is designed to be lightweight:
- Console logs are skipped when disabled
- Remote logs are batched to reduce requests
- Performance tracking has negligible overhead
- Log levels filter unnecessary operations

### Privacy & Security

⚠️ **Never log sensitive information**:

```typescript
// ❌ Never do this
logger.info('User login', { 
  password: password, // Never log passwords
  creditCard: cardNumber, // Never log PII
  apiKey: key, // Never log secrets
});

// ✅ Do this instead
logger.info('User login', { 
  userId: userId,
  method: 'oauth',
  success: true,
});
```

## Monitoring Integration

Integrate with monitoring services:

```typescript
import { LogTransport, LogEntry, LogLevel } from '@/types/logger';

class SentryTransport implements LogTransport {
  name = 'sentry';

  log(entry: LogEntry): void {
    if (entry.level >= LogLevel.ERROR) {
      Sentry.captureException(entry.metadata.error, {
        level: 'error',
        extra: entry.metadata,
      });
    }
  }
}

logger.configure({
  transports: [new SentryTransport()],
});
```

## Troubleshooting

### Logs not appearing?

1. Check log level configuration
2. Verify `enableConsole` is true
3. Check browser console filters

### Remote logs not sending?

1. Verify `VITE_ENABLE_REMOTE_LOGS=true`
2. Check `VITE_LOG_ENDPOINT` is correct
3. Verify backend endpoint is accessible
4. Check network tab for failed requests

### Performance impact?

1. Increase batch size for remote logs
2. Adjust flush interval
3. Disable debug logs in production
4. Use appropriate log levels

## Examples

See the following files for usage examples:

- `src/App.tsx` - Main app with logging
- `src/services/api.ts` - API service with performance tracking
- `src/components/ErrorBoundary.tsx` - Error handling

## Support

For issues or questions, please refer to the project documentation or contact the development team.

