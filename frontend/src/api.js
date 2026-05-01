import axios from 'axios';

const TOKEN_STORAGE_KEY = 'token';
const explicitApiOrigin = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
const fallbackApiOrigin = 'http://127.0.0.1:8000';
const API_ORIGIN = import.meta.env.DEV ? explicitApiOrigin : (explicitApiOrigin || fallbackApiOrigin);
const API_BASE_URL = API_ORIGIN ? `${API_ORIGIN}/api` : '/api';
const buildApiUrl = (path) => `${API_BASE_URL}${path}`;

console.info('[api] configured', {
  dev: import.meta.env.DEV,
  apiBaseUrl: API_BASE_URL,
});

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

export const getStoredToken = () => localStorage.getItem(TOKEN_STORAGE_KEY);

export const setStoredToken = (token) => {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
};

export const clearStoredToken = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
};

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (!config.headers?.Authorization && token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  console.info('[api] request', {
    method: config.method,
    url: `${config.baseURL || ''}${config.url || ''}`,
  });
  return config;
});

// Handle 401 errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[api] response error', {
      status: error.response?.status,
      url: `${error.config?.baseURL || ''}${error.config?.url || ''}`,
      message: error.message,
    });
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      clearStoredToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth API ──
export const registerUser = (data) => api.post('/auth/register', data);
export const loginUser = (data) => api.post('/auth/login', data);
export const getMe = (token) =>
  api.get('/auth/me', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
export const forgotPassword = (data) => api.post('/auth/forgot-password', data);
export const resetPassword = (data) => api.post('/auth/reset-password', data);
export const pingBackend = () => api.get('/health');

// ── Document API ──
export const uploadDocument = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getDocuments = () => api.get('/documents/');
export const deleteDocument = (id) => api.delete(`/documents/${id}`);

// ── Chat API ──
export const createSession = (title) => api.post('/chat/sessions', { title });
export const getSessions = () => api.get('/chat/sessions');
export const getMessages = (sessionId) => api.get(`/chat/sessions/${sessionId}/messages`);
export const sendMessage = (sessionId, content, mode) =>
  api.post(`/chat/sessions/${sessionId}/messages`, { content, mode });
export const deleteSession = (sessionId) => api.delete(`/chat/sessions/${sessionId}`);

/**
 * Stream a message response via SSE.
 * @param {string} sessionId
 * @param {string} content
 * @param {(chunk: string) => void} onChunk - called with each text chunk as it arrives
 * @param {(userMsg: object) => void} onUserMessage - called with the saved user message
 * @param {(sources: array) => void} onSources - called when document matching sources are received
 * @param {(mode: string) => void} onMode - called when the auto mode is detected
 * @param {(status: object) => void} onStatus - called when stream progress updates are emitted
 */
export const streamMessage = async (
  sessionId,
  content,
  mode,
  { onChunk, onUserMessage, onDone, onError, onSources, onMode, onStatus }
) => {
  const token = getStoredToken();
  try {
    const streamUrl = buildApiUrl(`/chat/sessions/${sessionId}/messages/stream`);
    console.info('[api] stream request', { sessionId, streamUrl });
    const response = await fetch(streamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content, mode }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        clearStoredToken();
        window.location.href = '/login';
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: [SOURCES] ')) {
          try {
            const jsonStr = line.replace('data: [SOURCES] ', '');
            const parsed = JSON.parse(jsonStr);
            if (onSources) onSources(parsed.sources);
          } catch (parseErr) {
            console.error("Failed to parse sources", parseErr);
          }
          continue;
        }

        if (line.startsWith('data: [MODE] ')) {
          try {
            const jsonStr = line.replace('data: [MODE] ', '');
            const parsed = JSON.parse(jsonStr);
            if (onMode) onMode(parsed.mode);
          } catch (parseErr) {
            console.error("Failed to parse mode", parseErr);
          }
          continue;
        }

        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            const normalizedStatus = event.type === 'status'
              ? {
                stage: event.stage || event.data?.stage,
                step: event.step || event.data?.step || event.label || event.data?.label,
                detail: event.detail || event.data?.detail || '',
              }
              : null;
            if (event.type === 'user_message' && onUserMessage) {
              onUserMessage(event.data);
            } else if (event.type === 'chunk' && onChunk) {
              onChunk(event.data);
            } else if (event.type === 'status' && onStatus) {
              onStatus(normalizedStatus);
            } else if (event.type === 'done' && onDone) {
              onDone(event.data);
            }
          } catch (parseErr) {
            // skip malformed SSE lines
          }
        }
      }
    }
  } catch (err) {
    console.error('Chat stream request failed', {
      message: err?.message,
      apiBaseUrl: API_BASE_URL,
      sessionId,
    });
    if (onError) onError(err);
  }
};

export default api;
