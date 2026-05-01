import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FiArrowLeft, FiMail, FiSend } from 'react-icons/fi';
import { forgotPassword } from '../api';
import AuthShell from '../components/AuthShell';

const RECOVERY_HIGHLIGHTS = [
  {
    title: 'Secure reset flow',
    description: 'Generate a short-lived reset link tied to your account.',
  },
  {
    title: 'Fast return',
    description: 'Pick up where you left off after signing back in.',
  },
  {
    title: 'Simple testing',
    description: 'This environment exposes the reset token directly for development.',
  },
];

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setResetToken('');
    setLoading(true);

    try {
      const response = await forgotPassword({ email });
      setMessage(response.data.message);
      if (response.data.reset_token) {
        setResetToken(response.data.reset_token);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Account Recovery"
      showcaseTitle="Recover access without losing your workspace."
      showcaseText="Request a reset link and return to your documents, conversations, and saved research sessions."
      highlights={RECOVERY_HIGHLIGHTS}
      formTitle="Reset your password"
      formText="Enter your email address and we will prepare a reset link."
      footer={
        <p className="auth-footer auth-footer-inline">
          <FiArrowLeft /> <Link to="/login">Back to sign in</Link>
        </p>
      }
    >
      {error && <div className="auth-notice error">{error}</div>}
      {message && <div className="auth-notice success">{message}</div>}

      {resetToken ? (
        <div className="auth-form">
          <p className="field-caption">
            In a real app, you would receive an email. For testing purposes, use the generated token directly.
          </p>
          <Link to={`/reset-password/${resetToken}`} className="btn-primary">
            Reset password now
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <FiMail className="input-icon" />
            <input
              id="forgot-email"
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? <span className="btn-spinner"></span> : <><FiSend /> Send reset link</>}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
