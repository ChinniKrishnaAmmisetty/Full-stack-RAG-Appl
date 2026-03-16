import { useEffect, useRef, useState } from 'react';
import './AiBot.css';

/**
 * AI Robot mascot that follows the cursor with its eyes.
 * Supports different expressions: 'neutral', 'happy', 'sad', 'laugh'.
 */
export default function AiBot({ size = 120, expression = 'neutral' }) {
  const [isHovered, setIsHovered] = useState(false);
  const botRef = useRef(null);
  const leftEyeRef = useRef(null);
  const rightEyeRef = useRef(null);

  useEffect(() => {
    const handleMouseMove = (e) => {
      const bot = botRef.current;
      if (!bot) return;

      const rect = bot.getBoundingClientRect();
      const botCenterX = rect.left + rect.width / 2;
      const botCenterY = rect.top + rect.height / 2;

      const dx = e.clientX - botCenterX;
      const dy = e.clientY - botCenterY;
      const angle = Math.atan2(dy, dx);
      const maxMove = size * 0.06;

      const eyeX = Math.cos(angle) * maxMove;
      const eyeY = Math.sin(angle) * maxMove;

      if (leftEyeRef.current) {
        leftEyeRef.current.style.transform = `translate(${eyeX}px, ${eyeY}px)`;
      }
      if (rightEyeRef.current) {
        rightEyeRef.current.style.transform = `translate(${eyeX}px, ${eyeY}px)`;
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, [size]);

  const s = size;
  
  // Hover effect gets priority for laughing
  const currentExpression = isHovered ? 'laugh' : expression;

  return (
    <div 
      className={`ai-bot bot-${currentExpression}`} 
      ref={botRef} 
      style={{ width: s, height: s, cursor: 'pointer' }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Head */}
      <div className="bot-head">
        {/* Antenna */}
        <div className="bot-antenna">
          <div className="bot-antenna-ball"></div>
        </div>
        {/* Ears */}
        <div className="bot-ear bot-ear-left"></div>
        <div className="bot-ear bot-ear-right"></div>
        {/* Face */}
        <div className="bot-face">
          {/* Eyes */}
          <div className="bot-eye bot-eye-left">
            <div className="bot-pupil" ref={leftEyeRef}></div>
          </div>
          <div className="bot-eye bot-eye-right">
            <div className="bot-pupil" ref={rightEyeRef}></div>
          </div>
          {/* Mouth */}
          <div className="bot-mouth"></div>
        </div>
      </div>
    </div>
  );
}
