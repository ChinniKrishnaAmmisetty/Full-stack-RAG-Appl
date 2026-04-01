import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { FiX, FiSun, FiMoon, FiUser, FiMail, FiShield } from 'react-icons/fi';

export default function SettingsModal({ isOpen, onClose }) {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="modal-close" onClick={onClose}><FiX /></button>
        </div>

        <div className="settings-section">
          <h3 className="section-title">Profile</h3>
          <div className="profile-card">
            <div className="profile-avatar">
              {user?.username?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="profile-details">
              <div className="profile-row">
                <FiUser className="profile-icon" />
                <span>{user?.username || 'Unknown'}</span>
              </div>
              <div className="profile-row">
                <FiMail className="profile-icon" />
                <span>{user?.email || 'No email'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="settings-section">
          <h3 className="section-title">Appearance</h3>
          <div className="theme-toggle-row">
            <div className="theme-label">
              {theme === 'dark' ? <FiMoon /> : <FiSun />}
              <span>{theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
            </div>
            <button className={`theme-switch ${theme}`} onClick={toggleTheme}>
              <div className="switch-knob" />
            </button>
          </div>
        </div>

        <div className="settings-section">
          <h3 className="section-title">About</h3>
          <div className="about-info">
            <div className="about-row"><FiShield /> <span>RAG Document Assistant v1.0</span></div>
            <p className="about-desc">Powered by Gemini API with Milvus vector search</p>
          </div>
        </div>
      </div>
    </div>
  );
}
