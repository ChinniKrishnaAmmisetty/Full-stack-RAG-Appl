import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { registerUser, getMe } from '../api';
import { useAuth } from '../context/AuthContext';
import { FiMail, FiLock, FiUser, FiUserPlus } from 'react-icons/fi';
import AiBot from '../components/AiBot';
import MatrixBackground from '../components/MatrixBackground';
import { playWelcomeSound } from '../utils/welcomeSound';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isPasswordFocused, setIsPasswordFocused] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [botExpression, setBotExpression] = useState('neutral');
  const { login } = useAuth();
  const navigate = useNavigate();
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
      const res = await registerUser({ email, username, password });
      const token = res.data.access_token;
      localStorage.setItem('token', token);
      const userRes = await getMe();
      login(token, userRes.data);
      
      setBotExpression('happy');
      playWelcomeSound();
      setTimeout(() => navigate('/chat'), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
      setBotExpression('sad');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page" id="register-page" style={{ position: 'relative', overflow: 'hidden' }}>
      <MatrixBackground isError={!!error} />
      <div className="auth-card" ref={cardRef} onMouseMove={handleCardMove} onMouseLeave={handleCardLeave}>
        <div className="auth-header">
          <div className="bot-mascot-container" style={{ marginTop: '-40px', marginBottom: '10px' }}>
            <AiBot size={75} expression={isPasswordFocused ? 'back' : botExpression} isError={!!error} />
          </div>
          <h1>Join <span className="brand-gradient">ACK AI</span></h1>
          <p>Create an account to start chatting with your documents</p>
        </div>
        {error && <div className="auth-error">{error}</div>}
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <FiUser className="input-icon" />
            <input
              id="register-username"
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
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
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="input-group">
            <FiLock className="input-icon" />
            <input
              id="register-password"
              type="password"
              placeholder="Password (min 6 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setIsPasswordFocused(true)}
              onBlur={() => setIsPasswordFocused(false)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </div>
          <div className="input-group">
            <FiLock className="input-icon" />
            <input
              id="register-confirm-password"
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onFocus={() => setIsPasswordFocused(true)}
              onBlur={() => setIsPasswordFocused(false)}
              required
              autoComplete="new-password"
            />
          </div>
          <button id="register-submit" type="submit" className="btn-primary" disabled={loading}>
            {loading ? <span className="btn-spinner"></span> : <><FiUserPlus /> Create Account</>}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
