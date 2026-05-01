import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiBarChart2, FiMenu, FiTrash2, FiUploadCloud, FiX } from 'react-icons/fi';
import { createSession, deleteSession, getDocuments, getMessages, getSessions, streamMessage } from '../api';
import AnalyticsPanel from '../components/AnalyticsPanel';
import ChatMessage from '../components/ChatMessage';
import InputBox from '../components/InputBox';
import SettingsModal from '../components/SettingsModal';
import Sidebar from '../components/Sidebar';
import { useAuth } from '../context/AuthContext';

const getDefaultSidebarState = () => (typeof window === 'undefined' ? true : window.innerWidth >= 960);
const getDefaultAnalyticsState = () => (typeof window === 'undefined' ? true : window.innerWidth >= 1280);
const STATUS_ORDER = ['queued', 'embedding', 'retrieving', 'matching', 'generating'];
const STATUS_TEMPLATE = {
  queued: {
    stage: 'queued',
    step: 'Preparing request',
    detail: 'Sending your question into the retrieval pipeline.',
  },
  embedding: {
    stage: 'embedding',
    step: 'Building query embedding',
    detail: 'Converting your question for retrieval.',
  },
  retrieving: {
    stage: 'retrieving',
    step: 'Running hybrid search',
    detail: 'Searching vector and keyword candidates in your documents.',
  },
  matching: {
    stage: 'matching',
    step: 'Extracting matching chunks',
    detail: 'Selecting the best evidence from retrieved results.',
  },
  generating: {
    stage: 'generating',
    step: 'Generating grounded answer',
    detail: 'Writing the response from the matched chunks.',
  },
};

const mergeStatusSteps = (currentSteps = [], incomingStatus) => {
  const incomingStage = incomingStatus.stage || 'generating';
  const incomingIndex = STATUS_ORDER.indexOf(incomingStage);
  const stageMap = new Map(currentSteps.map((step) => [step.stage, step]));
  const previousStep = stageMap.get(incomingStage) || STATUS_TEMPLATE[incomingStage] || { stage: incomingStage };

  stageMap.set(incomingStage, {
    ...previousStep,
    ...incomingStatus,
    step: incomingStatus.step || previousStep.step,
  });

  return Array.from(stageMap.values())
    .sort((left, right) => STATUS_ORDER.indexOf(left.stage) - STATUS_ORDER.indexOf(right.stage))
    .map((step) => {
      const stepIndex = STATUS_ORDER.indexOf(step.stage);
      let state = step.state || 'pending';

      if (incomingIndex >= 0 && stepIndex >= 0) {
        if (stepIndex < incomingIndex) {
          state = 'complete';
        } else if (stepIndex === incomingIndex) {
          state = 'active';
        } else {
          state = 'pending';
        }
      } else if (step.stage === incomingStage) {
        state = 'active';
      }

      return { ...step, state };
    });
};

export default function ChatPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(getDefaultSidebarState);
  const [documents, setDocuments] = useState([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sources, setSources] = useState([]);
  const [showAnalytics, setShowAnalytics] = useState(getDefaultAnalyticsState);
  const [responseTimes, setResponseTimes] = useState([]);
  const [streamStatusLabel, setStreamStatusLabel] = useState('');
  const messagesEndRef = useRef(null);

  const currentSession = sessions.find((session) => session.id === activeSessionId) || null;
  const readyDocs = documents.filter((document) => document.status === 'ready');
  const hasReadyDocs = readyDocs.length > 0;
  const averageResponseTimeMs = responseTimes.length
    ? responseTimes.reduce((sum, value) => sum + value, 0) / responseTimes.length
    : null;

  const loadSessions = async () => {
    try {
      const response = await getSessions();
      setSessions(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const loadMessages = async (sessionId) => {
    try {
      const response = await getMessages(sessionId);
      setMessages(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const loadDocuments = async () => {
    try {
      const response = await getDocuments();
      setDocuments(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    loadSessions();
    loadDocuments();
  }, []);

  useEffect(() => {
    if (!documents.some((document) => document.status === 'processing')) {
      return undefined;
    }

    const interval = window.setInterval(loadDocuments, 5000);
    return () => window.clearInterval(interval);
  }, [documents]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }

    if (!sending) {
      loadMessages(activeSessionId);
    }
  }, [activeSessionId, sending]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sources, streamStatusLabel]);

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setSources([]);
    setInput('');
    setStreamStatusLabel('');
    if (typeof window !== 'undefined' && window.innerWidth < 960) {
      setSidebarOpen(false);
    }
  };

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!content || sending) return;

    const requestStartedAt = performance.now();
    setInput('');

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const response = await createSession(content.slice(0, 50));
        sessionId = response.data.id;
        setSessions((previousSessions) => [response.data, ...previousSessions]);
        setActiveSessionId(sessionId);
      } catch (error) {
        console.error(error);
        return;
      }
    }

    const tempUserId = `temp-u-${Date.now()}`;
    const tempAssistantId = `temp-a-${Date.now()}`;

    setMessages((previousMessages) => [
      ...previousMessages,
      { id: tempUserId, role: 'user', content, created_at: new Date().toISOString() },
      {
        id: tempAssistantId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        loading: true,
        statusSteps: [],
      },
    ]);

    setSending(true);
    setSources([]);
    setStreamStatusLabel('');

    try {
      await streamMessage(sessionId, content, null, {
        onUserMessage: (savedMessage) => {
          setMessages((previousMessages) => previousMessages.map((message) => (
            message.id === tempUserId ? { ...savedMessage } : message
          )));
        },
        onChunk: (chunk) => {
          setMessages((previousMessages) => previousMessages.map((message) => (
            message.id === tempAssistantId
              ? { ...message, content: `${message.content}${chunk}`, loading: true }
              : message
          )));
        },
        onStatus: (statusUpdate) => {
          setStreamStatusLabel(statusUpdate.step || 'Working in background');
          setMessages((previousMessages) => previousMessages.map((message) => (
            message.id === tempAssistantId
              ? {
                ...message,
                loading: true,
                statusSteps: mergeStatusSteps(message.statusSteps, statusUpdate),
              }
              : message
          )));
        },
        onDone: (savedMessage) => {
          setMessages((previousMessages) => previousMessages.map((message) => (
            message.id === tempAssistantId ? { ...savedMessage, loading: false } : message
          )));
          setResponseTimes((previousTimes) => [...previousTimes, performance.now() - requestStartedAt]);
          setStreamStatusLabel('');
          loadSessions();
        },
        onSources: (nextSources) => setSources(nextSources),
        onMode: () => {},
        onError: () => {
          setStreamStatusLabel('');
          setMessages((previousMessages) => previousMessages.map((message) => (
            message.id === tempAssistantId
              ? { ...message, content: 'Something went wrong. Please try again.', loading: false }
              : message
          )));
        },
      });
    } catch {
      setMessages((previousMessages) => previousMessages.map((message) => (
        message.id === tempAssistantId
          ? { ...message, content: 'Something went wrong. Please try again.', loading: false }
          : message
      )));
      setStreamStatusLabel('');
    } finally {
      setSending(false);
    }
  }, [activeSessionId, input, sending]);

  const handleDeleteSession = async (sessionId) => {
    try {
      await deleteSession(sessionId);
      const remainingSessions = sessions.filter((session) => session.id !== sessionId);
      setSessions(remainingSessions);

      if (activeSessionId === sessionId) {
        setActiveSessionId(remainingSessions[0]?.id ?? null);
        setMessages([]);
        setSources([]);
        setStreamStatusLabel('');
      }
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="app-layout" id="chat-page">
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen((current) => !current)}>
        {sidebarOpen ? <FiX /> : <FiMenu />}
      </button>

      <Sidebar
        isOpen={sidebarOpen}
        user={user}
        onOpenSettings={() => setSettingsOpen(true)}
        onCreateSession={handleNewChat}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={(sessionId) => {
          setActiveSessionId(sessionId);
          setSources([]);
          if (typeof window !== 'undefined' && window.innerWidth < 960) {
            setSidebarOpen(false);
          }
        }}
        onDeleteSession={handleDeleteSession}
        documents={documents}
        onNavigate={() => {
          if (typeof window !== 'undefined' && window.innerWidth < 960) {
            setSidebarOpen(false);
          }
        }}
      />

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

      <main className="chat-main">
        <header className="chat-header">
          <div className="chat-title-group">
            <h1>{currentSession?.title || 'AI Chatbot'}</h1>
            <p>
              {hasReadyDocs
                ? `${readyDocs.length} document${readyDocs.length === 1 ? '' : 's'} ready for grounded answers`
                : 'Upload documents to begin grounded conversations'}
            </p>
          </div>

          <div className="header-actions">
            <button className="header-btn" onClick={() => navigate('/documents')}>
              <FiUploadCloud /> Documents
            </button>
            <button className="header-btn" onClick={() => setShowAnalytics((current) => !current)}>
              <FiBarChart2 /> {showAnalytics ? 'Hide panel' : 'Show panel'}
            </button>
            {activeSessionId && (
              <button className="header-btn header-btn-danger" onClick={() => handleDeleteSession(activeSessionId)}>
                <FiTrash2 /> Delete
              </button>
            )}
          </div>
        </header>

        <div className="chat-shell">
          <section className="messages-panel">
            <div className="messages-area">
              {messages.length === 0 ? (
                <div className="empty-chat">
                  <h2>Start a conversation</h2>
                  <p>Ask a question from your uploaded documents.</p>
                </div>
              ) : (
                <div className="messages-list">
                  {messages.map((message, index) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      sources={index === messages.length - 1 && message.role === 'assistant' ? sources : []}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <InputBox
              input={input}
              setInput={setInput}
              onSubmit={handleSend}
              disabled={sending}
              hasReadyDocs={hasReadyDocs}
              processingLabel={streamStatusLabel}
            />
          </section>

          {showAnalytics && (
            <AnalyticsPanel
              sessions={sessions}
              messages={messages}
              sources={sources}
              onClose={() => setShowAnalytics(false)}
              averageResponseTimeMs={averageResponseTimeMs}
              rerankerUsed={null}
            />
          )}
        </div>
      </main>
    </div>
  );
}
