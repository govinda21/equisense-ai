import React from 'react';
import { ExclamationTriangleIcon, XCircleIcon, WifiIcon, ServerIcon, ClockIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

export interface ErrorStateProps {
  title?: string; message?: string; type?: 'network' | 'server' | 'timeout' | 'validation' | 'generic';
  onRetry?: () => void; retryLabel?: string; className?: string;
}

const ERROR_CONFIGS = {
  network: {
    icon: WifiIcon, iconColor: 'text-orange-500', bgColor: 'bg-orange-50', borderColor: 'border-orange-200',
    defaultTitle: 'Connection Problem', defaultMessage: 'Please check your internet connection and try again.',
    troubleshooting: ['Check if the backend server is running on port 8000','Verify your internet connection','Try refreshing the page','Check if port 8000 is blocked by firewall']
  },
  server: {
    icon: ServerIcon, iconColor: 'text-red-500', bgColor: 'bg-red-50', borderColor: 'border-red-200',
    defaultTitle: 'Server Error', defaultMessage: 'The server is temporarily unavailable. Please try again later.',
    troubleshooting: ['The backend service may have crashed','Check server logs for detailed error information','Try restarting the backend service','Contact system administrator if problem persists']
  },
  timeout: {
    icon: ClockIcon, iconColor: 'text-yellow-500', bgColor: 'bg-yellow-50', borderColor: 'border-yellow-200',
    defaultTitle: 'Request Timeout', defaultMessage: 'The request took too long to complete. Please try again.',
    troubleshooting: ['Try analyzing fewer tickers at once','Check if the server is overloaded','Verify your internet connection speed','Try again during off-peak hours']
  },
  validation: {
    icon: ExclamationTriangleIcon, iconColor: 'text-amber-500', bgColor: 'bg-amber-50', borderColor: 'border-amber-200',
    defaultTitle: 'Invalid Input', defaultMessage: 'Please check your input and try again.',
    troubleshooting: ['Check ticker symbols are correct','Ensure maximum 5 tickers per request','Verify country selection matches tickers','Use valid date ranges for analysis']
  },
  generic: {
    icon: XCircleIcon, iconColor: 'text-gray-500', bgColor: 'bg-gray-50', borderColor: 'border-gray-200',
    defaultTitle: 'Something went wrong', defaultMessage: 'An unexpected error occurred. Please try again.',
    troubleshooting: ['Try refreshing the page','Clear browser cache and cookies','Check browser console for errors','Contact support if problem persists']
  }
} as const;

export const ErrorState: React.FC<ErrorStateProps> = ({ title, message, type = 'generic', onRetry, retryLabel = 'Try Again', className = '' }) => {
  const config = ERROR_CONFIGS[type];
  const Icon = config.icon;
  return (
    <div className={`min-h-[200px] flex items-center justify-center ${config.bgColor} ${config.borderColor} border rounded-lg p-6 ${className}`}>
      <div className="text-center max-w-md">
        <Icon className={`h-12 w-12 ${config.iconColor} mx-auto mb-4`} />
        <h3 className="text-lg font-semibold text-gray-800 mb-2">{title || config.defaultTitle}</h3>
        <p className="text-gray-600 mb-4 text-sm leading-relaxed">{message || config.defaultMessage}</p>
        {onRetry && (
          <button onClick={onRetry} className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
            <ArrowPathIcon className="h-4 w-4 mr-2" />{retryLabel}
          </button>
        )}
        <details className="mt-4 text-left">
          <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-800">Troubleshooting Steps</summary>
          <ul className="mt-2 text-xs text-gray-600 space-y-1">
            {config.troubleshooting.map((step, i) => (
              <li key={i} className="flex items-start">
                <span className="inline-block w-4 text-center text-gray-400 text-xs leading-4 mr-2">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </div>
  );
};

export const NetworkError: React.FC<Omit<ErrorStateProps, 'type'>> = (props) => <ErrorState {...props} type="network" />;
export const ServerError: React.FC<Omit<ErrorStateProps, 'type'>> = (props) => <ErrorState {...props} type="server" />;
export const TimeoutError: React.FC<Omit<ErrorStateProps, 'type'>> = (props) => <ErrorState {...props} type="timeout" />;
export const ValidationError: React.FC<Omit<ErrorStateProps, 'type'>> = (props) => <ErrorState {...props} type="validation" />;

export const InlineError: React.FC<{ message: string; className?: string }> = ({ message, className = '' }) => (
  <div className={`flex items-center text-red-600 text-sm mt-1 ${className}`}>
    <ExclamationTriangleIcon className="h-4 w-4 mr-1 flex-shrink-0" /><span>{message}</span>
  </div>
);

export const ErrorAlert: React.FC<{ title?: string; message: string; onDismiss?: () => void; className?: string }> = ({ title, message, onDismiss, className = '' }) => (
  <div className={`bg-red-50 border border-red-200 rounded-md p-4 ${className}`}>
    <div className="flex">
      <XCircleIcon className="h-5 w-5 text-red-400 flex-shrink-0" />
      <div className="ml-3 flex-1">
        {title && <h3 className="text-sm font-medium text-red-800 mb-1">{title}</h3>}
        <p className="text-sm text-red-700">{message}</p>
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss}
          className="ml-auto pl-3 inline-flex bg-red-50 rounded-md p-1.5 text-red-500 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-red-50 focus:ring-red-600">
          <span className="sr-only">Dismiss</span><XCircleIcon className="h-4 w-4" />
        </button>
      )}
    </div>
  </div>
);

export const EmptyState: React.FC<{
  title: string; message: string; actionLabel?: string; onAction?: () => void;
  icon?: React.ComponentType<{ className?: string }>; className?: string
}> = ({ title, message, actionLabel, onAction, icon: Icon, className = '' }) => (
  <div className={`text-center py-12 ${className}`}>
    {Icon && <Icon className="h-12 w-12 text-gray-400 mx-auto mb-4" />}
    <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
    <p className="text-gray-500 mb-6 max-w-sm mx-auto">{message}</p>
    {actionLabel && onAction && (
      <button onClick={onAction} className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
        {actionLabel}
      </button>
    )}
  </div>
);
