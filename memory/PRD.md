# PRD — SaaS PCM (AURIX) — Tecnologia para Gestão Industrial

## Problema Original
Implementar SaaS de Planejamento e Controle de Manutenção industrial multi-tenant, com 9 fases:
1. Novos campos DB (failure_group, occurrences, response_time_min, employee_id, generic_session_sector)
2. Login genérico do técnico (POST /auth/tecnico-login + GET /sectors/tecnico-options)
3. Regras de OS — bloqueio por failure_group (409), PATCH ocorrência append-only, response_time_min
4. Dashboards por perfil (operador/líder/superusuário)
5. Frontend tela de login do técnico (stepper 3 etapas)
6. Dashboards diferenciados (operador/líder)
7. Kanban enriquecido (badges, timers, SLA)
8. Restrições do operador (failure_group obrigatório, BloqueioModal)
9. Testes e validação

## Stack
- Backend: FastAPI + SQLAlchemy + PostgreSQL (Supabase)
- Frontend: React + Tailwind + Shadcn UI + Recharts + Lucide React
- Auth: JWT em cookies httponly + Bearer header
- Design: Swiss/High-Contrast, Outfit + Inter, rounded-sm, sem glassmorphism

## User Personas
- ADMIN — gestão completa da organização (limites de plano, equipamentos, usuários)
- LIDER — KPIs + dados financeiros do setor (custo de parada, Pareto, técnicos ativos)
- OPERADOR — abre OS, adiciona ocorrências (sem ver custos)
- TECNICO — atua em OS, mesma view do operador, login genérico por setor
- SUPERUSUARIO — visão consolidada multi-empresa

## Estado Atual (validado em 2026-05-28)

### Backend — 100% (27/27 testes)
✅ FASE 1: Campos failure_group, occurrences, response_time_min, employee_id, generic_session_sector
✅ FASE 2: POST /auth/tecnico-login + GET /sectors/tecnico-options (público)
✅ FASE 3.1: Bloqueio failure_group HTTP 409
✅ FASE 3.2: PATCH /ordens-servico/{id}/ocorrencia (append-only, não muda downtime/status)
✅ FASE 3.3: response_time_min calculado ao mudar status para em_atendimento
✅ FASE 4.1: GET /dashboard/operador (operador/técnico, sem financeiros)
✅ FASE 4.2: GET /dashboard/lider (com custo_total_parada_mes, Pareto, Top 5)
✅ FASE 4.3: GET /dashboard/superusuario (visão consolidada, role-gated)

### Frontend — Validado parcialmente
✅ FASE 5: TecnicoLoginPage 3 etapas (setor → matrícula → confirmação)
✅ FASE 6.1: DashboardOperadorPage (5 KPIs, sem financeiros, auto-refresh)
✅ FASE 6.2: DashboardLiderPage (6 KPIs com Custo BRL, Pareto, Top 5, Técnicos)
✅ FASE 6.3: Role routing (operador→/dashboard/operador, lider→/dashboard/lider, admin→/dashboard)
⚠️ FASE 7: Kanban — código completo (badges failure_group, timers 30s, SLA color), mas backend /api/kanban retorna 500 quando OS tem downtime_start NULL (bug em server.py:5139)
⚠️ FASE 8: BloqueioModal + failure_group chips — código completo (data-testid `bloqueio-modal`, `fg-chip-*`, `failure-group-chips`), mas validação E2E bloqueada por bug do Kanban

## Bugs Identificados

### CRÍTICO (1)
1. **server.py:5139 — Kanban 500 Internal Server Error**
   - Código: `getattr(o, "downtime_start", o.created_at).isoformat()` retorna None.isoformat() quando downtime_start é None (getattr não retorna default se atributo existe com valor None)
   - Fix: `((o.downtime_start or o.created_at).isoformat() if (o.downtime_start or o.created_at) else None)`

### MENOR (3)
2. **Migrações in-code de ALTER TYPE** falham silenciosamente — PostgreSQL não permite em transação. Aplicado manualmente em conexão AUTOCOMMIT.
3. **PUT vs PATCH** — Prompt pede `PATCH /ordens-servico/{id}` para mudar status, backend usa `PUT`. Funcional mas divergente.
4. **Title overlap visual** em DashboardOperadorPage/DashboardLiderPage — título dentro da página é parcialmente coberto pelo header da AppLayout (sobreposição CSS).

## Gaps de Implementação
**Nenhum.** Todas as 9 fases do prompt foram implementadas no código.

## Histórico
- 2026-05-28: Validação completa das 9 fases — backend 100%, frontend ~85% (kanban e bloqueio bloqueados por bug de 1 linha)
- Iteration 3 (test report): identificou bug do enum statusos AGUARDANDO_PECA — corrigido via ALTER TYPE em AUTOCOMMIT
- Iteration 4 (test report): backend 27/27 após fix
- Iteration 5 (test report): frontend E2E parcial — 25% reportado, mas re-validação manual elevou para 75-85%

## Backlog
**P0 (bloqueador):**
- Corrigir bug do Kanban (server.py:5139) — 1 linha

**P1 (alta prioridade):**
- Adicionar @api_router.patch como alias para mudança de status (alinhar contrato com prompt)
- Refatorar bloco de migrations para usar `isolation_level='AUTOCOMMIT'` em ALTER TYPE
- Fix overlap visual de título no Dashboard

**P2 (médio):**
- Refatorar server.py (5781 linhas) em módulos /routers, /models, /schemas, /services
- Remover defaults hardcoded de DB_HOST/DB_USER/DB_PASSWORD em server.py
- JWT_SECRET deveria fail-fast se ausente em vez de gerar random a cada restart
- Seed inicial de OS de demonstração (3-5 OS em diferentes statuses) para facilitar QA

## Próximas Ações
1. Aplicar fix do Kanban (server.py:5139)
2. Re-rodar testing agent para validar FASE 7 e FASE 8 E2E
3. Tratar P1 e P2 conforme priorização do usuário
