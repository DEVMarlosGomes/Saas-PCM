<div align="center">

AURIX

Plataforma SaaS para Gestão de Manutenção Industrial

Ativos, equipes, ordens de serviço e indicadores de manutenção reunidos em um único ambiente operacional.



Tecnologia aplicada à confiabilidade, disponibilidade e eficiência da manutenção industrial.

</div>

Sumário

Sobre o AURIX

Visão do produto

Indicadores do projeto

Principais funcionalidades

Fluxo operacional

Módulos da plataforma

Indicadores de manutenção

Arquitetura

Decisões de engenharia

Segurança e privacidade

Perfis e controle de acesso

Tecnologias

Estrutura do projeto

Instalação local

Variáveis de ambiente

Execução e build

Testes

API e observabilidade

Deploy

Roadmap

Competências demonstradas

Autor

Licença

Sobre o AURIX

O AURIX é uma plataforma SaaS de Planejamento e Controle de Manutenção (PCM) criada para centralizar a gestão de ativos, equipes e intervenções técnicas em operações industriais.

A solução acompanha o processo de manutenção desde a identificação de uma falha até a validação do serviço realizado, registrando tempos, custos, materiais, evidências, responsáveis e histórico operacional.

Com arquitetura multiempresa, cada organização utiliza um ambiente logicamente isolado. A experiência e as permissões são adaptadas ao papel de cada usuário, permitindo que gestores, líderes, técnicos e operadores atuem sobre o mesmo processo com níveis de acesso distintos.

O projeto foi construído como uma aplicação Full Stack real, contemplando não apenas telas e cadastros, mas também regras de negócio, billing SaaS, segurança, auditoria, operação offline, eventos em tempo real, integrações e observabilidade.

Visão do produto

O AURIX busca transformar registros dispersos de manutenção em um fluxo operacional rastreável e orientado por dados.

Desafio industrial

Como o AURIX atua

Falhas registradas de forma descentralizada

Centraliza solicitações e ordens de serviço

Dificuldade para priorizar atendimentos

Organiza criticidade, prioridade, SLA e status

Pouca visibilidade sobre máquinas paradas

Registra downtime e calcula impacto operacional

Histórico técnico incompleto

Mantém ocorrências, evidências, custos e auditoria

Manutenção preventiva dependente de controles manuais

Estrutura planos e rotinas de geração de OS

Decisões sem indicadores confiáveis

Consolida MTTR, MTBF, disponibilidade, Pareto e custos

Sistemas diferentes para cada unidade

Isola organizações dentro de uma plataforma multi-tenant

Crescimento sem modelo comercial escalável

Aplica planos, limites, feature flags e billing integrado

Indicadores do projeto

Os números abaixo representam a estrutura analisada nesta versão do repositório e podem evoluir conforme o produto recebe novos módulos.

<div align="center">

API

Interface

Componentes

Qualidade

160+ endpoints

20+ páginas

50+ componentes React

Cerca de 80 testes backend

Rotas organizadas por domínio

Fluxos por perfil de usuário

Biblioteca reutilizável de UI

Testes unitários, segurança e negócio

</div>

Outros destaques técnicos:

Mais de 20 módulos de rotas no backend

Separação entre routers, services, schemas, models e middlewares

API versionada atualmente como 4.0.0

Aplicação web instalável com recursos de PWA

Suporte a API REST e eventos em tempo real via Server-Sent Events

Deploy preparado para frontend e backend independentes

Principais funcionalidades

Ordens de Serviço

Abertura de OS corretivas, preventivas e preditivas

Classificação por prioridade, setor, equipamento, grupo e subgrupo

Ciclo completo de atendimento, revisão e encerramento

Registro incremental de ocorrências durante a intervenção

Cálculo de tempo de resposta e tempo total de parada

Controle de SLA conforme a prioridade

Bloqueio de grupos de falha conflitantes no mesmo equipamento

Associação de equipes e colaboradores

Registro de custos, peças e evidências

Histórico de mudanças de status

Fluxo de revisão com atribuição de responsável

Ativos e equipamentos

Cadastro de máquinas, equipamentos e componentes

Organização hierárquica de ativos

Classificação de criticidade

Agrupamento por setor, grupo e subgrupo

Localização e dados operacionais

Histórico de manutenções por equipamento

Custo estimado de parada com base no valor/hora do ativo

Planejamento preventivo

Criação de planos preventivos

Definição de frequência e responsáveis

Vinculação com equipamentos

Geração de ordens preventivas

Processamento por rotinas agendadas

Acompanhamento de execução e vencimento

Monitoramento preditivo e IoT

Cadastro de configurações de monitoramento

Recebimento de telemetria autenticada por API key

Registro de leituras de sensores

Alertas classificados por severidade

Conversão de eventos críticos em ações operacionais

Visão consolidada de alertas por organização

Kanban operacional

Visualização das ordens por etapa

Movimentação entre estados permitidos

Priorização visual de atendimentos

Acompanhamento de SLA e downtime

Atualização de informações operacionais em tempo real

Dashboards por perfil

Dashboard estratégico para administração

Dashboard de liderança de manutenção

Dashboard operacional para técnicos e produção

KPIs de disponibilidade, produtividade e confiabilidade

Rankings de equipamentos e falhas

Visões de custos e impacto de parada

Acompanhamento do volume de OS por status e período

Almoxarifado e estoque

Cadastro de peças e fornecedores

Organização por depósitos

Controle de saldo por item e local

Entradas, saídas, ajustes e transferências

Consumo de material associado à ordem de serviço

Alertas de estoque abaixo do ponto de reposição

Rastreabilidade das movimentações

Evidências e checklists

Anexos vinculados às ordens de serviço

Registro de imagens e documentos técnicos

Templates de checklist

Execução de checklists durante a manutenção

Evidências para validação, auditoria e conformidade

Relatórios

Análise de Pareto por grupo de falha

Indicadores de MTTR e MTBF

Tempo de resposta e tempo de parada

Relatórios de custo de manutenção

Filtros por período, setor e equipamento

Exportação de dados em PDF e Excel

Auditoria e notificações

Registro de ações críticas

Rastreamento de alterações em campos relevantes

Filtros por usuário, ação e período

Notificações internas por evento

Eventos em tempo real isolados por organização

Integração opcional com canais externos de comunicação

Gestão SaaS e billing

Organizações independentes na mesma plataforma

Planos com limites de equipamentos, usuários e ordens

Feature flags por nível de assinatura

Fluxo de upgrade dentro da aplicação

Integração com Stripe Checkout

Processamento de webhooks

Histórico de transações

Portal administrativo para gestão da plataforma

Fluxo operacional

Identificação da necessidade
          │
          ▼
Abertura da solicitação / OS
          │
          ├── Equipamento e setor
          ├── Tipo de manutenção
          ├── Prioridade e criticidade
          └── Grupo e subgrupo de falha
          │
          ▼
Triagem e planejamento
          │
          ├── Definição de responsável
          ├── Verificação de SLA
          ├── Disponibilidade de materiais
          └── Preparação da intervenção
          │
          ▼
Execução técnica
          │
          ├── Início do atendimento
          ├── Ocorrências e apontamentos
          ├── Peças, custos e mão de obra
          ├── Evidências e checklist
          └── Controle do downtime
          │
          ▼
Revisão e validação
          │
          ├── Conferência da execução
          ├── Aprovação da liderança
          └── Registro de auditoria
          │
          ▼
Encerramento
          │
          ▼
Histórico, indicadores e melhoria contínua

Estados principais de uma OS

ABERTA
  │
  ▼
EM ATENDIMENTO
  │
  ├── AGUARDANDO PEÇA
  │
  ▼
AGUARDANDO REVISÃO
  │
  ▼
REVISADA
  │
  ▼
FECHADA

As transições respeitam regras de negócio, permissões, histórico e validações do processo.

Módulos da plataforma

Módulo

Responsabilidade

Autenticação

Login, refresh token, recuperação de acesso e sessões

MFA

Autenticação multifator com TOTP e códigos de recuperação

SSO

Integração corporativa com provedores compatíveis com OIDC

Organizações

Isolamento multiempresa, configurações e plano contratado

Usuários e RBAC

Papéis, permissões e controle de acesso granular

Colaboradores

Gestão das pessoas envolvidas na operação

Setores

Organização dos ambientes e equipes industriais

Equipamentos

Cadastro, hierarquia, criticidade e histórico de ativos

Ordens de Serviço

Planejamento, execução, revisão e encerramento das intervenções

Custos

Materiais, substituições, mão de obra e custo de parada

Preventiva

Planos e rotinas de manutenção programada

Preditiva

Leituras, monitoramento e alertas por severidade

IoT

Entrada autenticada de telemetria de equipamentos

Kanban

Gestão visual do fluxo operacional

Estoque

Peças, depósitos, saldos e movimentações

Fornecedores

Apoio ao abastecimento e controle de materiais

Evidências

Anexos, checklists e comprovações técnicas

Dashboards

Indicadores adequados ao contexto de cada perfil

Relatórios

Análises de desempenho, falhas e custos

Notificações

Avisos internos e atualizações em tempo real

Auditoria

Histórico de ações administrativas e operacionais

LGPD

Consentimento, portabilidade e tratamento de solicitações

Billing

Assinaturas, planos, limites e integração de pagamentos

Superusuário

Administração global da plataforma SaaS

Indicadores de manutenção

O AURIX utiliza os dados operacionais para apoiar decisões de manutenção e confiabilidade.

Indicador

Aplicação

MTTR

Mede o tempo médio necessário para reparar um equipamento

MTBF

Indica o tempo médio de operação entre falhas

Disponibilidade

Avalia o percentual de tempo em que o ativo permanece disponível

Tempo de resposta

Mede o intervalo entre a abertura e o início do atendimento

Downtime

Consolida o período de indisponibilidade dos ativos

Cumprimento de SLA

Compara o atendimento com os limites definidos por prioridade

Custo de parada

Estima o impacto financeiro da indisponibilidade

Custo de manutenção

Agrupa peças, mão de obra e demais custos da intervenção

Pareto de falhas

Identifica os grupos responsáveis pela maior recorrência de problemas

Backlog de OS

Mostra a distribuição de serviços pendentes e em andamento

SLA padrão por prioridade

Prioridade

Limite de referência

Crítica

30 minutos

Alta

60 minutos

Média

120 minutos

Baixa

480 minutos

Os valores podem evoluir para configurações específicas de cada operação e contrato.

Arquitetura

┌─────────────────────────────────────────────────────────────┐
│                         FRONTEND                            │
│ React 19 · React Router 7 · Tailwind CSS · Radix UI        │
│ Context API · Axios · Recharts · PWA · Offline Queue       │
└────────────────────────────┬────────────────────────────────┘
                             │
                  REST API + Server-Sent Events
                             │
┌────────────────────────────▼────────────────────────────────┐
│                          BACKEND                            │
│ FastAPI · Pydantic 2 · SQLAlchemy 2 · APScheduler          │
│ JWT · MFA · OIDC · RBAC · Rate Limiting · Security Headers│
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                         POSTGRESQL                          │
│        Isolamento lógico por organization_id               │
└────────────────────────────┬────────────────────────────────┘
                             │
            ┌────────────────┼───────────────────┐
            ▼                ▼                   ▼
          Stripe       Observabilidade      Serviços externos
      Checkout/Webhook  Sentry/Prometheus   E-mail/Notificações

Organização do backend

Request
  │
  ▼
Middleware
  ├── Request ID
  ├── Security Headers
  ├── Rate Limiting
  └── Tenant Isolation
  │
  ▼
Router
  │
  ▼
Service / Regra de negócio
  │
  ▼
SQLAlchemy Model
  │
  ▼
PostgreSQL

Organização do frontend

Rota protegida
  │
  ▼
Layout e guarda de acesso
  │
  ▼
Página do módulo
  │
  ├── Componentes compartilhados
  ├── Contextos globais
  ├── Cliente HTTP com interceptors
  └── Eventos em tempo real / fila offline

Decisões de engenharia

Arquitetura multi-tenant

Os dados operacionais são associados a uma organização. O tenant é extraído do contexto autenticado e aplicado às consultas, reduzindo o risco de acesso cruzado entre empresas.

Organização A                     Organização B
├── Usuários                      ├── Usuários
├── Equipamentos                  ├── Equipamentos
├── Ordens de Serviço             ├── Ordens de Serviço
├── Estoque                       ├── Estoque
└── Indicadores                   └── Indicadores

             Mesma plataforma, dados isolados

Separação por domínio

O backend é organizado em módulos independentes, evitando concentrar toda a aplicação em um único arquivo. Rotas, contratos, entidades e regras de negócio possuem responsabilidades distintas.

Controle de acesso em múltiplas camadas

As permissões não dependem apenas da interface. O frontend controla a experiência do usuário, enquanto o backend valida a autorização sobre cada recurso protegido.

Feature flags por assinatura

Recursos como Kanban, análise preditiva, estoque, evidências, relatórios e integrações podem ser liberados conforme o plano da organização.

Tempo real isolado por organização

O sistema utiliza Server-Sent Events (SSE) para distribuir eventos operacionais. Cada conexão é vinculada ao tenant autenticado, evitando que atualizações de uma organização sejam entregues a outra.

Operação offline

O frontend possui service worker e fila local para melhorar a experiência em ambientes industriais com conectividade instável. Leituras podem utilizar cache controlado, e operações pendentes podem ser sincronizadas após o retorno da conexão.

Processamento agendado

Rotinas periódicas utilizam APScheduler para automatizar tarefas relacionadas a manutenção preventiva e processos internos.

Observabilidade

A aplicação disponibiliza health checks, request IDs, logs estruturados e integrações opcionais com Sentry e Prometheus.

Segurança e privacidade

A segurança foi tratada como parte da arquitetura da aplicação, não apenas como uma camada visual.

Autenticação

Access tokens e refresh tokens JWT

Senhas protegidas com bcrypt

Expiração e renovação de sessão

Registro de tentativas de login

Recuperação de acesso

Sessões específicas para operação técnica

Autenticação multifator

MFA baseado em TOTP, compatível com aplicativos autenticadores

Secret protegido com criptografia simétrica

Códigos de recuperação

Confirmação adicional para ativação e desativação

SSO corporativo

Integração com provedores OIDC

Fluxo de autorização e callback

Provisionamento de usuário conforme configuração da organização

Recurso controlado por plano e configuração administrativa

Proteções de API

Rate limiting em endpoints sensíveis

Security headers HTTP

CORS configurável por ambiente

Request ID para rastreabilidade

Validação de payloads com Pydantic

Autorização por perfil e permissão

Isolamento de tenant no backend

Inicialização fail-fast quando variáveis críticas estão ausentes em produção

LGPD

O projeto contempla recursos associados aos direitos do titular, incluindo:

Registro e atualização de consentimentos

Exportação de dados pessoais

Solicitações de privacidade

Anonimização mediante fluxo administrativo

Redução de dados pessoais enviados à observabilidade

Credenciais, tokens, dados de clientes, chaves privadas, arquivos .env e informações comerciais sensíveis não devem ser publicados no repositório.

Perfis e controle de acesso

A plataforma possui RBAC com perfis gerais e especializações para manutenção e produção.

Perfil

Escopo principal

Superusuário

Administração global da plataforma e das organizações

Administrador

Usuários, configurações, assinatura e operação da organização

Gerente industrial

Visão estratégica da operação e indicadores globais

Supervisor de manutenção

Gestão do backlog, prioridades, equipes e desempenho

Liderança de manutenção

Coordenação técnica por área ou especialidade

Analista de manutenção

Planejamento, indicadores e análise de confiabilidade

Engenheiro de manutenção

Análise técnica e apoio à estratégia dos ativos

Técnico

Execução de OS, ocorrências, evidências e apontamentos

Liderança de produção

Acompanhamento dos ativos e impacto sobre a produção

Operador

Abertura de ocorrências e acompanhamento do setor

As permissões são organizadas por recurso e ação, permitindo controles como visualizar, criar, atualizar, aprovar, baixar estoque ou gerenciar usuários.

Tecnologias

Frontend

Tecnologia

Aplicação

React 19

Construção da interface e dos módulos operacionais

React Router 7

Navegação, rotas protegidas e layouts aninhados

Tailwind CSS 3

Estilização e design responsivo

Radix UI / shadcn/ui

Componentes acessíveis e reutilizáveis

Axios

Comunicação com a API e renovação de token

React Hook Form + Zod

Formulários e validação

Recharts

Dashboards e indicadores visuais

Sonner

Feedback e notificações de interface

Lucide React

Ícones da aplicação

Service Worker

Instalação PWA, cache e suporte offline

Backend

Tecnologia

Aplicação

Python 3.11+

Linguagem principal do backend

FastAPI 0.110

API REST e documentação OpenAPI

Uvicorn

Servidor ASGI

Pydantic 2

Contratos, validação e configurações

SQLAlchemy 2

Mapeamento e persistência de dados

PostgreSQL

Banco relacional principal

APScheduler

Tarefas e rotinas agendadas

ReportLab

Geração de documentos PDF

OpenPyXL

Exportação de planilhas Excel

Segurança, SaaS e observabilidade

Tecnologia

Aplicação

JWT / PyJWT

Access e refresh tokens

bcrypt

Hash de senhas

PyOTP

MFA baseado em TOTP

Authlib

Fluxos SSO/OIDC

SlowAPI

Rate limiting

Stripe

Checkout, assinaturas e webhooks

Sentry

Monitoramento de erros opcional

Prometheus Instrumentator

Métricas técnicas da API

Estrutura do projeto

Saas-PCM/
├── backend/
│   ├── server.py                    # Bootstrap da API e registro dos módulos
│   ├── requirements.txt             # Dependências Python
│   ├── tests/                       # Testes unitários e de segurança
│   └── app/
│       ├── config.py                # Planos, limites, enums e SLA
│       ├── database.py              # Engine e sessões SQLAlchemy
│       ├── deps.py                  # Dependências de autenticação e tenant
│       ├── settings.py              # Configuração centralizada por ambiente
│       ├── middleware/
│       │   ├── logging_config.py
│       │   ├── rate_limiter.py
│       │   ├── request_id.py
│       │   ├── security_headers.py
│       │   └── tenant.py
│       ├── models/
│       │   ├── core.py              # Entidades centrais do PCM
│       │   ├── estoque.py           # Entidades de almoxarifado
│       │   └── evidencias.py        # Anexos e checklists
│       ├── routers/                 # Endpoints separados por domínio
│       ├── schemas/                 # Schemas Pydantic
│       └── services/
│           ├── auth_service.py
│           ├── estoque_service.py
│           ├── mfa_service.py
│           ├── preditivo_service.py
│           ├── rbac_service.py
│           ├── realtime.py
│           ├── report_service.py
│           ├── scheduler.py
│           ├── sso_service.py
│           ├── storage_service.py
│           ├── tenant_service.py
│           └── whatsapp_service.py
│
├── frontend/
│   ├── public/
│   │   ├── manifest.json            # Metadados PWA
│   │   ├── service-worker.js        # Cache e experiência offline
│   │   └── icons/
│   ├── src/
│   │   ├── App.js                   # Rotas públicas e protegidas
│   │   ├── components/
│   │   │   ├── AppLayout.jsx
│   │   │   ├── shared/              # Componentes de negócio reutilizáveis
│   │   │   └── ui/                  # Biblioteca visual
│   │   ├── contexts/
│   │   │   ├── AuthContext.js
│   │   │   ├── RealtimeContext.jsx
│   │   │   └── ThemeContext.js
│   │   ├── hooks/
│   │   ├── lib/
│   │   │   ├── api.js               # Cliente HTTP e integrações da API
│   │   │   ├── offlineQueue.js      # Fila de operações offline
│   │   │   └── serviceWorkerRegistration.js
│   │   └── pages/                   # Páginas dos módulos da plataforma
│   ├── package.json
│   ├── tailwind.config.js
│   └── vercel.json
│
├── scripts/                         # Utilitários do projeto
├── test_reports/                    # Histórico de ciclos de teste
├── backend_test.py                  # Suite de integração da API
├── render.yaml                      # Deploy do backend
├── design_guidelines.json           # Diretrizes do design system
└── README.md

Instalação local

Pré-requisitos

Python 3.11 ou superior

Node.js 18 ou superior

Yarn 1.22 ou npm compatível

PostgreSQL local ou hospedado

Git

Integrações como Stripe, Sentry, SMTP, MFA e SSO são opcionais em desenvolvimento e dependem da configuração de cada ambiente.

1. Clonar o projeto

git clone <URL_DO_REPOSITORIO>
cd Saas-PCM

2. Criar o ambiente do backend

cd backend
python -m venv .venv

No Windows:

.venv\Scripts\activate

No Linux ou macOS:

source .venv/bin/activate

Instale as dependências:

pip install -r requirements.txt

3. Instalar o frontend

Em outro terminal:

cd frontend
yarn install

Também é possível utilizar:

npm install

Variáveis de ambiente

Backend — backend/.env

Use valores próprios e seguros. Nunca publique o arquivo real no Git.

# Ambiente
ENV=development

# Banco de dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/aurix

# Autenticação
JWT_SECRET=<CHAVE_ALEATORIA_COM_PELO_MENOS_32_CARACTERES>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7

# Frontend e CORS
FRONTEND_URL=http://localhost:3000
CORS_EXTRA_ORIGINS=

# MFA — opcional
MFA_ENCRYPTION_KEY=<CHAVE_FERNET>

# Stripe — opcional
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# E-mail — opcional
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@example.com

# Observabilidade — opcional
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1

Gere um segredo JWT seguro:

python -c "import secrets; print(secrets.token_hex(32))"

Gere uma chave para criptografia do MFA:

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Frontend — frontend/.env

REACT_APP_BACKEND_URL=http://localhost:8001

Execução e build

Backend em desenvolvimento

Execute a partir da pasta backend:

uvicorn server:app --reload --host 0.0.0.0 --port 8001

Serviços disponíveis:

Serviço

Endereço local

API

http://localhost:8001

Swagger UI

http://localhost:8001/docs

Health check

http://localhost:8001/health

Readiness check

http://localhost:8001/ready

A documentação Swagger é desabilitada automaticamente em ambiente de produção.

Frontend em desenvolvimento

Execute a partir da pasta frontend:

yarn start

A interface será iniciada, por padrão, em:

http://localhost:3000

Build de produção do frontend

yarn build

Execução do backend em produção

uvicorn server:app --host 0.0.0.0 --port $PORT

Testes

O backend possui testes voltados a autenticação, billing, isolamento multi-tenant, estoque, uploads, headers de segurança e regras do PCM.

Executar todos os testes unitários

A partir da raiz do projeto:

pytest backend/tests -v

Executar arquivos específicos

pytest backend/tests/test_auth_unit.py -v
pytest backend/tests/test_billing_unit.py -v
pytest backend/tests/test_estoque_unit.py -v
pytest backend/tests/test_security.py -v
pytest backend/tests/test_tenant_unit.py -v

Suite de integração da API

Com o backend em execução:

python backend_test.py

Para utilizar outro endereço de API:

AURIX_API_URL=http://localhost:8001/api python backend_test.py

A quantidade de testes não representa, por si só, cobertura integral. O roadmap prevê ampliar a cobertura automatizada do frontend, dos fluxos end-to-end e das integrações externas.

API e observabilidade

Documentação da API

Em desenvolvimento, o FastAPI disponibiliza uma interface OpenAPI interativa:

http://localhost:8001/docs

O README apresenta a visão de produto e arquitetura. A documentação detalhada de endpoints deve permanecer no Swagger/OpenAPI ou em arquivos específicos dentro de docs/, evitando transformar a página principal do repositório em uma lista extensa de rotas.

Health checks

Endpoint

Finalidade

GET /health

Verifica se o processo da aplicação está ativo

GET /ready

Verifica se a aplicação consegue acessar o banco de dados

Telemetria operacional

Request ID em todas as requisições

Logs configurados conforme o ambiente

Integração opcional com Sentry

Instrumentação preparada para Prometheus

Auditoria funcional separada dos logs técnicos

Deploy

A estrutura atual permite a publicação separada das duas camadas:

Camada

Estratégia presente no projeto

Frontend

Build React e configuração SPA compatível com Vercel

Backend

Serviço Python configurado para execução com Uvicorn

Banco

PostgreSQL local ou gerenciado, incluindo Supabase

O arquivo render.yaml contém uma configuração declarativa para o backend. O diretório frontend possui regras de rewrite para navegação SPA.

Em produção:

Configure todas as variáveis críticas no provedor de hospedagem

Utilize uma chave JWT exclusiva e forte

Não salve segredos no repositório

Restrinja as origens de CORS

Configure o webhook do Stripe com assinatura válida

Utilize HTTPS em todas as integrações

Configure backup e monitoramento do PostgreSQL

Habilite observabilidade e alertas operacionais

Roadmap

Engenharia e entrega

Pipeline CI/CD com lint, testes e build automatizado

Containerização completa com Docker e Docker Compose

Versionamento formal de migrations com Alembic

Cobertura automatizada do frontend

Testes end-to-end dos fluxos críticos

Análise estática e verificação de dependências no pipeline

Escalabilidade e observabilidade

Event bus distribuído para escalar eventos em tempo real horizontalmente

Dashboards de métricas Prometheus e alertas operacionais

Centralização de logs

Políticas automatizadas de backup e recuperação

Cache distribuído para consultas de alta frequência

Produto

Aplicativo ou experiência mobile especializada para técnicos

Leitura de QR Code para identificação de ativos

Scheduler configurável por organização

Relatórios personalizados por unidade e setor

Assinatura e validação digital de evidências

Evolução da análise preditiva com modelos baseados em histórico

Integrações industriais adicionais via API e webhooks

Competências demonstradas

O AURIX reúne desafios típicos de um produto empresarial e demonstra experiência prática em:

Desenvolvimento Full Stack com React e Python

Arquitetura modular de aplicações

Modelagem relacional com SQLAlchemy e PostgreSQL

Desenvolvimento e organização de APIs REST

Autenticação, autorização, RBAC, MFA e SSO

Arquitetura SaaS multi-tenant

Billing, feature flags e limites por assinatura

Processos industriais e regras de PCM

Dashboards e visualização de indicadores

Comunicação em tempo real com SSE

Aplicações PWA e estratégias offline

Geração de relatórios PDF e Excel

Integrações de pagamento e serviços externos

Segurança de APIs e proteção de dados

Auditoria, observabilidade e rastreabilidade

Testes automatizados e validação de regras de negócio

Deploy desacoplado de frontend e backend

Autor

<div align="center">

Marlos Gomes

Desenvolvedor Full Stack

Aplicações empresariais · APIs · Automação de processos · Cloud · UI/UX



</div>

Licença e confidencialidade

Este software possui licença proprietária.

AURIX © 2026. Todos os direitos reservados.

O código-fonte, a marca, os fluxos operacionais, os componentes visuais e a documentação não podem ser copiados, redistribuídos, sublicenciados ou utilizados comercialmente sem autorização expressa do responsável pelo projeto.

Dados reais de clientes, credenciais, segredos, chaves de API e demais informações sensíveis não fazem parte da documentação pública e devem permanecer protegidos por variáveis de ambiente e controles apropriados.

<div align="center">

AURIX

Manutenção inteligente. Operação confiável. Decisões orientadas por dados.

Desenvolvido por Marlos Gomes.

</div>
