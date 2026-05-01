import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiLock, FiLogIn, FiUser } from 'react-icons/fi';
import { loginUser } from '../api';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../context/AuthContext';
import { playWelcomeSound } from '../utils/welcomeSound';

const LOGIN_HIGHLIGHTS = [
  {
    title: 'Grounded responses',
    description: 'Every answer is generated from the documents you upload.',
  },
  {
    title: 'Workspace history',
    description: 'Return to earlier conversations without losing context.',
  },
  {
    title: 'Source visibility',
    description: 'Review the matching evidence behind each response.',
  },
];

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    if (password.length < 6) {
      setError('Incorrect username or password.');
      setLoading(false);
      return;
    }

    try {
      const response = await loginUser({ username, password });
      const token = response.data.access_token;
      await login(token);
      playWelcomeSound();

      setTimeout(() => navigate('/chat'), 500);
    } catch (err) {
      const status = err.response?.status;
      if (status === 401) {
        setError(err.response?.data?.detail || 'Incorrect username/email or password.');
      } else if (status === 429) {
        setError('Too many login attempts. Please wait a minute and try again.');
      } else if (!err.response) {
        setError('Cannot reach the backend. Make sure FastAPI is running on http://127.0.0.1:8000.');
      } else {
        setError(err.response?.data?.detail || 'Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Secure Access"
      showcaseTitle="Professional document research, without the clutter."
      showcaseText="ACK AI keeps your uploaded knowledge base, verified answers, and conversation history in one calm workspace."
      highlights={LOGIN_HIGHLIGHTS}
      formTitle="Sign in"
      formText="Use your username or email and password to continue to your document workspace."
      footer={
        <p className="auth-footer">
          Don&apos;t have an account? <Link to="/register">Create one</Link>
        </p>
      }
    >
      {error && <div className="auth-notice error">{error}</div>}

      <form onSubmit={handleLogin} className="auth-form">
        <div className="input-group">
          <FiUser className="input-icon" />
          <input
            id="login-username"
            type="text"
            placeholder="Username or email"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            autoComplete="username"
          />
        </div>

        <div className="input-group">
          <FiLock className="input-icon" />
          <input
            id="login-password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="current-password"
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

        <div className="auth-helper-row">
          <Link to="/forgot-password" className="auth-link">
            Forgot password?
          </Link>
        </div>

        <button id="login-submit" type="submit" className="btn-primary" disabled={loading}>
          {loading ? <span className="btn-spinner"></span> : <><FiLogIn /> Sign in</>}
        </button>
      </form>
    </AuthShell>
  );
}
