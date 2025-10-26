import React from 'react'
import { Icons } from './icons'

interface ModernDashboardProps {
  data: any
}

export function ModernDashboard({ data }: ModernDashboardProps) {
  const report = data?.reports?.[0]
  
  if (!report) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <Icons.TrendingUp className="w-16 h-16 text-slate-400 mx-auto mb-4" />
        <p className="text-slate-600 dark:text-slate-400">No analysis data available</p>
      </div>
    </div>
    )
  }
  
  const fundamentals = report.fundamentals?.details
  const decision = report.decision
  
  return (
    <div className="space-y-6">
      {/* Header with Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Current Price"
          value={fundamentals?.basic_fundamentals?.current_price || '—'}
          trend={decision?.expected_return_pct || 0}
          icon={<Icons.DollarSign />}
          color="blue"
        />
        <MetricCard
          title="Price Target"
          value={decision?.price_target_12m || '—'}
          trend={decision?.expected_return_pct || 0}
          icon={<Icons.Target />}
          color="green"
        />
        <MetricCard
          title="Overall Score"
          value={decision?.score?.toFixed(1) || '—'}
          trend={0}
          icon={<Icons.TrendingUp />}
          color="purple"
        />
        <MetricCard
          title="Recommendation"
          value={decision?.action || '—'}
          trend={0}
          icon={<Icons.AlertCircle />}
          color="amber"
        />
      </div>
      
      {/* Key Insights Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InsightCard
          title="Financial Health"
          score={fundamentals?.deep_financial_analysis?.balance_sheet_strength?.overall_strength_score || 0}
          grade={fundamentals?.deep_financial_analysis?.balance_sheet_strength?.grade || 'N/A'}
          icon={<Icons.Activity />}
        />
        <InsightCard
          title="Growth Prospects"
          score={report.growth_prospects?.details?.growth_outlook?.overall_outlook || 'Moderate'}
          grade="B"
          icon={<Icons.TrendingUp />}
        />
      </div>
      
      {/* Valuation Metrics */}
      <div className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-slate-800 dark:to-slate-900 rounded-xl p-6 shadow-lg">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
          Valuation Summary
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricItem label="P/E Ratio" value={fundamentals?.basic_fundamentals?.pe_ratio?.toFixed(1) || '—'} />
          <MetricItem label="P/B Ratio" value={fundamentals?.basic_fundamentals?.pb_ratio?.toFixed(1) || '—'} />
          <MetricItem label="ROE" value={`${fundamentals?.basic_fundamentals?.roe || 0}%`} />
          <MetricItem label="Dividend Yield" value={`${(fundamentals?.basic_fundamentals?.dividend_yield || 0).toFixed(2)}%`} />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, value, trend, icon, color }: any) {
  const colorClasses = {
    blue: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400',
    green: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400',
    purple: 'bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400',
    amber: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400'
  }
  
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-md hover:shadow-lg transition-shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg ${colorClasses[color as keyof typeof colorClasses]}`}>
          {icon}
        </div>
        {trend !== 0 && (
          <span className={`text-sm font-medium ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
      <h4 className="text-sm text-slate-600 dark:text-slate-400 mb-1">{title}</h4>
      <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
    </div>
  )
}

function InsightCard({ title, score, grade, icon }: any) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-md hover:shadow-lg transition-shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
            {icon}
          </div>
          <h4 className="font-semibold text-slate-900 dark:text-slate-100">{title}</h4>
        </div>
        <span className="text-xs font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 px-2 py-1 rounded">
          {typeof score === 'number' ? `Score: ${score}` : grade}
        </span>
      </div>
      <div className="text-sm text-slate-600 dark:text-slate-400">
        {typeof score === 'number' ? (
          <div className="space-y-2">
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div 
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(score, 100)}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Grade: {grade}</p>
          </div>
        ) : (
          <p>{score}</p>
        )}
      </div>
    </div>
  )
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">{label}</p>
      <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{value}</p>
    </div>
  )
}

