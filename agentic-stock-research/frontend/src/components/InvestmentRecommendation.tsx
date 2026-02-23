import { useState } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, TrendingUp, TrendingDown, Target, DollarSign, FileText, CheckCircle, Loader2, BarChart3, TrendingUp as TrendingUpIcon } from 'lucide-react'
import { Icons } from './icons'
import { ProfessionalHeader } from './ProfessionalHeader'
import { MetricCard } from './MetricCard'
import { CollapsibleSection } from './CollapsibleSection'
import { ExecutiveSummarySections } from './ExecutiveSummarySections'
import { ValuationVisualization } from './ValuationVisualization'
import { ScenarioVisualization } from './ScenarioVisualization'
import { ActionableWarningBox } from './ActionableWarningBox'

interface InvestmentRecommendationProps {
  report: any
  ticker?: string
}

function currencySymbolForTicker(ticker?: string): string {
  if (!ticker) return '$'
  const t = ticker.toUpperCase()
  return (t.endsWith('.NS') || t.endsWith('.BO')) ? '₹' : '$'
}

function formatAmountByCurrency(value?: number, ticker?: string): string {
  if (value === undefined || value === null || isNaN(Number(value)) || value === 0) return '—'
  const symbol = currencySymbolForTicker(ticker)
  const v = Number(value)
  const abs = Math.abs(v)
  if (symbol === '₹') {
    if (abs >= 1e7) return `₹${(v / 1e7).toFixed(1)} Cr`
    if (abs >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`
    return `₹${v.toLocaleString()}`
  }
  if (abs >= 1e12) return `${symbol}${(v / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${symbol}${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${symbol}${(v / 1e6).toFixed(1)}M`
  return `${symbol}${v.toLocaleString()}`
}

function calculateMarginOfSafety(intrinsicValue?: number, currentPrice?: number): number | null {
  if (!intrinsicValue || !currentPrice || currentPrice <= 0 || intrinsicValue <= 0) return null
  return ((intrinsicValue - currentPrice) / intrinsicValue) * 100
}

type PdfStatus = 'idle' | 'generating' | 'success' | 'error'

export function InvestmentRecommendation({ report, ticker }: InvestmentRecommendationProps) {
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false)
  const [pdfStatus, setPdfStatus] = useState<PdfStatus>('idle')
  const [pdfErrorMessage, setPdfErrorMessage] = useState('')

  const decision = report?.decision || {}
  const currentPrice = report?.analyst_recommendations?.details?.current_price
  const priceChange = report?.technicals?.details?.close_change_pct || report?.fundamentals?.details?.change_pct || 0
  const priceTarget = decision.price_target_12m
  const expectedReturn = decision.expected_return_pct || 0
  const dcfValuation = report?.fundamentals?.details?.dcf_valuation
  const dcfWarnings = dcfValuation?.sanity_check?.warnings || []
  const dcfScenarios = dcfValuation?.scenario_results || []

  const dcfValue = (() => {
    if (dcfScenarios.length > 0) {
      return dcfScenarios.find((s: any) => s.scenario === 'Base')?.result?.intrinsic_value_per_share
    }
    return dcfValuation?.intrinsic_value || null
  })()

  const marginOfSafety = calculateMarginOfSafety(dcfValue, currentPrice)
  const showValuationWarning = marginOfSafety != null && Math.abs(marginOfSafety) > 50
  const action = decision.action || 'Hold'
  const rating = decision.rating || 0
  const confidence = decision.confidence_score || 0
  const execSummary = decision.executive_summary || decision.professional_rationale || ''
  const entryZoneLow = decision.entry_zone_low || report?.technicals?.details?.entry_zone_low
  const entryZoneHigh = decision.entry_zone_high || report?.technicals?.details?.entry_zone_high
  const stopLoss = decision.stop_loss || report?.technicals?.details?.stop_loss

  const handleExportPDF = async () => {
    setIsGeneratingPDF(true)
    setPdfStatus('generating')
    setPdfErrorMessage('')
    try {
      const response = await fetch('/api/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: [report?.ticker] })
      })
      if (response.ok) {
        const blob = await response.blob()
        if (blob.type === 'application/pdf' || blob.size > 0) {
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `${report?.ticker || 'report'}_equity_research_${new Date().toISOString().split('T')[0]}.pdf`
          document.body.appendChild(a)
          a.click()
          a.remove()
          window.URL.revokeObjectURL(url)
          setPdfStatus('success')
          setTimeout(() => setPdfStatus('idle'), 3000)
        } else {
          const text = await blob.text()
          try { setPdfErrorMessage(JSON.parse(text).error || 'Failed to generate PDF') } catch { setPdfErrorMessage(text || 'Failed to generate PDF') }
          setPdfStatus('error')
          setTimeout(() => setPdfStatus('idle'), 5000)
        }
      } else {
        const ct = response.headers.get('content-type')
        const msg = ct?.includes('application/json')
          ? (await response.json()).error
          : await response.text()
        setPdfErrorMessage(msg || 'Failed to generate PDF')
        setPdfStatus('error')
        setTimeout(() => setPdfStatus('idle'), 5000)
      }
    } catch (error: any) {
      setPdfErrorMessage(error.message || 'Network error occurred')
      setPdfStatus('error')
      setTimeout(() => setPdfStatus('idle'), 5000)
    } finally {
      setIsGeneratingPDF(false)
    }
  }

  const statusMsg = pdfErrorMessage.length > 30 ? pdfErrorMessage.substring(0, 30) + '...' : pdfErrorMessage

  return (
    <div className="space-y-6">
      {/* PDF Export */}
      <div className="flex justify-end">
        <div className="flex items-center gap-3">
          {pdfStatus === 'success' && (
            <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-2 px-3 py-1.5 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 rounded-lg text-sm font-medium">
              <CheckCircle className="w-4 h-4" /> PDF downloaded successfully
            </motion.div>
          )}
          {pdfStatus === 'error' && (
            <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} title={pdfErrorMessage}
              className="flex items-center gap-2 px-3 py-1.5 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 rounded-lg text-sm font-medium max-w-xs">
              <AlertTriangle className="w-4 h-4" /> {statusMsg}
            </motion.div>
          )}
          <motion.button onClick={handleExportPDF} disabled={isGeneratingPDF}
            whileHover={!isGeneratingPDF ? { scale: 1.02 } : {}} whileTap={!isGeneratingPDF ? { scale: 0.98 } : {}}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all text-sm font-medium shadow-md ${
              isGeneratingPDF ? 'bg-blue-100 dark:bg-blue-900/50 border border-blue-300 dark:border-blue-800 text-blue-600 dark:text-blue-400 cursor-not-allowed'
              : pdfStatus === 'success' ? 'bg-green-100 dark:bg-green-900/50 border border-green-300 dark:border-green-800 text-green-700 dark:text-green-300'
              : 'bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-500 dark:to-blue-600 border border-blue-700 dark:border-blue-600 text-white hover:from-blue-700 hover:to-blue-800 dark:hover:from-blue-600 dark:hover:to-blue-700'
            }`}>
            {isGeneratingPDF ? (<><Loader2 className="w-4 h-4 animate-spin" /><span>Generating...</span></>)
              : pdfStatus === 'success' ? (<><CheckCircle className="w-4 h-4" /><span>Download Complete</span></>)
              : (<><Icons.Download className="w-4 h-4" /><span>Export PDF</span></>)}
          </motion.button>
        </div>
      </div>

      {currentPrice && (
        <ProfessionalHeader ticker={ticker || report?.ticker || 'N/A'} action={action} rating={rating}
          confidence={confidence} currentPrice={currentPrice} priceChange={priceChange}
          marketCap={report?.fundamentals?.details?.market_cap} />
      )}

      <div className="mb-2">
        <h1 className="text-3xl font-extrabold text-black dark:text-white tracking-tight">Investment Recommendation</h1>
        <p className="text-base text-slate-800 dark:text-slate-300 font-semibold mt-1">AI-powered comprehensive analysis</p>
      </div>

      {execSummary && (
        <CollapsibleSection title="Executive Summary" icon={<FileText className="w-6 h-6" />} defaultOpen={true}>
          <ExecutiveSummarySections summary={execSummary} />
        </CollapsibleSection>
      )}

      <CollapsibleSection title="Key Metrics" icon={<BarChart3 className="w-6 h-6" />} badge="4 metrics" defaultOpen={true}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {currentPrice && <MetricCard icon={DollarSign} label="Current Price" value={formatAmountByCurrency(currentPrice, ticker)} subtitle="Market value" color="slate" delay={0.1} tooltip="Current trading price" />}
          {priceTarget && <MetricCard icon={Target} label="Price Target" value={formatAmountByCurrency(priceTarget, ticker)} subtitle={decision.price_target_source || 'Analyst consensus target'} color="green" trend="up" delay={0.15} tooltip="12-month analyst target price" />}
          <MetricCard icon={expectedReturn > 0 ? TrendingUpIcon : TrendingDown} label="Expected Return" value={`${expectedReturn > 0 ? '+' : ''}${expectedReturn.toFixed(1)}%`} subtitle="12-month forecast" color={expectedReturn > 0 ? 'blue' : 'red'} trend={expectedReturn > 0 ? 'up' : 'down'} delay={0.2} tooltip="Expected percentage return over 12 months" />
          <MetricCard icon={FileText} label="DCF Valuation"
            value={dcfValuation?.dcf_applicable === false ? '⚠️ Not Applicable' : dcfValue ? formatAmountByCurrency(dcfValue, ticker) : 'Available'}
            subtitle={dcfValuation?.dcf_applicable === false ? dcfValuation.reason : 'Base case scenario'}
            color="purple" delay={0.25} tooltip="Discounted Cash Flow intrinsic value" />
        </div>
      </CollapsibleSection>

      {currentPrice && (
        <CollapsibleSection title="Valuation Analysis" icon={<TrendingUpIcon className="w-6 h-6" />} defaultOpen={true}>
          <ValuationVisualization currentPrice={currentPrice} intrinsicValue={dcfValue} priceTarget={priceTarget}
            entryZoneLow={entryZoneLow} entryZoneHigh={entryZoneHigh} stopLoss={stopLoss} ticker={ticker || report?.ticker} />
        </CollapsibleSection>
      )}

      {dcfWarnings.length > 0 && currentPrice && (
        <ActionableWarningBox
          warnings={[
            ...dcfWarnings.map((w: string) => ({
              type: 'valuation' as const,
              severity: showValuationWarning ? 'high' as const : 'moderate' as const,
              title: 'VALUATION RISK', message: w,
              action: w.includes('overvaluation') ? 'Wait for 50% correction before entry' : undefined
            })),
            ...(stopLoss ? [{ type: 'downside' as const, severity: 'high' as const, title: 'DOWNSIDE RISK',
              message: `Stop-loss level at ${formatAmountByCurrency(stopLoss, ticker)} (${((stopLoss - currentPrice) / currentPrice * 100).toFixed(1)}%)`,
              action: 'Set stop-loss alert at this level', actionLabel: 'Set Alert' }] : []),
            ...(entryZoneLow && entryZoneHigh ? [{ type: 'monitoring' as const, severity: 'moderate' as const, title: 'MONITORING REQUIRED',
              message: `Price needs to reach entry zone (${formatAmountByCurrency(entryZoneLow, ticker)} - ${formatAmountByCurrency(entryZoneHigh, ticker)})`,
              action: 'Add to watchlist for monitoring', actionLabel: 'Add to Watchlist' }] : [])
          ]}
          onSetAlert={(price) => console.log('Set alert at:', price)}
          onAddToWatchlist={() => console.log('Add to watchlist')}
        />
      )}

      {dcfScenarios.length > 0 && currentPrice && (
        <CollapsibleSection title="DCF Scenario Analysis" icon={<BarChart3 className="w-6 h-6" />} badge="3 scenarios" defaultOpen={true}>
          <ScenarioVisualization
            scenarios={dcfScenarios.map((s: any) => ({ name: s.scenario || s.name, probability: s.probability || 33.33, intrinsic_value: s.intrinsic_value || s.result?.intrinsic_value_per_share || 0 }))}
            currentPrice={currentPrice} ticker={ticker || report?.ticker} />
        </CollapsibleSection>
      )}
    </div>
  )
}
