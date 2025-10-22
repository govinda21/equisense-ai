import React, { useState, useEffect, useRef } from 'react';

interface ChartData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TechnicalIndicator {
  name: string;
  data: number[];
  color: string;
  type: 'line' | 'histogram' | 'overlay';
}

interface AdvancedChartProps {
  ticker: string;
  data: ChartData[];
  indicators?: TechnicalIndicator[];
  timeframe: '1D' | '1W' | '1M' | '3M' | '6M' | '1Y';
  onTimeframeChange?: (timeframe: string) => void;
  onIndicatorAdd?: (indicator: string) => void;
  onIndicatorRemove?: (indicator: string) => void;
}

export const AdvancedChart: React.FC<AdvancedChartProps> = ({
  ticker,
  data,
  indicators = [],
  timeframe,
  onTimeframeChange,
  onIndicatorAdd,
  onIndicatorRemove
}) => {
  const [selectedIndicator, setSelectedIndicator] = useState<string>('');
  const [chartType, setChartType] = useState<'candlestick' | 'line' | 'volume'>('candlestick');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  const timeframes = [
    { label: '1D', value: '1D' },
    { label: '1W', value: '1W' },
    { label: '1M', value: '1M' },
    { label: '3M', value: '3M' },
    { label: '6M', value: '6M' },
    { label: '1Y', value: '1Y' }
  ];

  const availableIndicators = [
    { name: 'SMA 20', value: 'sma_20', color: '#3B82F6' },
    { name: 'SMA 50', value: 'sma_50', color: '#EF4444' },
    { name: 'EMA 12', value: 'ema_12', color: '#10B981' },
    { name: 'EMA 26', value: 'ema_26', color: '#F59E0B' },
    { name: 'RSI', value: 'rsi', color: '#8B5CF6' },
    { name: 'MACD', value: 'macd', color: '#06B6D4' },
    { name: 'Bollinger Bands', value: 'bollinger', color: '#84CC16' },
    { name: 'Volume', value: 'volume', color: '#6B7280' }
  ];

  const handleIndicatorAdd = () => {
    if (selectedIndicator && onIndicatorAdd) {
      onIndicatorAdd(selectedIndicator);
      setSelectedIndicator('');
    }
  };

  const handleIndicatorRemove = (indicator: string) => {
    if (onIndicatorRemove) {
      onIndicatorRemove(indicator);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      chartRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  return (
    <div 
      ref={chartRef}
      className={`bg-white rounded-lg shadow-lg p-4 ${
        isFullscreen ? 'fixed inset-0 z-50' : ''
      }`}
    >
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <h3 className="text-lg font-semibold text-gray-900">{ticker}</h3>
          <div className="flex space-x-2">
            {timeframes.map((tf) => (
              <button
                key={tf.value}
                onClick={() => onTimeframeChange?.(tf.value)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  timeframe === tf.value
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <select
            value={chartType}
            onChange={(e) => setChartType(e.target.value as any)}
            className="px-3 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="candlestick">Candlestick</option>
            <option value="line">Line</option>
            <option value="volume">Volume</option>
          </select>
          
          <button
            onClick={toggleFullscreen}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
            title="Toggle Fullscreen"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Chart Content */}
      <div className="h-96 mb-4">
        {chartType === 'candlestick' && (
          <Candlestick data={data} indicators={indicators} />
        )}
        {chartType === 'line' && (
          <Line data={data} indicators={indicators} />
        )}
        {chartType === 'volume' && (
          <Volume data={data} />
        )}
      </div>

      {/* Technical Indicators Panel */}
      <div className="border-t pt-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-gray-700">Technical Indicators</h4>
          <div className="flex items-center space-x-2">
            <select
              value={selectedIndicator}
              onChange={(e) => setSelectedIndicator(e.target.value)}
              className="px-2 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Add Indicator</option>
              {availableIndicators.map((indicator) => (
                <option key={indicator.value} value={indicator.value}>
                  {indicator.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleIndicatorAdd}
              disabled={!selectedIndicator}
              className="px-2 py-1 text-xs bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Add
            </button>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-2">
          {indicators.map((indicator, index) => (
            <div
              key={index}
              className="flex items-center space-x-1 px-2 py-1 bg-gray-100 rounded-md text-xs"
            >
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: indicator.color }}
              />
              <span className="text-gray-700">{indicator.name}</span>
              <button
                onClick={() => handleIndicatorRemove(indicator.name)}
                className="text-gray-500 hover:text-red-500 transition-colors"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chart Controls */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center space-x-4">
          <span>Zoom: Mouse wheel</span>
          <span>Pan: Click & drag</span>
          <span>Crosshair: Hover</span>
        </div>
        <div className="flex items-center space-x-2">
          <button className="hover:text-gray-700 transition-colors">Reset Zoom</button>
          <button className="hover:text-gray-700 transition-colors">Save Chart</button>
        </div>
      </div>
    </div>
  );
};

// Chart Components
export const Candlestick: React.FC<{ data: ChartData[]; indicators: TechnicalIndicator[] }> = ({
  data,
  indicators
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw candlesticks
    drawCandlesticks(ctx, data, canvas.width, canvas.height);

    // Draw indicators
    indicators.forEach(indicator => {
      drawIndicator(ctx, indicator, data, canvas.width, canvas.height);
    });

  }, [data, indicators]);

  const drawCandlesticks = (ctx: CanvasRenderingContext2D, data: ChartData[], width: number, height: number) => {
    const candleWidth = width / data.length * 0.8;
    const candleSpacing = width / data.length * 0.2;

    data.forEach((candle, index) => {
      const x = index * (candleWidth + candleSpacing) + candleSpacing / 2;
      const isGreen = candle.close >= candle.open;
      
      // Draw wick
      ctx.strokeStyle = isGreen ? '#10B981' : '#EF4444';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + candleWidth / 2, candle.low * height / 1000);
      ctx.lineTo(x + candleWidth / 2, candle.high * height / 1000);
      ctx.stroke();

      // Draw body
      ctx.fillStyle = isGreen ? '#10B981' : '#EF4444';
      ctx.fillRect(
        x,
        Math.min(candle.open, candle.close) * height / 1000,
        candleWidth,
        Math.abs(candle.close - candle.open) * height / 1000
      );
    });
  };

  const drawIndicator = (ctx: CanvasRenderingContext2D, indicator: TechnicalIndicator, data: ChartData[], width: number, height: number) => {
    ctx.strokeStyle = indicator.color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    indicator.data.forEach((value, index) => {
      const x = index * (width / data.length);
      const y = height - (value * height / 1000);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();
  };

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full border border-gray-200 rounded"
      style={{ background: '#fafafa' }}
    />
  );
};

export const Line: React.FC<{ data: ChartData[]; indicators: TechnicalIndicator[] }> = ({
  data,
  indicators
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw main line
    drawLine(ctx, data, canvas.width, canvas.height, '#3B82F6', 2);

    // Draw indicators
    indicators.forEach(indicator => {
      drawLine(ctx, data, canvas.width, canvas.height, indicator.color, 1);
    });

  }, [data, indicators]);

  const drawLine = (ctx: CanvasRenderingContext2D, data: ChartData[], width: number, height: number, color: string, lineWidth: number) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();

    data.forEach((point, index) => {
      const x = index * (width / data.length);
      const y = height - (point.close * height / 1000);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();
  };

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full border border-gray-200 rounded"
      style={{ background: '#fafafa' }}
    />
  );
};

export const Volume: React.FC<{ data: ChartData[] }> = ({ data }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw volume bars
    const maxVolume = Math.max(...data.map(d => d.volume));
    const barWidth = canvas.width / data.length * 0.8;
    const barSpacing = canvas.width / data.length * 0.2;

    data.forEach((point, index) => {
      const x = index * (barWidth + barSpacing) + barSpacing / 2;
      const barHeight = (point.volume / maxVolume) * canvas.height;
      const isGreen = point.close >= point.open;
      
      ctx.fillStyle = isGreen ? '#10B981' : '#EF4444';
      ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
    });

  }, [data]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full border border-gray-200 rounded"
      style={{ background: '#fafafa' }}
    />
  );
};

export const TechnicalIndicators: React.FC<{ indicators: TechnicalIndicator[] }> = ({ indicators }) => {
  return (
    <div className="space-y-2">
      {indicators.map((indicator, index) => (
        <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
          <div className="flex items-center space-x-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: indicator.color }}
            />
            <span className="text-sm font-medium">{indicator.name}</span>
          </div>
          <div className="text-sm text-gray-600">
            {indicator.data[indicator.data.length - 1]?.toFixed(2) || 'N/A'}
          </div>
        </div>
      ))}
    </div>
  );
};
