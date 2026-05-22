import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const TOKEN_KEY = 'aurix_token';
const USER_KEY  = 'aurix_user';

const api = axios.create({
  baseURL: `${API}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Interceptor de request: injeta JWT ──────────────────
api.interceptors.request.use(
  (config) => {
    const token =
      localStorage.getItem(TOKEN_KEY) ||
      localStorage.getItem('pcm_token'); // backward-compat durante migração
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Listeners globais para 402 (limite de plano) ────────
const upgradeListeners = new Set();

export function onUpgradeRequired(fn) {
  upgradeListeners.add(fn);
  return () => upgradeListeners.delete(fn);
}

function notifyUpgrade(detail) {
  upgradeListeners.forEach((fn) => fn(detail));
}

// ─── Interceptor de response: refresh 401 + upgrade 402 ──
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 402 — limite de plano atingido
    if (error.response?.status === 402) {
      const detail = error.response.data?.detail;
      notifyUpgrade(
        typeof detail === 'object'
          ? detail
          : { mensagem: typeof detail === 'string' ? detail : 'Limite do plano atingido.' }
      );
      return Promise.reject(error);
    }

    // 401 — tenta refresh de token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const token =
          localStorage.getItem(TOKEN_KEY) ||
          localStorage.getItem('pcm_token');
        const { data } = await axios.post(`${API}/api/auth/refresh`, {}, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (data.access_token) {
          localStorage.setItem(TOKEN_KEY, data.access_token);
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        }
        return api(originalRequest);
      } catch {
        if (!window.location.pathname.includes('/login')) {
          localStorage.removeItem(USER_KEY);
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem('pcm_user');
          localStorage.removeItem('pcm_token');
          setTimeout(() => { window.location.href = '/login'; }, 100);
        }
      }
    }

    return Promise.reject(error);
  }
);

// ─── Dashboard ───────────────────────────────────────────
export const getDashboardKPIs = () => api.get('/dashboard/kpis');
export const getBacklog = () => api.get('/dashboard/backlog');
export const getDashboardTendencia = (dias = 30) => api.get('/dashboard/tendencia', { params: { dias } });

// ─── Kanban ───────────────────────────────────────────────
export const getKanban = () => api.get('/kanban');

// ─── OS Ocorrências ───────────────────────────────────────
export const addOcorrenciaOS = (id, descricao) => api.post(`/ordens-servico/${id}/ocorrencias`, { descricao });

// ─── Equipamentos ─────────────────────────────────────────
export const getEquipamentos = () => api.get('/equipamentos');
export const getEquipamento = (id) => api.get(`/equipamentos/${id}`);
export const createEquipamento = (data) => api.post('/equipamentos', data);
export const updateEquipamento = (id, data) => api.put(`/equipamentos/${id}`, data);
export const deleteEquipamento = (id) => api.delete(`/equipamentos/${id}`);
export const getEquipamentoHistorico = (id) => api.get(`/equipamentos/${id}/historico`);

// ─── Ordens de Serviço ────────────────────────────────────
export const getOrdensServico = (params) => api.get('/ordens-servico', { params });
export const getOrdemServico = (id) => api.get(`/ordens-servico/${id}`);
export const createOrdemServico = (data) => api.post('/ordens-servico', data);
export const updateOrdemServico = (id, data) => api.put(`/ordens-servico/${id}`, data);

// ─── Custos ───────────────────────────────────────────────
export const getCustos = (params) => api.get('/custos', { params });
export const createCusto = (data) => api.post('/custos', data);

// ─── Grupos / Subgrupos ───────────────────────────────────
export const getGrupos = () => api.get('/grupos');
export const createGrupo = (data) => api.post('/grupos', data);
export const getSubgrupos = () => api.get('/subgrupos');
export const createSubgrupo = (data) => api.post('/subgrupos', data);

// ─── Planos Preventivos ───────────────────────────────────
export const getPlanosPreventivos = () => api.get('/planos-preventivos');
export const createPlanoPreventivo = (data) => api.post('/planos-preventivos', data);
export const executarPlano = (id) => api.post(`/planos-preventivos/${id}/executar`);

// ─── Usuários ─────────────────────────────────────────────
export const getUsers = () => api.get('/users');
export const createUser = (data) => api.post('/users', data);
export const updateUser = (id, data) => api.put(`/users/${id}`, data);
export const deleteUser = (id) => api.delete(`/users/${id}`);

// ─── Organização ──────────────────────────────────────────
export const getOrganization = () => api.get('/organization');
export const updateOrganization = (data) => api.put('/organization', data);
export const generateApiKey = () => api.post('/organization/generate-api-key');
export const revokeApiKey = () => api.delete('/organization/api-key');

// ─── Auditoria ────────────────────────────────────────────
export const getAuditoria = (params) => api.get('/auditoria', { params });

// ─── Billing ─────────────────────────────────────────────
export const getBillingPlan = () => api.get('/billing/plan');
export const getBillingPlanos = () => api.get('/billing/planos');
export const createBillingCheckout = (data) => api.post('/billing/checkout', data);
export const getCheckoutStatus = (sessionId) => api.get(`/billing/checkout/status/${sessionId}`);
export const getBillingTransactions = () => api.get('/billing/transactions');
export const cancelarAssinatura = () => api.post('/billing/cancelar');
export const getBillingPortal = () => api.get('/billing/portal');
export const changePlan = (plan) => api.post('/billing/change-plan', { plan });
export const contatoEnterprise = (data) => api.post('/billing/contato-enterprise', data);

// ─── Confiabilidade / Reliability ─────────────────────────
export const getConfiabilidade = (t = 24) => api.get('/confiabilidade', { params: { t } });
export const getCurvaConfiabilidade = (equipamentoId, maxT = 168, pontos = 50) =>
  api.get(`/confiabilidade/${equipamentoId}/curva`, { params: { max_t: maxT, pontos } });

// ─── Preditivo Completo ───────────────────────────────────
export const getPreditivoDashboard = () => api.get('/preditivo/dashboard');
export const getSaudeEquipamentos = () => api.get('/preditivo/saude-equipamentos');
export const getAlertasPreditivos = (params) => api.get('/preditivo/alertas', { params });
export const gerarOsAlerta = (id) => api.post(`/preditivo/alertas/${id}/gerar-os`);
export const ignorarAlerta = (id, motivo) => api.post(`/preditivo/alertas/${id}/ignorar`, { motivo });
export const getConfigsMonitoramento = () => api.get('/preditivo/configuracoes');
export const createConfigMonitoramento = (data) => api.post('/preditivo/configuracoes', data);
export const updateConfigMonitoramento = (id, data) => api.put(`/preditivo/configuracoes/${id}`, data);
export const registrarLeitura = (data) => api.post('/preditivo/leituras', data);
export const getHistoricoLeituras = (equipId, params) => api.get(`/preditivo/leituras/${equipId}`, { params });
export const getRelatorioKPIs = (params) => api.get('/relatorios/kpis', { params });
export const getRelatorioEquipamentos = (params) => api.get('/relatorios/equipamentos', { params });

// ─── Reviews ──────────────────────────────────────────────
export const getPendingReviews = () => api.get('/ordens-servico/pending-reviews');
export const autoApproveExpired = () => api.post('/ordens-servico/auto-approve');

// ─── Relatórios ───────────────────────────────────────────
export const getRelatorioOS = (params) => api.get('/relatorios/os', { params });
export const getRelatorioCustos = (params) => api.get('/relatorios/custos', { params });
export const getRelatorioPareto = (params) => api.get('/relatorios/pareto', { params });
export const getRelatorioPreventivos = () => api.get('/relatorios/preventivos');

// ─── Notificações ─────────────────────────────────────────
export const getNotificacoes = (params) => api.get('/notificacoes', { params });
export const countNotificacoes = () => api.get('/notificacoes/count');
export const marcarLida = (id) => api.post(`/notificacoes/${id}/ler`);
export const marcarTodasLidas = () => api.post('/notificacoes/ler-todas');

// ─── Auth ──────────────────────────────────────────────────
export const changePassword = (data) => api.post('/auth/change-password', data);
export const setTechnicianSession = (sector, employee_id) => api.post('/auth/technician-session', { sector, employee_id });
export const clearTechnicianSession = () => api.post('/auth/technician-logout-session');

// ─── Superusuário (plataforma) ────────────────────────────
export const getSuperuserEmpresas = () => api.get('/superuser/empresas');
export const createSuperuserEmpresa = (data) => api.post('/superuser/empresas', data);
export const updateSuperuserEmpresa = (orgId, data) => api.put(`/superuser/empresas/${orgId}`, data);
export const getSuperuserDashboard = () => api.get('/superuser/dashboard');

// ─── Seed Demo ────────────────────────────────────────────
export const seedDemo = (reset = false) => api.post(`/seed-demo${reset ? '?reset=true' : ''}`);

export default api;
