import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../api';
import { FiMail, FiSend, FiArrowLeft } from 'react-icons/fi';
import AiBot from '../components/AiBot';
import MatrixBackground from '../components/MatrixBackground';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [botExpression, setBotExpression] = useState('neutral');
  const cardRef = useRef(null);

  useEffect(() => {
    const handleBgMove = (e) => {
      document.documentElement.style.setProperty('--mouse-x', `${e.clientX}px`);
      document.documentElement.style.setProperty('--mouse-y', `${e.clientY}px`);
    };
    window.addEventListener('mousemove', handleBgMove);
    return () => window.removeEventListener('mousemove', handleBgMove);
  }, []);

  const handleCardMove = (e) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const rotateX = (y / (rect.height / 2)) * -8;
    const rotateY = (x / (rect.width / 2)) * 8;
    cardRef.current.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
    cardRef.current.style.transition = 'none';
  };

  const handleCardLeave = () => {
    if (cardRef.current) {
      cardRef.current.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)`;
      cardRef.current.style.transition = 'transform 0.5s ease';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setResetToken('');
    setLoading(true);
    setBotExpression('neutral');

    try {
      const res = await forgotPassword({ email });
      setMessage(res.data.message);
      if (res.data.reset_token) {
        setResetToken(res.data.reset_token);
      }
      setBotExpression('happy');
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
      setBotExpression('sad');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page" style={{ position: 'relative', overflow: 'hidden' }}>
      <MatrixBackground isError={!!error} />
      <div className="auth-card" ref={cardRef} onMouseMove={handleCardMove} onMouseLeave={handleCardLeave}>
        <div className="auth-header">
          <div className="bot-mascot-container" style={{ marginTop: '-40px', marginBottom: '10px' }}>
            <AiBot size={75} expression={botExpression} isError={!!error} />
          </div>
          <h1>Password Reset</h1>
          <p>Enter your email address to receive a reset link</p>
        </div>
        
        {error && <div className="auth-error">{error}</div>}
        {message && (
          <div className="auth-error" style={{ background: 'rgba(52, 211, 153, 0.1)', color: 'var(--success)', borderColor: 'rgba(52, 211, 153, 0.2)' }}>
            {message}
          </div>
        )}
        
        {resetToken && (
          <div className="auth-form" style={{ marginTop: '15px' }}>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              In a real app, you would receive an email. For testing purposes, click below to use the generated token directly:
            </p>
            <Link to={`/reset-password/${resetToken}`} className="btn-primary" style={{ textDecoration: 'none' }}>
              Reset Password Now
            </Link>
          </div>
        )}

        {!resetToken && (
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="input-group">
              <FiMail className="input-icon" />
              <input
                id="forgot-email"
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? <span className="btn-spinner"></span> : <>Send Reset Link <FiSend style={{marginLeft: '8px'}} /></>}
            </button>
          </form>
        )}

        <p className="auth-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
          <FiArrowLeft /> <Link to="/login">Back to Sign in</Link>
        </p>
      </div>
    </div>
  );
}
