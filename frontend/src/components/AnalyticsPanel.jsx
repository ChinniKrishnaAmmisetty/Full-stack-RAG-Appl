import { FiX } from 'react-icons/fi';

const formatLatency = (averageResponseTimeMs) => {
  if (averageResponseTimeMs === null || averageResponseTimeMs === undefined) {
    return 'Not available';
  }

  return `${(averageResponseTimeMs / 1000).toFixed(2)} s`;
};

const formatReranker = (rerankerUsed) => {
  if (rerankerUsed === null || rerankerUsed === undefined) {
    return 'Not available';
  }

  return rerankerUsed ? 'Yes' : 'No';
};

export default function AnalyticsPanel({
  sessions,
  messages,
  sources,
  onClose,
  averageResponseTimeMs,
  rerankerUsed,
}) {
  return (
    <aside className="analytics-panel">
      <div className="analytics-header">
        <div>
          <h3>Analytics</h3>
          <p>Session-level details from the current chat view.</p>
        </div>

        <button className="close-panel-btn" onClick={onClose} title="Close analytics">
          <FiX />
        </button>
      </div>

      <div className="analytics-section">
        <div className="stat-row"><span>Total messages</span><strong>{messages.length}</strong></div>
        <div className="stat-row"><span>Total sessions</span><strong>{sessions.length}</strong></div>
        <div className="stat-row"><span>Avg response time</span><strong>{formatLatency(averageResponseTimeMs)}</strong></div>
        <div className="stat-row"><span>Retrieved chunks</span><strong>{sources.length}</strong></div>
        <div className="stat-row"><span>Reranker used</span><strong>{formatReranker(rerankerUsed)}</strong></div>
      </div>

      <div className="analytics-section">
        <h4>Last response sources</h4>
        {sources.length === 0 ? (
          <p className="analytics-empty">No sources to show yet.</p>
        ) : (
          <div className="source-list">
            {sources.map((source, index) => (
              <div key={`${source.document_name}-${source.chunk_index}-${index}`} className="source-item">
                <span className="source-name">{source.document_name}</span>
                <span className="source-meta">
                  Chunk {source.chunk_index}
                  {source.confidence !== undefined ? ` | Match ${Math.round(source.confidence * 100)}%` : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
