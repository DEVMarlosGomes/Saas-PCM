# AURI— Gestão de Manutenção Industrial

> Plataforma SaaS multi-tenant para Planejamento e Controle de Manutenção (PCM) industrial. Rastreie ordens de serviço, equipamentos, manutenção preventiva, análise preditiva e muito mais — com billing integrado e controle de acesso por papel.

---

## Visão Geral

AURIX é uma aplicação web voltada para equipes de manutenção industrial. Cada empresa (organização) opera em seu próprio ambiente isolado (multi-tenancy via `organization_id`). A plataforma oferece:

- **Ordens de Serviço (OS)** com ciclo de vida completo e grupos de falha
- **Kanban** em tempo real com temporizadores de SLA e downtime
- **Dashboards** segmentados por papel (Admin, Líder, Operador)
- **Manutenção Preventiva** com planos e gatilhos automáticos
- **Análise Preditiva** com alertas críticos
- **Relatórios** com gráfico de Pareto e exportação
- **Billing** com 5 planos de assinatura via Stripe
- **RBAC** com 5 papéis hierárquicos
- **Login genérico de técnico** por setor (compartilhado)

---

## Funcionalidades

### Ordens de Serviço
- Criação com tipo (corretiva/preventiva), prioridade, equipamento, grupo de falha e setor
- Bloqueio por `failure_group` duplicado no mesmo equipamento (retorna 409 com grupos disponíveis)
- Registro de ocorrências (`downtime_start` imutável após primeiro registro)
- Cálculo automático de `response_time_min` ao mudar para `em_atendimento`
- Filtros avançados: status, prioridade, tipo, setor, busca textual

### Dashboards
- **Admin**: KPIs globais — OS abertas, em andamento, concluídas, taxa de resolução, eficiência, MTTR, MTBF
- **Líder**: KPIs + financeiro — custo de manutenção, relatório Pareto por grupo de falha
- **Operador/Técnico**: OS do turno, equipamentos críticos, tempo de resposta médio, alerta de SLA

### Equipamentos
- Cadastro com código, setor, modelo, fabricante, data de instalação
- Histórico de manutenções e indicadores de criticidade

### Análise Preditiva
- Alertas com severidade (CRITICO, ALTO, MEDIO)
- Badge de alertas críticos no sidebar (polling a cada 60s)

### Manutenção Preventiva
- Planos com frequência, responsável e gatilhos automáticos
- Geração automática de OS preventiva

### Relatórios
- Pareto de falhas por grupo
- Filtros por período e setor
- Exportação

### Billing
- 5 planos de assinatura com limites (equipamentos, usuários, OS)
- Troca de plano direta (sem Stripe) + via checkout Stripe
- Webhook Stripe para sincronização de status

### Auditoria
- Log de todas as ações críticas (criar, editar, excluir)
- Filtro por usuário, ação e período

### Login de Técnico
- Login genérico por setor sem credenciais individuais
- Sessão de turno — `endTechnicianSession` libera acesso para o próximo técnico

---

## Tech Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI, Python 3.11+ |
| ORM | SQLAlchemy 2.0 (async-ready, sync usado) |
| Banco | PostgreSQL (Supabase) |
| Auth | JWT HS256 — 8h access + 7d refresh |
| Hashing | bcrypt |
| Billing | Stripe API + Webhooks |
| Servidor | Uvicorn |
| Validação | Pydantic v2 |
| Frontend | React 19, React Router v7 |
| HTTP Client | Axios (interceptor JWT + auto-refresh) |
| UI | Shadcn UI + Tailwind CSS |
| Gráficos | Recharts |
| Toasts | Sonner |
| Ícones | Lucide-react |

---

## Arquitetura

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  React 19 + React Router v7 + Shadcn UI      │
│  AuthContext · ThemeContext · Axios           │
└──────────────────┬──────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼──────────────────────────┐
│                  Backend                     │
│  FastAPI · SQLAlchemy · Pydantic v2          │
│  JWT Auth · RBAC Middleware                  │
│  Stripe Webhook Handler                      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              PostgreSQL (Supabase)           │
│  Multi-tenant via organization_id            │
│  Sem Alembic — ALTER TABLE IF NOT EXISTS     │
└─────────────────────────────────────────────┘
```

**Multi-tenancy**: toda tabela possui `organization_id`. Todas as queries são filtradas pelo tenant do token JWT. O superusuário pode consultar qualquer organização.

**Migrações**: sem Alembic. A função `ensure_database_schema()` executa `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` ao iniciar o servidor.

---

## Planos e Limites

| Plano | Preço | Equipamentos | Usuários | OS/mês | Extras |
|---|---|---|---|---|---|
| Demo | Grátis (10 dias) | 5 | 3 | 10 | — |
| Essencial | R$ 250/mês | 20 | 10 | 100 | — |
| Profissional | R$ 490/mês | 35 | 45 | Ilimitado | Kanban, Preditivo |
| Avançado | R$ 790/mês | 50 | 100 | Ilimitado | Kanban, Preditivo, Relatórios |
| Enterprise | R$ 1.290/mês | Ilimitado | Ilimitado | Ilimitado | Todos |

---

## Roles e Permissões

| Role | Descrição | Acesso |
|---|---|---|
| `superusuario` | Gestor da plataforma | Portal Plataforma (todas as orgs) |
| `admin` | Administrador da organização | Tudo exceto Portal Plataforma |
| `lider` | Líder técnico | OS, Kanban, Equipamentos, Dashboards, Relatórios, Usuários, Auditoria |
| `tecnico` | Técnico de manutenção | OS, Kanban, Equipamentos, Planos Preventivos |
| `operador` | Operador de produção | OS (leitura + ocorrência), Kanban |

---

## Pré-requisitos

- Python 3.11+
- Node.js 18+ e Yarn
- PostgreSQL (ou conta Supabase)
- Conta Stripe (para billing)

---

## Instalação

```bash
# 1. Clone o repositório
git clone <repo-url>
cd Saas-PCM

# 2. Backend
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt

# 3. Frontend
cd ../frontend
yarn install
```

---

## Variáveis de Ambiente

### Backend — `backend/.env`

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
JWT_SECRET=seu_segredo_jwt_aqui
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
CORS_ORIGINS=http://localhost:3000
```

### Frontend — `frontend/.env`

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Rodando o Projeto

### Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

A API ficará disponível em `http://localhost:8001`. Documentação automática em `http://localhost:8001/docs`.

### Frontend

```bash
cd frontend
yarn start
```

O app ficará disponível em `http://localhost:3000`.

### Seed de demonstração

```bash
# Com o backend rodando:
curl -X POST http://localhost:8001/api/seed-demo
```

Cria uma organização demo com usuários, equipamentos e OS de exemplo.

---

## Estrutura de Pastas

```
Saas-PCM/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, startup, CORS
│   │   ├── config.py            # Planos, limites, SLA
│   │   ├── database.py          # Engine SQLAlchemy
│   │   ├── models.py            # Todos os modelos ORM
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── auth.py              # JWT, bcrypt, deps
│   │   ├── migrations.py        # ensure_database_schema()
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── equipamentos.py
│   │       ├── ordens_servico.py
│   │       ├── planos_preventivos.py
│   │       ├── preditivo.py
│   │       ├── relatorios.py
│   │       ├── usuarios.py
│   │       ├── billing.py
│   │       ├── auditoria.py
│   │       ├── setores.py
│   │       ├── dashboard.py
│   │       └── superusuario.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js               # Rotas e guards
│   │   ├── contexts/
│   │   │   ├── AuthContext.jsx
│   │   │   └── ThemeContext.jsx
│   │   ├── lib/
│   │   │   └── api.js           # Axios + todas as chamadas de API
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── TecnicoLoginPage.jsx
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── DashboardLiderPage.jsx
│   │   │   ├── DashboardOperadorPage.jsx
│   │   │   ├── EquipamentosPage.jsx
│   │   │   ├── OrdensServicoPage.jsx
│   │   │   ├── KanbanPage.jsx
│   │   │   ├── PlanosPreventivosPage.jsx
│   │   │   ├── PreditivoPage.jsx
│   │   │   ├── RelatoriosPage.jsx
│   │   │   ├── UsuariosPage.jsx
│   │   │   ├── AuditoriaPage.jsx
│   │   │   ├── BillingPage.jsx
│   │   │   ├── SettingsPage.jsx
│   │   │   └── SuperuserPage.jsx
│   │   └── components/
│   │       ├── AppLayout.jsx
│   │       ├── ui/              # Shadcn UI components
│   │       └── shared/
│   │           └── NotificacoesDropdown.jsx
│   └── package.json
├── backend_test.py              # Suite de testes automatizados
├── test_result.md               # Status e resultado dos testes
├── design_guidelines.json       # Design system da plataforma
└── README.md
```

---

## Rotas do Frontend

| Rota | Componente | Roles |
|---|---|---|
| `/login` | LoginPage | Público |
| `/login/tecnico` | TecnicoLoginPage | Público |
| `/dashboard` | DashboardPage | admin |
| `/dashboard/lider` | DashboardLiderPage | lider |
| `/dashboard/operador` | DashboardOperadorPage | tecnico, operador |
| `/equipamentos` | EquipamentosPage | admin, lider, tecnico |
| `/ordens-servico` | OrdensServicoPage | admin, lider, tecnico, operador |
| `/kanban` | KanbanPage | admin, lider, tecnico, operador |
| `/planos-preventivos` | PlanosPreventivosPage | admin, lider, tecnico |
| `/preditivo` | PreditivoPage | admin, lider |
| `/relatorios` | RelatoriosPage | admin, lider |
| `/usuarios` | UsuariosPage | admin, lider |
| `/auditoria` | AuditoriaPage | admin, lider |
| `/billing` | BillingPage | admin |
| `/settings` | SettingsPage | admin |
| `/superuser` | SuperuserPage | superusuario |

---

## API Endpoints

### Auth
| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/login` | Login com e-mail e senha |
| POST | `/api/auth/refresh` | Renovar access token |
| POST | `/api/auth/logout` | Revogar refresh token |
| POST | `/api/auth/login/tecnico` | Login genérico de técnico por setor |
| POST | `/api/auth/tecnico/end-session` | Finalizar turno do técnico |

### Setores
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/setores` | Listar setores da organização |
| POST | `/api/setores` | Criar setor |

### Equipamentos
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/equipamentos` | Listar (filtros: setor, busca) |
| POST | `/api/equipamentos` | Criar |
| PUT | `/api/equipamentos/{id}` | Editar |
| DELETE | `/api/equipamentos/{id}` | Excluir |

### Ordens de Serviço
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/ordens-servico` | Listar (filtros: status, prioridade, tipo, setor) |
| POST | `/api/ordens-servico` | Criar — 409 se failure_group duplicado |
| PUT | `/api/ordens-servico/{id}` | Editar |
| PATCH | `/api/ordens-servico/{id}/status` | Mudar status (calcula response_time_min) |
| PATCH | `/api/ordens-servico/{id}/ocorrencia` | Adicionar ocorrência (downtime_start imutável) |
| DELETE | `/api/ordens-servico/{id}` | Excluir |

### Dashboard
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/dashboard` | KPIs admin |
| GET | `/api/dashboard/lider` | KPIs + financeiro (lider) |
| GET | `/api/dashboard/operador` | KPIs do turno (tecnico/operador) |

### Planos Preventivos
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/planos-preventivos` | Listar planos |
| POST | `/api/planos-preventivos` | Criar plano |
| PUT | `/api/planos-preventivos/{id}` | Editar |
| DELETE | `/api/planos-preventivos/{id}` | Excluir |
| POST | `/api/planos-preventivos/{id}/executar` | Gerar OS preventiva |

### Análise Preditiva
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/preditivo/alertas` | Listar alertas (filtro: severidade) |
| POST | `/api/preditivo/alertas` | Criar alerta |
| PATCH | `/api/preditivo/alertas/{id}` | Atualizar alerta |

### Relatórios
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/relatorios` | Relatório Pareto de falhas |

### Usuários
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/usuarios` | Listar usuários da organização |
| POST | `/api/usuarios` | Criar usuário |
| PUT | `/api/usuarios/{id}` | Editar |
| DELETE | `/api/usuarios/{id}` | Excluir |

### Billing
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/billing/plans` | Listar planos disponíveis |
| POST | `/api/billing/checkout` | Criar sessão Stripe Checkout |
| POST | `/api/billing/change-plan` | Trocar plano diretamente |
| POST | `/api/billing/webhook` | Webhook Stripe |

### Superusuário
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/superuser/organizations` | Listar todas as organizações |
| GET | `/api/superuser/stats` | Estatísticas globais da plataforma |
| POST | `/api/superuser/organizations` | Criar organização |
| PATCH | `/api/superuser/organizations/{id}` | Editar organização/plano |

---

## Testes

O arquivo `backend_test.py` contém uma suite de testes automatizados contra a API:

```bash
# Com o backend rodando em localhost:8001:
python backend_test.py

# URL customizada:
AURIX_API_URL=https://api.meudominio.com/api python backend_test.py
```

Resultado salvo em `backend_test_results.json`. Status detalhado em `test_result.md`.

| # | Cenário | Endpoint |
|---|---|---|
| 1 | Login admin | POST /auth/login |
| 2 | Criar equipamento | POST /equipamentos |
| 3 | Criar OS corretiva | POST /ordens-servico |
| 4 | Mudar status da OS | PATCH /ordens-servico/{id}/status |
| 5 | Criar plano preventivo | POST /planos-preventivos |
| 6 | Criar alerta preditivo | POST /preditivo/alertas |
| 7 | Dashboard admin | GET /dashboard |
| 8 | Criar usuário técnico | POST /usuarios |
| 9 | RBAC — técnico sem acesso admin | GET /usuarios (403) |
| 10 | Limite de equipamentos | POST /equipamentos (402) |
| 11 | OS com failure_group | POST /ordens-servico |
| 12 | Bloqueio grupo de falha (409) | POST /ordens-servico |
| 13 | OS grupo diferente (mesmo equip.) | POST /ordens-servico |
| 14 | Login genérico técnico | POST /auth/login/tecnico |
| 15 | Adicionar ocorrência | PATCH /ordens-servico/{id}/ocorrencia |
| 16 | response_time_min calculado | PATCH /ordens-servico/{id}/status |
| 17 | Dashboard operador | GET /dashboard/operador |
| 18 | Dashboard lider | GET /dashboard/lider |

---

## Design System

Arquétipo **Swiss / High-Contrast** — foco em legibilidade e densidade de informação.

### Tipografia
- **Headings**: Outfit (font-heading)
- **Body**: Inter (font-sans)

### Paleta (modo escuro padrão)
| Token | Uso |
|---|---|
| `--primary` | Azul principal (#3B82F6) |
| `--background` | Fundo da página |
| `--card` | Superfícies de card |
| `--muted-foreground` | Texto secundário |
| `--border` | Bordas |

### Grupos de Falha — Cores
| Grupo | Cor |
|---|---|
| Elétrico | Azul (#3B82F6) |
| Hidráulico | Âmbar (#F59E0B) |
| Mecânico | Cinza (#6B7280) |
| Pneumático | Teal (#0D9488) |
| Instrumentação | Violeta (#8B5CF6) |
| Estrutural | Laranja (#FB923C) |
| Outro | Neutro |

### SLA por Prioridade
| Prioridade | Limite |
|---|---|
| Crítica | 30 min |
| Alta | 60 min |
| Média | 120 min |
| Baixa | 480 min |

### Regras
- Sem glassmorphism
- Bordas 1px com `border-border/50`
- `rounded-sm` / `rounded-lg` — sem `rounded-full` em cards
- Todos os inputs/botões novos com `data-testid`
- Suporte a dark mode via variáveis Tailwind CSS
- Textos em PT-BR

---

## Licença

Proprietário — AURIX © 2026. Todos os direitos reservados.
