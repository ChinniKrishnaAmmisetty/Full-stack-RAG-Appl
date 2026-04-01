import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { getSessions, createSession, getMessages, sendMessage, streamMessage, deleteSession, uploadDocument, getDocuments, deleteDocument } from '../api';
import Sidebar from '../components/Sidebar';
import ChatMessage from '../components/ChatMessage';
import SettingsModal from '../components/SettingsModal';
import AiBot from '../components/AiBot';
import { FiMenu, FiX, FiSend, FiPaperclip, FiFile, FiCheckCircle, FiLoader, FiAlertCircle, FiTrash2 } from 'react-icons/fi';

export default function ChatPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  // Typing effect for welcome text
  const fullWelcomeText = "Welcome to ACK AI";
  const [welcomeText, setWelcomeText] = useState("");

  useEffect(() => {
    if (messages.length === 0) {
      setWelcomeText("");
      let i = 0;
      const typeInterval = setInterval(() => {
        if (i < fullWelcomeText.length) {
          setWelcomeText(fullWelcomeText.substring(0, i + 1));
          i++;
        } else {
          clearInterval(typeInterval);
        }
      }, 100);
      return () => clearInterval(typeInterval);
    }
  }, [messages.length]);

  useEffect(() => { loadSessions(); loadDocuments(); }, []);

  // Poll documents every 5s while any are processing
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'processing');
    if (!hasProcessing) return;
    const interval = setInterval(loadDocuments, 5000);
    return () => clearInterval(interval);
  }, [documents]);

  useEffect(() => {
    if (activeSessionId && !sending) loadMessages(activeSessionId);
    else if (!activeSessionId) setMessages([]);
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  const loadSessions = async () => {
    try { const res = await getSessions(); setSessions(res.data); }
    catch (err) { console.error('Failed to load sessions:', err); }
  };

  const loadMessages = async (sessionId) => {
    try { const res = await getMessages(sessionId); setMessages(res.data); }
    catch (err) { console.error('Failed to load messages:', err); }
  };

  const loadDocuments = async () => {
    try { const res = await getDocuments(); setDocuments(res.data); }
    catch (err) { console.error('Failed to load documents:', err); }
  };

  const handleNewChat = () => { setActiveSessionId(null); setMessages([]); };

  const hasReadyDocs = documents.some((d) => d.status === 'ready');

  const handleSendMessage = useCallback(async (content) => {
    if (!content.trim() || sending) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const res = await createSession(content.slice(0, 50));
        sessionId = res.data.id;
        setSessions((prev) => [res.data, ...prev]);
        setActiveSessionId(sessionId);
      } catch (err) { console.error('Failed to create session:', err); return; }
    }

    const tempUserMsg = { id: 'temp-user-' + Date.now(), role: 'user', content, created_at: new Date().toISOString() };
    const tempAiMsgId = 'temp-ai-' + Date.now();
    const tempAiMsg = { id: tempAiMsgId, role: 'assistant', content: '', created_at: new Date().toISOString(), loading: true };
    setMessages((prev) => [...prev, tempUserMsg, tempAiMsg]);
    setSending(true);

    try {
      await streamMessage(sessionId, content, {
        onUserMessage: (savedUserMsg) => {
          // Replace temp user message with saved one from DB
          setMessages((prev) =>
            prev.map((m) => (m.id === tempUserMsg.id ? { ...savedUserMsg } : m))
          );
        },
        onChunk: (textChunk) => {
          // Append each chunk to the AI message in real-time
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAiMsgId
                ? { ...m, content: m.content + textChunk, loading: true }
                : m
            )
          );
        },
        onDone: (savedAssistantMsg) => {
          // Replace temp AI message with the final saved version
          setMessages((prev) =>
            prev.map((m) => (m.id === tempAiMsgId ? { ...savedAssistantMsg, loading: false } : m))
          );
          loadSessions();
        },
        onError: (err) => {
          console.error('Streaming failed:', err);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAiMsgId
                ? { ...m, content: 'Sorry, something went wrong. Please try again.', loading: false }
                : m
            )
          );
        },
      });
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempAiMsgId
            ? { ...m, content: 'Sorry, something went wrong. Please try again.', loading: false }
            : m
        )
      );
    } finally { setSending(false); }
  }, [activeSessionId, sending]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !sending) {
      handleSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    const allowed = ['pdf', 'docx', 'txt', 'csv', 'xlsx', 'md'];
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!allowed.includes(ext)) { setUploadStatus({ type: 'error', msg: `Only ${allowed.join(', ')} allowed` }); return; }
    if (file.size > 50 * 1024 * 1024) { setUploadStatus({ type: 'error', msg: 'File too large (max 50 MB)' }); return; }

    setUploading(true);
    setUploadStatus({ type: 'info', msg: `Uploading "${file.name}"...` });
    try {
      await uploadDocument(file);
      setUploadStatus({ type: 'success', msg: `"${file.name}" uploaded! Processing...` });
      loadDocuments();
      setTimeout(() => setUploadStatus(null), 5000);
    } catch (err) {
      setUploadStatus({ type: 'error', msg: err.response?.data?.detail || 'Upload failed' });
    } finally { setUploading(false); }
  };

  const handleDeleteDoc = async (docId) => {
    try { await deleteDocument(docId); loadDocuments(); }
    catch (err) { console.error('Failed to delete document:', err); }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) { setActiveSessionId(null); setMessages([]); }
    } catch (err) { console.error('Failed to delete session:', err); }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ready': return <FiCheckCircle className="doc-status ready" />;
      case 'failed': return <FiAlertCircle className="doc-status failed" />;
      default: return <FiLoader className="doc-status processing" />;
    }
  };

  return (
    <div className="chat-layout" id="chat-page">
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)} id="sidebar-toggle">
        {sidebarOpen ? <FiX /> : <FiMenu />}
      </button>

      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onDeleteDocument={handleDeleteDoc}
        isOpen={sidebarOpen}
        user={user}
        documents={documents}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

      <main className="chat-main-area" style={{ background: messages.length === 0 ? '#000000' : 'var(--bg-primary)' }}>
        {/* Upload status toast */}
        {uploadStatus && (
          <div className={`upload-toast ${uploadStatus.type}`}>
            {uploadStatus.msg}
            <button onClick={() => setUploadStatus(null)}>×</button>
          </div>
        )}

        {/* Messages or Welcome */}
        <div className="chat-messages-scroll">
          {messages.length === 0 ? (
            <div className="welcome-container">
              <div className="welcome-hero">
                <div className="bot-mascot-container">
                  <AiBot size={150} expression="happy" />
                </div>
                <h1 style={{ minHeight: '48px' }}>
                   {messages.length === 0 && welcomeText.length > 0 ? (
                     <span>
                       {welcomeText.substring(0, 11)} 
                       <span className="brand-gradient">{welcomeText.substring(11)}</span>
                       <span className="typing-cursor"></span>
                     </span>
                   ) : (
                     <span className="typing-cursor"></span>
                   )}
                </h1>
              </div>

              {/* Grid removed as per user request */}
            </div>
          ) : (
            <div className="chat-messages-list">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="chat-input-area">
          {!hasReadyDocs && documents.length > 0 && (
            <div className="processing-banner">
              <FiLoader className="spin-icon" /> Documents are still processing. Please wait before asking questions.
            </div>
          )}
          {documents.length === 0 && (
            <div className="processing-banner info-banner">
              📄 Upload a document first to start asking questions.
            </div>
          )}
          <div className="chat-input-container">
            <button
              className="attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              title="Upload document"
              id="attach-btn"
            >
              {uploading ? <div className="mini-spinner"></div> : <FiPaperclip />}
            </button>
            <textarea
              ref={textareaRef}
              id="chat-input"
              className="chat-textarea"
              placeholder={hasReadyDocs ? 'Message RAG Assistant...' : 'Upload a document to start chatting...'}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending || !hasReadyDocs}
              rows={1}
            />
            <button
              type="button"
              className={`send-msg-btn ${input.trim() && hasReadyDocs ? 'active' : ''}`}
              onClick={handleSubmit}
              disabled={sending || !input.trim() || !hasReadyDocs}
              id="send-btn"
              title="Send message"
            >
              <FiSend />
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.csv,.xlsx,.md"
            onChange={(e) => { handleFileUpload(e.target.files[0]); e.target.value = ''; }}
            hidden
            id="file-input"
          />
        </div>
      </main>
    </div>
  );
}
