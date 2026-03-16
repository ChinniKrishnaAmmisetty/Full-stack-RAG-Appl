import { useAuth } from '../context/AuthContext';
import { FiPlus, FiMessageSquare, FiTrash2, FiLogOut, FiSettings, FiFile, FiCheckCircle, FiAlertCircle, FiLoader } from 'react-icons/fi';

export default function Sidebar({ sessions, activeSessionId, onSelectSession, onNewChat, onDeleteSession, isOpen, user, documents, onOpenSettings, onDeleteDocument }) {
  const { logout } = useAuth();

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ready': return <FiCheckCircle className="doc-status-icon ready" />;
      case 'failed': return <FiAlertCircle className="doc-status-icon failed" />;
      default: return <FiLoader className="doc-status-icon processing" />;
    }
  };

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`} id="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span className="logo-icon">🤖</span>
          <span className="logo-text">ACK AI</span>
        </div>
        <button className="new-chat-btn" onClick={onNewChat} id="new-chat-btn" title="New Chat">
          <FiPlus />
        </button>
      </div>

      {/* Documents Section */}
      {documents && documents.length > 0 && (
        <div className="sidebar-docs">
          <div className="sessions-label">Documents</div>
          {documents.map((doc) => (
            <div key={doc.id} className="doc-sidebar-item">
              {getStatusIcon(doc.status)}
              <span className="doc-sidebar-name" title={doc.filename}>{doc.filename}</span>
              <button
                className="session-delete doc-delete-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteDocument(doc.id);
                }}
                title="Delete document"
              >
                <FiTrash2 />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Chat History */}
      <div className="sidebar-sessions">
        <div className="sessions-label">Chat History</div>
        {sessions.length === 0 && (
          <p className="no-sessions">No chats yet. Start a new conversation!</p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
            onClick={() => onSelectSession(session.id)}
          >
            <FiMessageSquare className="session-icon" />
            <span className="session-title">{session.title}</span>
            <button
              className="session-delete"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteSession(session.id);
              }}
              title="Delete chat"
            >
              <FiTrash2 />
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">{user?.username?.[0]?.toUpperCase() || '?'}</div>
          <span className="user-name">{user?.username || 'User'}</span>
        </div>
        <div className="sidebar-actions">
          <button className="settings-btn" onClick={onOpenSettings} title="Settings">
            <FiSettings />
          </button>
          <button className="logout-btn" onClick={logout} id="logout-btn" title="Logout">
            <FiLogOut />
          </button>
        </div>
      </div>
    </aside>
  );
}
