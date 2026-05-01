import { useEffect, useRef } from 'react';
import { FiMic, FiSend } from 'react-icons/fi';

export default function InputBox({
  input,
  setInput,
  onSubmit,
  disabled,
  hasReadyDocs,
  processingLabel,
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
  }, [input]);

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  const startVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      window.alert('Voice input is not supported in this browser.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInput((currentValue) => (currentValue ? `${currentValue} ${transcript}` : transcript));
    };
    recognition.start();
  };

  return (
    <div className="input-box">
      {disabled && <div className="thinking-indicator">{processingLabel || 'Working in background'}</div>}

      <div className="input-row">
        <textarea
          ref={textareaRef}
          id="chat-input"
          placeholder={
            hasReadyDocs
              ? 'Ask a question from your uploaded documents.'
              : 'Upload documents to begin asking questions.'
          }
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />

        <button
          type="button"
          className="input-icon-btn"
          onClick={startVoiceInput}
          disabled={disabled}
          title="Voice input"
        >
          <FiMic />
        </button>

        <button
          type="button"
          className="send-btn"
          onClick={onSubmit}
          disabled={disabled || !input.trim()}
          id="send-btn"
          title="Send"
        >
          <FiSend />
        </button>
      </div>
    </div>
  );
}
