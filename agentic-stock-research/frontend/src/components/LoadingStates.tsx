import React from 'react';

// Skeleton Loading Components
export const SkeletonCard: React.FC<{ className?: string }> = ({ className = "" }) => (
  <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`}>
    <div className="p-4 space-y-3">
      <div className="h-4 bg-gray-300 rounded w-3/4"></div>
      <div className="h-6 bg-gray-300 rounded w-1/2"></div>
      <div className="h-3 bg-gray-300 rounded w-full"></div>
    </div>
  </div>
);

export const SkeletonGrid: React.FC<{ cards?: number }> = ({ cards = 6 }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {Array.from({ length: cards }, (_, i) => (
      <SkeletonCard key={i} className="h-32" />
    ))}
  </div>
);

export const SkeletonTable: React.FC<{ rows?: number; cols?: number }> = ({ 
  rows = 5, 
  cols = 4 
}) => (
  <div className="animate-pulse">
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-100 px-4 py-3 border-b border-gray-200">
        <div className="flex space-x-4">
          {Array.from({ length: cols }, (_, i) => (
            <div key={i} className="h-4 bg-gray-300 rounded flex-1"></div>
          ))}
        </div>
      </div>
      
      {/* Rows */}
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div key={rowIndex} className="px-4 py-3 border-b border-gray-100 last:border-b-0">
          <div className="flex space-x-4">
            {Array.from({ length: cols }, (_, colIndex) => (
              <div key={colIndex} className="h-3 bg-gray-200 rounded flex-1"></div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
);

export const SkeletonChart: React.FC<{ className?: string }> = ({ className = "h-64" }) => (
  <div className={`animate-pulse bg-gray-100 rounded-lg border ${className}`}>
    <div className="p-4 h-full flex flex-col">
      {/* Chart title */}
      <div className="h-4 bg-gray-300 rounded w-1/3 mb-4"></div>
      
      {/* Chart area */}
      <div className="flex-1 flex items-end space-x-1">
        {Array.from({ length: 20 }, (_, i) => (
          <div
            key={i}
            className="bg-gray-300 rounded-t flex-1"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          ></div>
        ))}
      </div>
      
      {/* X-axis labels */}
      <div className="flex justify-between mt-2">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="h-2 bg-gray-300 rounded w-8"></div>
        ))}
      </div>
    </div>
  </div>
);

// Spinner Components
export const Spinner: React.FC<{ size?: 'sm' | 'md' | 'lg'; className?: string }> = ({ 
  size = 'md', 
  className = "" 
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6', 
    lg: 'h-8 w-8'
  };

  return (
    <div className={`${sizeClasses[size]} ${className}`}>
      <div className="animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 h-full w-full"></div>
    </div>
  );
};

export const LoadingOverlay: React.FC<{ 
  isLoading: boolean;
  message?: string;
  children: React.ReactNode;
}> = ({ isLoading, message = "Loading...", children }) => (
  <div className="relative">
    {children}
    {isLoading && (
      <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10 rounded-lg">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-2" />
          <p className="text-gray-600 font-medium">{message}</p>
        </div>
      </div>
    )}
  </div>
);

// Progress Indicators
export const ProgressBar: React.FC<{ 
  progress: number; // 0-100
  className?: string;
  showPercentage?: boolean;
}> = ({ progress, className = "", showPercentage = true }) => (
  <div className={`w-full ${className}`}>
    <div className="flex justify-between text-sm text-gray-600 mb-1">
      <span>Progress</span>
      {showPercentage && <span>{Math.round(progress)}%</span>}
    </div>
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div
        className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      ></div>
    </div>
  </div>
);

export const LoadingDots: React.FC<{ className?: string }> = ({ className = "" }) => (
  <div className={`flex space-x-1 ${className}`}>
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
        style={{ animationDelay: `${i * 0.1}s` }}
      ></div>
    ))}
  </div>
);

// Analysis specific loading states
export const AnalysisLoadingCard: React.FC<{ title: string; progress?: number }> = ({ 
  title, 
  progress 
}) => (
  <div className="bg-white rounded-lg border p-4">
    <div className="flex items-center justify-between mb-3">
      <h3 className="font-medium text-gray-800">{title}</h3>
      <Spinner size="sm" />
    </div>
    
    {progress !== undefined ? (
      <ProgressBar progress={progress} showPercentage={false} className="mb-2" />
    ) : (
      <div className="space-y-2">
        <div className="h-3 bg-gray-200 rounded animate-pulse"></div>
        <div className="h-3 bg-gray-200 rounded animate-pulse w-3/4"></div>
      </div>
    )}
    
    <p className="text-sm text-gray-500 mt-2">
      {progress !== undefined ? `${Math.round(progress)}% complete` : 'Processing...'}
    </p>
  </div>
);
