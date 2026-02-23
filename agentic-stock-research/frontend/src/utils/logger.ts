/**
 * Frontend logging utility
 * Logs to browser console and optionally to backend API endpoint
 */

export const LogLevel = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARN: 'WARN',
  ERROR: 'ERROR'
} as const

export type LogLevel = typeof LogLevel[keyof typeof LogLevel]

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
  component?: string;
}

class Logger {
  private component?: string;

  constructor(component?: string) {
    this.component = component;
  }

  private formatMessage(level: LogLevel, message: string, data?: any): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      data,
      component: this.component
    };
  }

  private log(level: LogLevel, message: string, data?: any): void {
    const entry = this.formatMessage(level, message, data);
    
    // Always log to console
    const consoleMethod = level === LogLevel.ERROR ? 'error' :
                         level === LogLevel.WARN ? 'warn' :
                         level === LogLevel.DEBUG ? 'debug' : 'log';
    
    if (data) {
      console[consoleMethod](`[${level}] ${message}`, data);
    } else {
      console[consoleMethod](`[${level}] ${message}`);
    }

    // In production, send to backend logging endpoint
    if (process.env.NODE_ENV === 'production' && typeof window !== 'undefined') {
      this.sendToBackend(entry).catch(err => {
        // Silently fail - don't block app execution
        console.debug('Failed to send log to backend:', err);
      });
    }
  }

  private async sendToBackend(entry: LogEntry): Promise<void> {
    try {
      // Only log errors and warnings to backend to reduce noise
      if (entry.level === LogLevel.ERROR || entry.level === LogLevel.WARN) {
        await fetch('/api/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(entry),
          // Don't wait for response - fire and forget
        }).catch(() => {
          // Ignore network errors
        });
      }
    } catch (err) {
      // Silently fail
    }
  }

  debug(message: string, data?: any): void {
    this.log(LogLevel.DEBUG, message, data);
  }

  info(message: string, data?: any): void {
    this.log(LogLevel.INFO, message, data);
  }

  warn(message: string, data?: any): void {
    this.log(LogLevel.WARN, message, data);
  }

  error(message: string, data?: any): void {
    this.log(LogLevel.ERROR, message, data);
  }
}

export function createLogger(component?: string): Logger {
  return new Logger(component);
}

// Default logger
export const logger = createLogger();

