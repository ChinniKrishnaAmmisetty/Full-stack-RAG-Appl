import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { resetPassword } from '../api';
import { FiLock, FiCheck, FiArrowLeft, FiEye, FiEyeOff } from 'react-icons/fi';
import AiBot from '../components/AiBot';
import MatrixBackground from '../components/MatrixBackground';

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isPasswordFocused, setIsPasswordFocused] = useState(false);
  
  const [message, setMessage] = useState('');
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
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setBotExpression('sad');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      setBotExpression('sad');
      return;
    }

    setLoading(true);
    setBotExpression('neutral');

    try {
      const res = await resetPassword({ token, new_password: password });
      setMessage(res.data.message);
      setBotExpression('happy');
      
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired token. Please try again.');
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
            <AiBot size={75} expression={isPasswordFocused ? 'back' : botExpression} isError={!!error} />
          </div>
          <h1>Create New Password</h1>
          <p>Please enter your new password</p>
        </div>
        
        {error && <div className="auth-error">{error}</div>}
        {message && (
          <div className="auth-error" style={{ background: 'rgba(52, 211, 153, 0.1)', color: 'var(--success)', borderColor: 'rgba(52, 211, 153, 0.2)' }}>
            {message} Redirecting to login...
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <FiLock className="input-icon" />
            <input
              type={showPassword ? "text" : "password"}
              placeholder="New Password (min 6 chars)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setIsPasswordFocused(true)}
              onBlur={() => setIsPasswordFocused(false)}
              required
              minLength={6}
              style={{ paddingRight: '40px' }}
            />
            <button
              type="button"
              className="password-toggle-icon"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex="-1"
            >
              {showPassword ? <FiEyeOff /> : <FiEye />}
            </button>
          </div>
          <div className="input-group">
            <FiLock className="input-icon" />
            <input
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Confirm New Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onFocus={() => setIsPasswordFocused(true)}
              onBlur={() => setIsPasswordFocused(false)}
              required
              style={{ paddingRight: '40px' }}
            />
            <button
              type="button"
              className="password-toggle-icon"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              tabIndex="-1"
            >
              {showConfirmPassword ? <FiEyeOff /> : <FiEye />}
            </button>
          </div>
          
          <button type="submit" className="btn-primary" disabled={loading || message}>
            {loading ? <span className="btn-spinner"></span> : <>Reset Password <FiCheck style={{marginLeft: '8px'}} /></>}
          </button>
        </form>

        <p className="auth-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
          <FiArrowLeft /> <Link to="/login">Back to Sign in</Link>
        </p>
      </div>
    </div>
  );
}
