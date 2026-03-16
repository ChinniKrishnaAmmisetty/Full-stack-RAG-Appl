import ReactMarkdown from 'react-markdown';
import { FiUser, FiCpu } from 'react-icons/fi';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isStreaming = message.loading && message.content?.length > 0;
  const isWaiting = message.loading && (!message.content || message.content.length === 0);

  return (
    <div className={`msg-row ${isUser ? 'msg-user' : 'msg-assistant'}`}>
      <div className="msg-wrapper">
        <div className="msg-avatar">
          {isUser ? <FiUser /> : <FiCpu />}
        </div>
        <div className="msg-body">
          <div className="msg-sender">{isUser ? 'You' : 'ACK AI'}</div>
          <div className="msg-content">
            {isWaiting ? (
              <div className="typing-dots">
                <span></span><span></span><span></span>
              </div>
            ) : isUser ? (
              <p>{message.content}</p>
            ) : (
              <>
                <ReactMarkdown>{message.content}</ReactMarkdown>
                {isStreaming && <span className="stream-cursor">▌</span>}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

