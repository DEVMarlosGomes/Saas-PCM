import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const TOKEN_KEY = 'aurix_token';
const USER_KEY  = 'aurix_user';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

function formatApiErrorDetail(detail) {
  if (detail == null) return 'Algo deu errado. Tente novamente.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === 'string' ? e.msg : JSON.stringify(e))).filter(Boolean).join(' ');
  if (detail && typeof detail.msg === 'string') return detail.msg;
  return String(detail);
}

function formatRequestError(error) {
  if (!error.response)
    return `Não foi possível conectar ao servidor Aurix em ${API}. Verifique se a API está rodando.`;
  return formatApiErrorDetail(error.response?.data?.detail) || error.message;
}

let accessToken = null;
export const getAccessToken = () => accessToken;
export const setAccessToken = (token) => { accessToken = token; };

function readStoredToken() {
  return (
    localStorage.getItem(TOKEN_KEY) ||
    localStorage.getItem('pcm_token') // backward-compat
  );
}

function readStoredUser() {
  try {
    const raw =
      localStorage.getItem(USER_KEY) ||
      localStorage.getItem('pcm_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [needsTechnicianSession, setNeedsTechnicianSession] = useState(false);

  const checkAuth = useCallback(async () => {
    const storedUser  = readStoredUser();
    const storedToken = readStoredToken();

    if (storedUser && storedToken) {
      try {
        setAccessToken(storedToken);
        const { data } = await axios.get(`${API}/api/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` },
        });
        setUser(data);
        setNeedsTechnicianSession(!!data.needs_technician_session);
        setLoading(false);
        return;
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem('pcm_token');
        localStorage.removeItem('pcm_user');
        setAccessToken(null);
      }
    }
    setUser(false);
    setLoading(false);
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = async (email, password) => {
    try {
      const { data } = await axios.post(`${API}/api/auth/login`, { email, password });
      const token = data.access_token || data.token;
      if (token) {
        setAccessToken(token);
        localStorage.setItem(TOKEN_KEY, token);
      }
      localStorage.setItem(USER_KEY, JSON.stringify(data));
      setUser(data);
      setNeedsTechnicianSession(!!data.needs_technician_session);
      setLoading(false);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatRequestError(e) };
    }
  };

  const completeTechnicianSession = async (sector, employeeId) => {
    try {
      const token = readStoredToken();
      const { data } = await axios.post(
        `${API}/api/auth/technician-session`,
        { sector, employee_id: employeeId },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      const newToken = data.access_token || data.token;
      if (newToken) {
        setAccessToken(newToken);
        localStorage.setItem(TOKEN_KEY, newToken);
      }
      localStorage.setItem(USER_KEY, JSON.stringify(data));
      setUser(data);
      setNeedsTechnicianSession(false);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatRequestError(e) };
    }
  };

  const register = async (email, password, nome, organizationNome) => {
    try {
      const { data } = await axios.post(`${API}/api/auth/register`, {
        email, password, nome, organization_nome: organizationNome,
      });
      const token = data.access_token || data.token;
      if (token) {
        setAccessToken(token);
        localStorage.setItem(TOKEN_KEY, token);
      }
      localStorage.setItem(USER_KEY, JSON.stringify(data));
      setUser(data);
      setLoading(false);
      return { success: true };
    } catch (e) {
      return { success: false, error: formatRequestError(e) };
    }
  };

  const logout = async () => {
    try {
      const token = readStoredToken();
      if (token) {
        await axios.post(`${API}/api/auth/logout`, {}, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch { /* ignore */ }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem('pcm_token');
    localStorage.removeItem('pcm_user');
    setAccessToken(null);
    setUser(false);
    setNeedsTechnicianSession(false);
  };

  const endTechnicianSession = async () => {
    try {
      const token = readStoredToken();
      await axios.post(`${API}/api/auth/technician-logout-session`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch { /* ignore */ }
    await checkAuth();
  };

  const refreshToken = async () => {
    try {
      const token = readStoredToken();
      const { data } = await axios.post(`${API}/api/auth/refresh`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (data.access_token) {
        setAccessToken(data.access_token);
        localStorage.setItem(TOKEN_KEY, data.access_token);
      }
      await checkAuth();
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      setAccessToken(null);
      setUser(false);
    }
  };

  return (
    <AuthContext.Provider value={{
      user, loading,
      isAuthenticated: !!user && user !== false,
      needsTechnicianSession,
      login, register, logout, refreshToken, checkAuth, completeTechnicianSession, endTechnicianSession,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
