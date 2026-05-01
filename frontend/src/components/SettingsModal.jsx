import { FiInfo, FiMail, FiMoon, FiSun, FiUser, FiX } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function SettingsModal({ isOpen, onClose }) {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="modal-close" onClick={onClose} title="Close">
            <FiX />
          </button>
        </div>

        <div className="settings-section">
          <h3 className="section-title">Profile</h3>
          <div className="profile-card">
            <div className="profile-avatar">{user?.username?.[0]?.toUpperCase() || '?'}</div>
            <div className="profile-details">
              <div className="profile-row">
                <FiUser className="profile-icon" />
                <span>{user?.username || 'Unknown user'}</span>
              </div>
              <div className="profile-row">
                <FiMail className="profile-icon" />
                <span>{user?.email || 'No email available'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="settings-section">
          <h3 className="section-title">Appearance</h3>
          <button type="button" className="theme-option-row" onClick={toggleTheme}>
            <div className="theme-option-copy">
              <div className="about-row">
                {theme === 'dark' ? <FiSun /> : <FiMoon />}
                <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
              </div>
              <p className="about-desc">
                Toggle the workspace appearance without changing any data or app behavior.
              </p>
            </div>
            <span className="theme-option-state">{theme === 'dark' ? 'Dark' : 'Light'}</span>
          </button>
        </div>

        <div className="settings-section">
          <h3 className="section-title">About</h3>
          <div className="about-info">
            <div className="about-row">
              <FiInfo />
              <span>ACK AI Workspace</span>
            </div>
            <p className="about-desc">
              Retrieval-grounded chat with document sources, session history, and live dashboard metrics.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
