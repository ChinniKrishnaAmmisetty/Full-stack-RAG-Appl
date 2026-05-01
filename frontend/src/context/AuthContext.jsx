import { createContext, useContext, useState, useEffect } from 'react';
import { clearStoredToken, getMe, getStoredToken, pingBackend, setStoredToken } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (import.meta.env.DEV) {
      pingBackend()
        .then((res) => {
          console.info('[auth] backend reachable', {
            status: res.status,
            requestId: res.headers['x-request-id'],
          });
        })
        .catch((error) => {
          console.error('[auth] backend ping failed', {
            message: error.message,
            status: error.response?.status,
          });
        });
    }

    const token = getStoredToken();
    if (token) {
      getMe(token)
        .then((res) => setUser(res.data))
        .catch(() => {
          clearStoredToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (token) => {
    setStoredToken(token);

    try {
      const response = await getMe(token);
      setUser(response.data);
      return response.data;
    } catch (error) {
      clearStoredToken();
      setUser(null);
      throw error;
    }
  };

  const logout = () => {
    clearStoredToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
