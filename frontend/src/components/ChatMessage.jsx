import ReactMarkdown from 'react-markdown';

function TypingDots() {
  return (
    <span className="typing-dots" aria-hidden="true">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </span>
  );
}

export default function ChatMessage({ message, sources = [] }) {
  const isUser = message.role === 'user';
  const hasContent = Boolean(message.content);
  const showProgressTimeline = !isUser && message.loading && (message.statusSteps || []).length > 0;
  const statusSteps = message.statusSteps || [];

  return (
    <div className={`chat-message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className={`chat-bubble ${isUser ? 'user' : 'assistant'} ${showProgressTimeline ? 'has-progress' : ''}`}>
        <div className="chat-message-label">{isUser ? 'You' : 'ACK AI'}</div>

        {showProgressTimeline && (
          <div className="chat-progress-card" aria-live="polite">
            <div className="chat-progress-header">
              <TypingDots />
              <div className="chat-progress-copy">
                <strong>Working in background</strong>
              </div>
            </div>

            {statusSteps.length > 0 && (
              <div className="chat-progress-list">
                {statusSteps.map((step) => (
                  <div key={step.stage} className={`chat-progress-step ${step.state || 'pending'}`}>
                    <span className="chat-progress-marker" />
                    <div className="chat-progress-step-copy">
                      <span>{step.step}</span>
                      {step.state === 'active' && step.detail && <small>{step.detail}</small>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {hasContent && (
          <div className="chat-message-content">
            {isUser ? <p>{message.content}</p> : <ReactMarkdown>{message.content}</ReactMarkdown>}
          </div>
        )}

        {!isUser && sources.length > 0 && (
          <div className="chat-sources">
            <div className="chat-sources-title">{message.loading ? 'Matched chunks' : 'Sources'}</div>
            <div className="chat-sources-list">
              {sources.map((source, index) => {
                const matchText = source.confidence !== undefined
                  ? `Match ${Math.round(source.confidence * 100)}%`
                  : null;

                return (
                  <div
                    key={`${source.document_name}-${source.chunk_index}-${index}`}
                    className="chat-source-row"
                  >
                    <span className="chat-source-name">{source.document_name}</span>
                    <span className="chat-source-meta">
                      Chunk {source.chunk_index}
                      {matchText ? ` | ${matchText}` : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
