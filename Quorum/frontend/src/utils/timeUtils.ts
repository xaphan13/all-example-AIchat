/**
 * Time Utilities
 * Native time formatting utilities to replace date-fns
 */

/**
 * Format a date as relative time (e.g., "2 minutes ago", "just now")
 * Uses native Intl.RelativeTimeFormat for zero dependencies
 */
export function formatTimeAgo(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const seconds = Math.floor((Date.now() - dateObj.getTime()) / 1000);
  
  // Handle invalid dates
  if (isNaN(seconds)) {
    return 'Invalid date';
  }
  
  // Just now (< 10 seconds)
  if (seconds < 10) {
    return 'just now';
  }
  
  // Define time intervals in seconds
  const intervals: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
    ['second', 1],
  ];
  
  // Find the appropriate interval
  for (const [unit, secondsInUnit] of intervals) {
    const interval = Math.floor(seconds / secondsInUnit);
    if (interval >= 1) {
      const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
      return rtf.format(-interval, unit);
    }
  }
  
  return 'just now';
}

/**
 * Format a date as absolute time (e.g., "Jan 15, 2024 at 3:45 PM")
 */
export function formatAbsoluteTime(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  return new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(dateObj);
}

/**
 * Format duration in milliseconds to human readable string
 */
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  if (seconds > 0) {
    return `${seconds}s`;
  }
  return `${ms}ms`;
}

