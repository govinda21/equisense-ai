import { useState } from 'react'

const TABS = ['Overview', 'News', 'Technicals', 'Fundamentals', 'Peers', 'Analysts', 'Growth', 'Valuation', 'Cashflow', 'Leadership', 'Sources'] as const

type Report = any

export function TabbedReportViewer({ report }: { report: Report }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Overview')

  const SummaryItem = ({ title, value }: { title: string; value: any }) => (
    <div className="card p-4">
      <div className="text-slate-600 text-sm">{title}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="report sections" className="flex flex-wrap gap-2">
        {TABS.map(t => (
          <button key={t} role="tab" aria-selected={tab === t} className={`rounded-lg border px-3 py-2 text-sm ${tab === t ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-300'}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="grid md:grid-cols-3 gap-6">
          <SummaryItem title="Recommendation" value={report?.decision?.action} />
          <SummaryItem title="Rating" value={report?.decision?.rating} />
          <SummaryItem title="Expected Return" value={`${report?.decision?.expected_return_pct}%`} />
        </div>
      )}

      {tab === 'News' && (
        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="text-lg font-semibold mb-3">Recent Financial News</h3>
            {report?.news_sentiment?.raw_articles && report.news_sentiment.raw_articles.length > 0 ? (
              <div className="space-y-4">
                {report.news_sentiment.raw_articles.map((article: any, idx: number) => (
                  <div key={idx} className="border-l-4 border-blue-500 pl-4">
                    <h4 className="font-medium text-gray-900">{article.title}</h4>
                    <p className="text-sm text-gray-600 mt-1">{article.summary}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>Source: {article.source}</span>
                      <span>Published: {new Date(article.published_at).toLocaleString()}</span>
                      {article.url && (
                        <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          Read more →
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No recent news articles available for this ticker.</p>
                <p className="text-sm mt-2">News data is fetched from Yahoo Finance and other sources.</p>
              </div>
            )}
          </div>
          
          <div className="card p-4">
            <h3 className="text-lg font-semibold mb-2">News Analysis</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-gray-600">Sentiment Score</div>
                <div className="text-lg font-medium">{report?.news_sentiment?.score ? (report.news_sentiment.score * 100).toFixed(1) + '%' : '—'}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Article Count</div>
                <div className="text-lg font-medium">{report?.news_sentiment?.article_count || 0}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Latest News</div>
                <div className="text-sm font-medium">{report?.news_sentiment?.latest_date ? new Date(report.news_sentiment.latest_date).toLocaleDateString() : '—'}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Sources</div>
                <div className="text-sm font-medium">{report?.news_sentiment?.sources?.join(', ') || '—'}</div>
              </div>
            </div>
            <div className="mt-4">
              <div className="text-sm text-gray-600">Summary</div>
              <div className="text-sm mt-1">{report?.news_sentiment?.summary || 'No summary available'}</div>
            </div>
          </div>
        </div>
      )}

      {tab === 'Technicals' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.technicals?.details, null, 2)}</pre>
      )}
      {tab === 'Fundamentals' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.fundamentals?.details, null, 2)}</pre>
      )}
      {tab === 'Peers' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.peer_analysis?.details, null, 2)}</pre>
      )}
      {tab === 'Analysts' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.analyst_recommendations?.details, null, 2)}</pre>
      )}
      {tab === 'Growth' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.growth_prospects?.details, null, 2)}</pre>
      )}
      {tab === 'Valuation' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.valuation?.details, null, 2)}</pre>
      )}
      {tab === 'Cashflow' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.cashflow?.details, null, 2)}</pre>
      )}
      {tab === 'Leadership' && (
        <pre className="card p-4 text-sm whitespace-pre-wrap break-words">{JSON.stringify(report?.leadership?.details, null, 2)}</pre>
      )}
      {tab === 'Sources' && (
        <div className="card p-4 text-sm">Explore sources: News and YouTube titles used for sentiment.
          <pre className="mt-3 whitespace-pre-wrap break-words">{JSON.stringify({ news: report?.news_sentiment?.details, youtube: report?.youtube_sentiment?.details }, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
