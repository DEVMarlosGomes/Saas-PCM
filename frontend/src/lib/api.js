import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${API}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('pcm_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const token = localStorage.getItem('pcm_token');
        const { data } = await axios.post(`${API}/api/auth/refresh`, {}, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (data.access_token) {
          localStorage.setItem('pcm_token', data.access_token);
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        // Don't redirect if already on login page
        if (!window.location.pathname.includes('/login')) {
          localStorage.removeItem('pcm_user');
          localStorage.removeItem('pcm_token');
          // Use setTimeout to allow pending promises/finally blocks to settle
          setTimeout(() => {
            window.location.href = '/login';
          }, 100);
        }
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Dashboard
export const getDashboardKPIs = () => api.get('/dashboard/kpis');
export const getBacklog = () => api.get('/dashboard/backlog');

// Equipamentos
export const getEquipamentos = () => api.get('/equipamentos');
export const getEquipamento = (id) => api.get(`/equipamentos/${id}`);
export const createEquipamento = (data) => api.post('/equipamentos', data);
export const updateEquipamento = (id, data) => api.put(`/equipamentos/${id}`, data);
export const deleteEquipamento = (id) => api.delete(`/equipamentos/${id}`);
export const getEquipamentoHistorico = (id) => api.get(`/equipamentos/${id}/historico`);

// Ordens de Serviço
export const getOrdensServico = (params) => api.get('/ordens-servico', { params });
export const getOrdemServico = (id) => api.get(`/ordens-servico/${id}`);
export const createOrdemServico = (data) => api.post('/ordens-servico', data);
export const updateOrdemServico = (id, data) => api.put(`/ordens-servico/${id}`, data);

// Custos
export const getCustos = (params) => api.get('/custos', { params });
export const createCusto = (data) => api.post('/custos', data);

// Grupos e Subgrupos
export const getGrupos = () => api.get('/grupos');
export const createGrupo = (data) => api.post('/grupos', data);
export const getSubgrupos = () => api.get('/subgrupos');
export const createSubgrupo = (data) => api.post('/subgrupos', data);

// Planos Preventivos
export const getPlanosPreventivos = () => api.get('/planos-preventivos');
export const createPlanoPreventivo = (data) => api.post('/planos-preventivos', data);
export const executarPlano = (id) => api.post(`/planos-preventivos/${id}/executar`);

// Users
export const getUsers = () => api.get('/users');
export const createUser = (data) => api.post('/users', data);
export const updateUser = (id, data) => api.put(`/users/${id}`, data);
export const deleteUser = (id) => api.delete(`/users/${id}`);

// Organization
export const getOrganization = () => api.get('/organization');
export const updateOrganization = (data) => api.put('/organization', data);

// Auditoria
export const getAuditoria = (params) => api.get('/auditoria', { params });

// Billing
export const getBillingPlan = () => api.get('/billing/plan');
export const createBillingCheckout = (data) => api.post('/billing/checkout', data);
export const getCheckoutStatus = (sessionId) => api.get(`/billing/checkout/status/${sessionId}`);
export const getBillingTransactions = () => api.get('/billing/transactions');

// Reviews
export const getPendingReviews = () => api.get('/ordens-servico/pending-reviews');
export const autoApproveExpired = () => api.post('/ordens-servico/auto-approve');

// Password
export const changePassword = (data) => api.post('/auth/change-password', data);

// Seed Demo
export const seedDemo = () => api.post('/seed-demo');

export default api;
