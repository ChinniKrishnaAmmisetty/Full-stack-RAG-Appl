import { useState } from 'react';
import { FiSend } from 'react-icons/fi';

export default function ChatInput({ onSend, disabled }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="chat-input-form" onSubmit={handleSubmit} id="chat-input-form">
      <div className="chat-input-wrapper">
        <textarea
          id="chat-input"
          className="chat-input"
          placeholder="Ask a question about your documents..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <button
          type="submit"
          className="send-btn"
          disabled={disabled || !input.trim()}
          id="send-btn"
          title="Send message"
        >
          <FiSend />
        </button>
      </div>
      <p className="input-hint">Answers are generated based on your uploaded documents only.</p>
    </form>
  );
}
