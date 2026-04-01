import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth API ──
export const registerUser = (data) => api.post('/auth/register', data);
export const loginUser = (data) => api.post('/auth/login', data);
export const getMe = () => api.get('/auth/me');
export const forgotPassword = (data) => api.post('/auth/forgot-password', data);
export const resetPassword = (data) => api.post('/auth/reset-password', data);

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
export const sendMessage = (sessionId, content) =>
  api.post(`/chat/sessions/${sessionId}/messages`, { content });
export const deleteSession = (sessionId) => api.delete(`/chat/sessions/${sessionId}`);

/**
 * Stream a message response via SSE.
 * @param {string} sessionId
 * @param {string} content
 * @param {(chunk: string) => void} onChunk - called with each text chunk as it arrives
 * @param {(userMsg: object) => void} onUserMessage - called with the saved user message
 * @param {(assistantMsg: object) => void} onDone - called when the full response is complete
 * @param {(error: Error) => void} onError
 */
export const streamMessage = async (sessionId, content, { onChunk, onUserMessage, onDone, onError }) => {
  const token = localStorage.getItem('token');
  try {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('token');
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
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'user_message' && onUserMessage) {
              onUserMessage(event.data);
            } else if (event.type === 'chunk' && onChunk) {
              onChunk(event.data);
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
    if (onError) onError(err);
  }
};

export default api;
