import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiLock, FiMail, FiUser, FiUserPlus } from 'react-icons/fi';
import { registerUser } from '../api';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../context/AuthContext';
import { playWelcomeSound } from '../utils/welcomeSound';

const REGISTER_HIGHLIGHTS = [
  {
    title: 'Private knowledge base',
    description: 'Each account works with its own uploaded document collection.',
  },
  {
    title: 'Session memory',
    description: 'Keep separate conversation threads for different research tasks.',
  },
  {
    title: 'Fast evidence review',
    description: 'See which document chunks supported the answer.',
  },
];

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);

    try {
      const response = await registerUser({ email, username, password });
      const token = response.data.access_token;
      await login(token);
      playWelcomeSound();

      setTimeout(() => navigate('/chat'), 500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Workspace Setup"
      showcaseTitle="Create a focused AI workspace for your team documents."
      showcaseText="Upload reports, policies, spreadsheets, and notes, then ask questions in a cleaner, professional environment."
      highlights={REGISTER_HIGHLIGHTS}
      formTitle="Create your account"
      formText="Set up your login details to start building your document workspace."
      footer={
        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      }
    >
      {error && <div className="auth-notice error">{error}</div>}

      <form onSubmit={handleSubmit} className="auth-form">
        <div className="input-group">
          <FiUser className="input-icon" />
          <input
            id="register-username"
            type="text"
            placeholder="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            minLength={3}
            autoComplete="username"
          />
        </div>

        <div className="input-group">
          <FiMail className="input-icon" />
          <input
            id="register-email"
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
          />
        </div>

        <div className="input-group">
          <FiLock className="input-icon" />
          <input
            id="register-password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Password (min 6 characters)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={6}
            autoComplete="new-password"
          />
          <button
            type="button"
            className="password-toggle-icon"
            onClick={() => setShowPassword((current) => !current)}
            tabIndex="-1"
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <FiEyeOff /> : <FiEye />}
          </button>
        </div>

        <div className="input-group">
          <FiLock className="input-icon" />
          <input
            id="register-confirm-password"
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            autoComplete="new-password"
          />
          <button
            type="button"
            className="password-toggle-icon"
            onClick={() => setShowConfirmPassword((current) => !current)}
            tabIndex="-1"
            title={showConfirmPassword ? 'Hide password' : 'Show password'}
          >
            {showConfirmPassword ? <FiEyeOff /> : <FiEye />}
          </button>
        </div>

        <button id="register-submit" type="submit" className="btn-primary" disabled={loading}>
          {loading ? <span className="btn-spinner"></span> : <><FiUserPlus /> Create account</>}
        </button>
      </form>
    </AuthShell>
  );
}
