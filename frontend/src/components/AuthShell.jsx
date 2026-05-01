import { FiMoon, FiSun } from 'react-icons/fi';
import { useTheme } from '../context/ThemeContext';

export default function AuthShell({
  eyebrow = 'ACK AI',
  showcaseTitle,
  showcaseText,
  highlights = [],
  formTitle,
  formText,
  children,
  footer,
}) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="auth-page">
      <button
        type="button"
        className="auth-theme-toggle"
        onClick={toggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <FiSun /> : <FiMoon />}
        <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
      </button>

      <div className="auth-shell">
        <aside className="auth-showcase">
          <span className="auth-showcase-badge">{eyebrow}</span>
          <h1>{showcaseTitle}</h1>
          <p>{showcaseText}</p>

          <div className="auth-highlight-list">
            {highlights.map((item) => (
              <div key={item.title} className="auth-highlight-card">
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </div>
            ))}
          </div>
        </aside>

        <section className="auth-card">
          <div className="auth-header">
            <span className="auth-kicker">{eyebrow}</span>
            <h2>{formTitle}</h2>
            <p>{formText}</p>
          </div>

          {children}
          {footer}
        </section>
      </div>
    </div>
  );
}
