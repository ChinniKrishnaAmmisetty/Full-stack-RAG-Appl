import { useLocation, useNavigate } from 'react-router-dom';
import { FiClock, FiFileText, FiGrid, FiLogOut, FiMessageSquare, FiMoon, FiPlus, FiSettings, FiSun, FiTrash2 } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function Sidebar({
  isOpen,
  user,
  onOpenSettings,
  sessions = [],
  activeSessionId = null,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  documents = [],
  onNavigate,
}) {
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { label: 'Chat', path: '/chat', icon: <FiMessageSquare /> },
    { label: 'Documents', path: '/documents', icon: <FiFileText /> },
    { label: 'Dashboard', path: '/dashboard', icon: <FiGrid /> },
  ];

  const readyDocs = documents.filter((document) => document.status === 'ready').length;
  const userInitial = user?.username?.[0]?.toUpperCase() || '?';

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`} id="sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand-row">
          <div className="sidebar-logo">AI</div>
          <div className="sidebar-brand">
            <span className="sidebar-eyebrow">Workspace</span>
            <h2 className="brand-name">AI Chatbot</h2>
            <p className="brand-sub">RAG assistant</p>
          </div>
        </div>

        {onCreateSession && (
          <button className="new-chat-btn" onClick={onCreateSession}>
            <FiPlus /> New Chat
          </button>
        )}
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-title">Navigation</div>
        {navItems.map((item) => (
          <button
            key={item.path}
            className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            onClick={() => {
              navigate(item.path);
              onNavigate?.();
            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-sessions">
        <div className="sessions-header">
          <span className="sessions-label">Sessions</span>
          <span className="sessions-count">{sessions.length}</span>
        </div>

        {sessions.length === 0 ? (
          <p className="no-sessions">No conversations yet.</p>
        ) : (
          <div className="session-list">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-row ${activeSessionId === session.id ? 'active' : ''}`}
              >
                <button
                  className="session-btn"
                  onClick={() => {
                    onSelectSession?.(session.id);
                    onNavigate?.();
                  }}
                >
                  <FiClock />
                  <span className="session-title">{session.title}</span>
                </button>

                {onDeleteSession && (
                  <button
                    className="session-delete"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    title="Delete session"
                  >
                    <FiTrash2 />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="sidebar-library">
        <div className="library-stat"><span>Documents</span><strong>{documents.length}</strong></div>
        <div className="library-stat"><span>Ready for chat</span><strong>{readyDocs}</strong></div>
      </div>

      <div className="sidebar-bottom">
        <div className="user-info">
          <div className="user-avatar">{userInitial}</div>
          <div className="user-details">
            <span className="user-name">{user?.username || 'User'}</span>
            <span className="user-email">{user?.email || ''}</span>
          </div>
        </div>

        <div className="sidebar-actions">
          <button
            className="sidebar-icon-btn"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <FiSun /> : <FiMoon />}
          </button>
          <button className="sidebar-icon-btn" onClick={onOpenSettings} title="Settings">
            <FiSettings />
          </button>
          <button className="sidebar-icon-btn" onClick={logout} title="Logout">
            <FiLogOut />
          </button>
        </div>
      </div>
    </aside>
  );
}
