import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiClock, FiFileText, FiMenu, FiMessageSquare, FiRefreshCw, FiUploadCloud, FiX } from 'react-icons/fi';
import { getDocuments, getMessages, getSessions } from '../api';
import SettingsModal from '../components/SettingsModal';
import Sidebar from '../components/Sidebar';
import { useAuth } from '../context/AuthContext';

const getDefaultSidebarState = () => (typeof window === 'undefined' ? true : window.innerWidth >= 960);
const hourFormatter = new Intl.DateTimeFormat(undefined, { hour: 'numeric' });
const monthFormatter = new Intl.DateTimeFormat(undefined, { month: 'short' });

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const clampPercentage = (value) => Math.max(0, Math.min(100, Math.round(value)));

const formatRelativeTime = (timestamp) => {
  if (!timestamp) return 'No activity';

  const target = new Date(timestamp).getTime();
  const now = Date.now();
  const diffMs = now - target;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diffMs < hour) {
    const minutes = Math.max(1, Math.round(diffMs / minute));
    return `${minutes}m ago`;
  }

  if (diffMs < day) {
    return `${Math.round(diffMs / hour)}h ago`;
  }

  return `${Math.round(diffMs / day)}d ago`;
};

const createLastTwelveHourSeries = (messages) => {
  const now = new Date();
  const rangeStart = new Date(now);
  rangeStart.setMinutes(0, 0, 0);
  rangeStart.setHours(rangeStart.getHours() - 11);

  const series = Array.from({ length: 12 }, (_, index) => {
    const slotTime = new Date(rangeStart);
    slotTime.setHours(rangeStart.getHours() + index);
    return {
      key: slotTime.toISOString(),
      label: hourFormatter.format(slotTime),
      count: 0,
    };
  });

  messages
    .filter((message) => message.role === 'user')
    .forEach((message) => {
      const messageDate = new Date(message.created_at);
      const hourOffset = Math.floor((messageDate.getTime() - rangeStart.getTime()) / (60 * 60 * 1000));
      if (hourOffset >= 0 && hourOffset < series.length) {
        series[hourOffset].count += 1;
      }
    });

  return series;
};

const createMonthlySeries = (messages) => {
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth() - 5, 1);

  const series = Array.from({ length: 6 }, (_, index) => {
    const slotDate = new Date(start.getFullYear(), start.getMonth() + index, 1);
    return {
      key: `${slotDate.getFullYear()}-${slotDate.getMonth()}`,
      label: monthFormatter.format(slotDate),
      user: 0,
      assistant: 0,
    };
  });

  messages.forEach((message) => {
    const messageDate = new Date(message.created_at);
    const monthOffset = (messageDate.getFullYear() - start.getFullYear()) * 12 + (messageDate.getMonth() - start.getMonth());
    if (monthOffset >= 0 && monthOffset < series.length) {
      if (message.role === 'user') {
        series[monthOffset].user += 1;
      }
      if (message.role === 'assistant') {
        series[monthOffset].assistant += 1;
      }
    }
  });

  return series;
};

const buildRecentActivity = (documents, sessionDetails) => {
  const documentEvents = documents.map((document) => ({
    id: `document-${document.id}`,
    title: document.filename,
    subtitle: `Uploaded ${document.file_type.toUpperCase()} | ${formatSize(document.file_size)}`,
    time: document.created_at,
    kind: 'Document',
  }));

  const messageEvents = sessionDetails.flatMap((session) => {
    const latestMessage = session.messages[session.messages.length - 1];
    if (!latestMessage) {
      return [];
    }

    return [{
      id: `session-${session.id}`,
      title: session.title,
      subtitle: latestMessage.content.slice(0, 72) || 'Conversation updated',
      time: latestMessage.created_at,
      kind: latestMessage.role === 'assistant' ? 'Answer' : 'Question',
    }];
  });

  return [...documentEvents, ...messageEvents]
    .sort((left, right) => new Date(right.time) - new Date(left.time))
    .slice(0, 6);
};

function SummaryCard({ label, value, detail }) {
  return (
    <div className="dashboard-summary-card">
      <span className="dashboard-summary-label">{label}</span>
      <strong className="dashboard-summary-value">{value}</strong>
      <span className="dashboard-summary-detail">{detail}</span>
    </div>
  );
}

function HourlyActivityCard({ series, totalPrompts }) {
  const maxCount = Math.max(...series.map((slot) => slot.count), 1);

  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Conversation activity</h2>
          <p>User prompts in the last 12 hours.</p>
        </div>
        <span className="dashboard-card-badge">{totalPrompts}</span>
      </div>

      <div className="dashboard-mini-chart">
        {series.map((slot) => (
          <div key={slot.key} className="dashboard-mini-column">
            <span className="dashboard-mini-value">{slot.count}</span>
            <div className="dashboard-mini-track">
              <div
                className="dashboard-mini-fill"
                style={{ height: `${Math.max((slot.count / maxCount) * 100, slot.count > 0 ? 10 : 0)}%` }}
              />
            </div>
            <span className="dashboard-mini-label">{slot.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentSessionsCard({ sessionDetails }) {
  const recentSessions = [...sessionDetails]
    .map((session) => {
      const latestMessage = session.messages[session.messages.length - 1] || null;
      return {
        ...session,
        latestMessage,
        totalMessages: session.messages.length,
        assistantMessages: session.messages.filter((message) => message.role === 'assistant').length,
      };
    })
    .sort((left, right) => {
      const leftTime = left.latestMessage?.created_at || left.created_at;
      const rightTime = right.latestMessage?.created_at || right.created_at;
      return new Date(rightTime) - new Date(leftTime);
    })
    .slice(0, 4);

  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Recent conversations</h2>
          <p>Latest active sessions with real message counts.</p>
        </div>
      </div>

      {recentSessions.length === 0 ? (
        <div className="dashboard-empty">No chat sessions yet.</div>
      ) : (
        <div className="dashboard-list">
          {recentSessions.map((session) => {
            const latestTimestamp = session.latestMessage?.created_at || session.created_at;
            const statusLabel = Date.now() - new Date(latestTimestamp).getTime() < 24 * 60 * 60 * 1000 ? 'Active' : 'Idle';

            return (
              <div key={session.id} className="dashboard-list-item">
                <div className="dashboard-list-copy">
                  <strong>{session.title}</strong>
                  <span>{session.latestMessage?.content?.slice(0, 68) || 'Conversation created'}</span>
                </div>
                <div className="dashboard-list-meta">
                  <span className={`dashboard-status-pill ${statusLabel.toLowerCase()}`}>{statusLabel}</span>
                  <span>{session.totalMessages} msgs</span>
                  <span>{formatRelativeTime(latestTimestamp)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function CoverageCard({ answeredPrompts, pendingPrompts, userPromptCount, assistantCount, averageMessagesPerSession }) {
  const coverage = userPromptCount ? clampPercentage((answeredPrompts / userPromptCount) * 100) : 0;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (coverage / 100) * circumference;

  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Response coverage</h2>
          <p>Answered versus pending user prompts.</p>
        </div>
      </div>

      <div className="dashboard-coverage">
        <div className="dashboard-ring">
          <svg viewBox="0 0 120 120" className="dashboard-ring-svg" aria-label="Response coverage">
            <circle className="dashboard-ring-track" cx="60" cy="60" r={radius} />
            <circle
              className="dashboard-ring-progress"
              cx="60"
              cy="60"
              r={radius}
              style={{
                strokeDasharray: circumference,
                strokeDashoffset: dashOffset,
              }}
            />
          </svg>
          <div className="dashboard-ring-text">
            <strong>{coverage}%</strong>
            <span>Answered</span>
          </div>
        </div>

        <div className="dashboard-metric-stack">
          <div className="dashboard-metric-row"><span>Answered prompts</span><strong>{answeredPrompts}</strong></div>
          <div className="dashboard-metric-row"><span>Pending prompts</span><strong>{pendingPrompts}</strong></div>
          <div className="dashboard-metric-row"><span>Assistant replies</span><strong>{assistantCount}</strong></div>
          <div className="dashboard-metric-row"><span>Avg msgs / session</span><strong>{averageMessagesPerSession}</strong></div>
        </div>
      </div>
    </section>
  );
}

function KnowledgeBaseCard({ documents, readyCount, processingCount, totalChunks, totalSize }) {
  const readiness = documents.length ? clampPercentage((readyCount / documents.length) * 100) : 0;
  const formats = Object.entries(
    documents.reduce((accumulator, document) => {
      const nextKey = document.file_type.toUpperCase();
      accumulator[nextKey] = (accumulator[nextKey] || 0) + 1;
      return accumulator;
    }, {})
  ).sort((left, right) => right[1] - left[1]);

  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Knowledge base</h2>
          <p>Exact document and indexing status from the workspace.</p>
        </div>
        <span className="dashboard-card-badge">{readiness}% ready</span>
      </div>

      <div className="dashboard-metric-stack">
        <div className="dashboard-metric-row"><span>Total documents</span><strong>{documents.length}</strong></div>
        <div className="dashboard-metric-row"><span>Ready documents</span><strong>{readyCount}</strong></div>
        <div className="dashboard-metric-row"><span>Processing</span><strong>{processingCount}</strong></div>
        <div className="dashboard-metric-row"><span>Indexed chunks</span><strong>{totalChunks}</strong></div>
        <div className="dashboard-metric-row"><span>Storage used</span><strong>{formatSize(totalSize)}</strong></div>
      </div>

      {formats.length > 0 && (
        <div className="dashboard-tag-row">
          {formats.slice(0, 4).map(([format, count]) => (
            <span key={format} className="dashboard-tag">{format} x {count}</span>
          ))}
        </div>
      )}
    </section>
  );
}

function ResponseChartCard({ monthlySeries }) {
  const maxValue = Math.max(
    ...monthlySeries.flatMap((month) => [month.user, month.assistant]),
    1
  );

  return (
    <section className="dashboard-card dashboard-wide-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Responses over time</h2>
          <p>User prompts and assistant replies for the last six months.</p>
        </div>
        <div className="dashboard-legend">
          <span><i className="legend-dot answered" />Assistant</span>
          <span><i className="legend-dot unanswered" />User</span>
        </div>
      </div>

      <div className="dashboard-response-chart">
        {monthlySeries.map((month) => (
          <div key={month.key} className="dashboard-response-group">
            <div className="dashboard-response-bars">
              <div className="dashboard-response-track">
                <div
                  className="dashboard-response-bar user"
                  style={{ height: `${(month.user / maxValue) * 100}%` }}
                />
              </div>
              <div className="dashboard-response-track">
                <div
                  className="dashboard-response-bar assistant"
                  style={{ height: `${(month.assistant / maxValue) * 100}%` }}
                />
              </div>
            </div>
            <div className="dashboard-response-values">
              <span>{month.user}</span>
              <span>{month.assistant}</span>
            </div>
            <span className="dashboard-response-label">{month.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentActivityCard({ activity }) {
  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <div>
          <h2>Recent activity</h2>
          <p>Latest uploads and chat events.</p>
        </div>
      </div>

      {activity.length === 0 ? (
        <div className="dashboard-empty">No recent activity available.</div>
      ) : (
        <div className="dashboard-list">
          {activity.map((item) => (
            <div key={item.id} className="dashboard-list-item">
              <div className="dashboard-list-copy">
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </div>
              <div className="dashboard-list-meta">
                <span className="dashboard-type-label">{item.kind}</span>
                <span>{formatRelativeTime(item.time)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(getDefaultSidebarState);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [sessionDetails, setSessionDetails] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const loadOverview = async () => {
      setLoading(true);

      try {
        const [documentsResponse, sessionsResponse] = await Promise.all([
          getDocuments(),
          getSessions(),
        ]);

        const nextDocuments = documentsResponse.data;
        const nextSessions = sessionsResponse.data;
        const nextSessionDetails = await Promise.all(
          nextSessions.map(async (session) => {
            try {
              const response = await getMessages(session.id);
              return { ...session, messages: response.data };
            } catch (error) {
              console.error(`Failed to load messages for session ${session.id}:`, error);
              return { ...session, messages: [] };
            }
          })
        );

        if (!isMounted) return;

        setDocuments(nextDocuments);
        setSessions(nextSessions);
        setSessionDetails(nextSessionDetails);
      } catch (error) {
        console.error('Failed to load dashboard overview:', error);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadOverview();
    return () => {
      isMounted = false;
    };
  }, []);

  const allMessages = sessionDetails.flatMap((session) =>
    session.messages.map((message) => ({
      ...message,
      sessionId: session.id,
      sessionTitle: session.title,
    }))
  );

  const userMessages = allMessages.filter((message) => message.role === 'user');
  const assistantMessages = allMessages.filter((message) => message.role === 'assistant');
  const readyCount = documents.filter((document) => document.status === 'ready').length;
  const processingCount = documents.filter((document) => document.status === 'processing').length;
  const totalChunks = documents.reduce((sum, document) => sum + (document.chunk_count || 0), 0);
  const totalSize = documents.reduce((sum, document) => sum + (document.file_size || 0), 0);
  const answeredPrompts = Math.min(userMessages.length, assistantMessages.length);
  const pendingPrompts = Math.max(userMessages.length - assistantMessages.length, 0);
  const averageMessagesPerSession = sessions.length ? (allMessages.length / sessions.length).toFixed(1) : '0.0';
  const lastTwelveHourSeries = createLastTwelveHourSeries(allMessages);
  const monthlySeries = createMonthlySeries(allMessages);
  const recentActivity = buildRecentActivity(documents, sessionDetails);

  return (
    <div className="chat-layout">
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen((current) => !current)}>
        {sidebarOpen ? <FiX /> : <FiMenu />}
      </button>

      <Sidebar
        isOpen={sidebarOpen}
        user={user}
        onOpenSettings={() => setSettingsOpen(true)}
        sessions={sessions}
        documents={documents}
        onNavigate={() => {
          if (typeof window !== 'undefined' && window.innerWidth < 960) {
            setSidebarOpen(false);
          }
        }}
      />

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

      <main className="workspace-main">
        <div className="workspace-scroll">
          <section className="page-panel">
            <header className="page-header dashboard-header">
              <div className="page-title-group">
                <span className="page-kicker">Dashboard</span>
                <h1>AI Chatbot</h1>
                <p>Live workspace metrics built from your actual documents, sessions, and chat history.</p>
              </div>

              <div className="page-actions">
                <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>
                  <FiRefreshCw /> Refresh
                </button>
                <button type="button" className="btn-secondary" onClick={() => navigate('/documents')}>
                  <FiUploadCloud /> Data sources
                </button>
                <button type="button" className="btn-primary" onClick={() => navigate('/chat')}>
                  <FiMessageSquare /> Open chat
                </button>
              </div>
            </header>

            <div className="dashboard-summary-grid">
              <SummaryCard
                label="Total sessions"
                value={loading ? '--' : sessions.length}
                detail="Conversation threads"
              />
              <SummaryCard
                label="Total messages"
                value={loading ? '--' : allMessages.length}
                detail="User and assistant messages"
              />
              <SummaryCard
                label="Answered prompts"
                value={loading ? '--' : answeredPrompts}
                detail={`${pendingPrompts} pending`}
              />
              <SummaryCard
                label="Ready documents"
                value={loading ? '--' : readyCount}
                detail={`${totalChunks} indexed chunks`}
              />
            </div>

            <div className="dashboard-grid">
              <HourlyActivityCard
                series={lastTwelveHourSeries}
                totalPrompts={userMessages.filter((message) => {
                  const hoursAgo = (Date.now() - new Date(message.created_at).getTime()) / (60 * 60 * 1000);
                  return hoursAgo <= 12;
                }).length}
              />
              <RecentSessionsCard sessionDetails={sessionDetails} />
              <CoverageCard
                answeredPrompts={answeredPrompts}
                pendingPrompts={pendingPrompts}
                userPromptCount={userMessages.length}
                assistantCount={assistantMessages.length}
                averageMessagesPerSession={averageMessagesPerSession}
              />
              <KnowledgeBaseCard
                documents={documents}
                readyCount={readyCount}
                processingCount={processingCount}
                totalChunks={totalChunks}
                totalSize={totalSize}
              />
              <ResponseChartCard monthlySeries={monthlySeries} />
              <RecentActivityCard activity={recentActivity} />
            </div>

            {loading && (
              <div className="dashboard-loading-note">
                <FiClock />
                <span>Loading live dashboard values...</span>
              </div>
            )}

            {!loading && documents.length === 0 && sessions.length === 0 && (
              <div className="dashboard-loading-note">
                <FiFileText />
                <span>Upload documents and start a chat to populate the dashboard.</span>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
