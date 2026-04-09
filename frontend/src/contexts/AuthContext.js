import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

function formatApiErrorDetail(detail) {
  if (detail == null) return "Algo deu errado. Tente novamente.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

// Store token in memory for security
let accessToken = null;

export const getAccessToken = () => accessToken;
export const setAccessToken = (token) => { accessToken = token; };

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // null = checking, false = not auth, object = auth
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // Try to get user from stored token
    const storedUser = localStorage.getItem('pcm_user');
    const storedToken = localStorage.getItem('pcm_token');
    
    if (storedUser && storedToken) {
      try {
        setAccessToken(storedToken);
        const { data } = await axios.get(`${API}/api/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` }
        });
        setUser(data);
        setLoading(false);
        return;
      } catch (e) {
        // Token invalid, clear storage
        localStorage.removeItem('pcm_user');
        localStorage.removeItem('pcm_token');
        setAccessToken(null);
      }
    }
    
    setUser(false);
    setLoading(false);
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    try {
      const { data, headers } = await axios.post(
        `${API}/api/auth/login`,
        { email, password }
      );
      
      // Extract token from response if provided, or use email as fallback identifier
      const token = data.access_token || data.token;
      
      if (token) {
        setAccessToken(token);
        localStorage.setItem('pcm_token', token);
      }
      
      localStorage.setItem('pcm_user', JSON.stringify(data));
      setUser(data);
      setLoading(false);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const register = async (email, password, nome, organizationNome) => {
    try {
      const { data } = await axios.post(
        `${API}/api/auth/register`,
        { email, password, nome, organization_nome: organizationNome }
      );
      
      const token = data.access_token || data.token;
      
      if (token) {
        setAccessToken(token);
        localStorage.setItem('pcm_token', token);
      }
      
      localStorage.setItem('pcm_user', JSON.stringify(data));
      setUser(data);
      setLoading(false);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem('pcm_token');
      if (token) {
        await axios.post(`${API}/api/auth/logout`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (e) {
      console.error('Logout error:', e);
    }
    localStorage.removeItem('pcm_user');
    localStorage.removeItem('pcm_token');
    setAccessToken(null);
    setUser(false);
  };

  const refreshToken = async () => {
    try {
      const token = localStorage.getItem('pcm_token');
      const { data } = await axios.post(`${API}/api/auth/refresh`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (data.access_token) {
        setAccessToken(data.access_token);
        localStorage.setItem('pcm_token', data.access_token);
      }
      await checkAuth();
    } catch (e) {
      localStorage.removeItem('pcm_user');
      localStorage.removeItem('pcm_token');
      setAccessToken(null);
      setUser(false);
    }
  };

  const value = {
    user,
    loading,
    isAuthenticated: !!user && user !== false,
    login,
    register,
    logout,
    refreshToken,
    checkAuth
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
