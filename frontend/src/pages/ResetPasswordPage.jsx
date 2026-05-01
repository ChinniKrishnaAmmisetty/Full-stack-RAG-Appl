import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { FiArrowLeft, FiCheck, FiEye, FiEyeOff, FiLock } from 'react-icons/fi';
import { resetPassword } from '../api';
import AuthShell from '../components/AuthShell';

const RESET_HIGHLIGHTS = [
  {
    title: 'Fresh credentials',
    description: 'Choose a strong password with at least six characters.',
  },
  {
    title: 'Quick recovery',
    description: 'After success, you will be redirected back to sign in.',
  },
  {
    title: 'No workspace loss',
    description: 'Your documents and previous chat sessions remain available.',
  },
];

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');

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
      const response = await resetPassword({ token, new_password: password });
      setMessage(response.data.message);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired token. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Password Update"
      showcaseTitle="Set a new password and return to your document workspace."
      showcaseText="Once updated, you can sign back in and continue reviewing files, sessions, and answers."
      highlights={RESET_HIGHLIGHTS}
      formTitle="Create a new password"
      formText="Enter the new password you want to use for your account."
      footer={
        <p className="auth-footer auth-footer-inline">
          <FiArrowLeft /> <Link to="/login">Back to sign in</Link>
        </p>
      }
    >
      {error && <div className="auth-notice error">{error}</div>}
      {message && <div className="auth-notice success">{message} Redirecting to login...</div>}

      <form onSubmit={handleSubmit} className="auth-form">
        <div className="input-group">
          <FiLock className="input-icon" />
          <input
            type={showPassword ? 'text' : 'password'}
            placeholder="New password (min 6 characters)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={6}
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
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
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

        <button type="submit" className="btn-primary" disabled={loading || Boolean(message)}>
          {loading ? <span className="btn-spinner"></span> : <><FiCheck /> Reset password</>}
        </button>
      </form>
    </AuthShell>
  );
}
