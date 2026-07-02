"""
SQL migrations idempotentes — rodadas uma vez no startup.
DDL normal vai em _DDL; ALTER TYPE (PostgreSQL enum) precisa de AUTOCOMMIT.
"""

DDL = [
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS api_key VARCHAR(64) UNIQUE",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS plano_trial_expira_em TIMESTAMPTZ",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contato_enterprise_solicitado BOOLEAN DEFAULT FALSE",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS setor VARCHAR(100)",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS monitoramento_ativo BOOLEAN DEFAULT FALSE",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS status_saude VARCHAR(20) DEFAULT 'NORMAL'",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS rul_estimado_dias INTEGER",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS mttr_horas FLOAT",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS mtbf_horas FLOAT",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS disponibilidade_percent FLOAT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS generic_session_sector VARCHAR(100)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS valor_hora FLOAT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS downtime_start TIMESTAMPTZ",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS occurrences TEXT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS technician_employee_id VARCHAR(20)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS failure_group VARCHAR(50)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS solicitante_cracha VARCHAR(30)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS solicitante_nome VARCHAR(200)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS solicitante_user_id UUID",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS relatorio_o_que_foi_realizado TEXT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS relatorio_analise_problema TEXT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS relatorio_preenchido_em TIMESTAMPTZ",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS relatorio_preenchido_por UUID",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS custo_mao_obra FLOAT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS horas_trabalhadas FLOAT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS valor_hora_tecnico FLOAT",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS area_manutencao VARCHAR(50)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS subarea_manutencao VARCHAR(80)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS custo_total_pecas FLOAT DEFAULT 0",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS assinatura_hash VARCHAR(64)",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS assinado_por UUID",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS assinado_em TIMESTAMPTZ",
    "ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    "ALTER TABLE custos_os ADD COLUMN IF NOT EXISTS criado_por UUID REFERENCES users(id)",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES equipamentos(id)",
    "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS nivel VARCHAR(20) DEFAULT 'maquina'",
    "CREATE INDEX IF NOT EXISTS idx_equip_parent ON equipamentos (parent_id)",
    """CREATE TABLE IF NOT EXISTS setores (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES organizations(id),
        nome VARCHAR(100) NOT NULL,
        senha_tecnico_hash VARCHAR(255) NOT NULL,
        ativo BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_setor_org ON setores (organization_id)",
    """CREATE TABLE IF NOT EXISTS os_equipe (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        os_id UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
        user_id UUID REFERENCES users(id),
        nome_membro VARCHAR(200) NOT NULL,
        cracha VARCHAR(30), especialidade VARCHAR(100),
        adicionado_em TIMESTAMPTZ DEFAULT now(),
        adicionado_por UUID REFERENCES users(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_os_equipe_os ON os_equipe (os_id)",
    """CREATE TABLE IF NOT EXISTS os_historico (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        os_id UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
        status_novo VARCHAR(50) NOT NULL,
        etapa_label VARCHAR(200) NOT NULL,
        timestamp TIMESTAMPTZ DEFAULT now(),
        user_id UUID REFERENCES users(id),
        user_nome VARCHAR(200)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_os_historico_os ON os_historico (os_id)",
    """CREATE TABLE IF NOT EXISTS colaboradores (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        nome VARCHAR(200) NOT NULL, matricula VARCHAR(30) NOT NULL,
        cargo VARCHAR(100), setor VARCHAR(100),
        ativo BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_colaboradores_org ON colaboradores (organization_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_colaboradores_org_matricula ON colaboradores (organization_id, matricula) WHERE ativo = TRUE",
    """CREATE TABLE IF NOT EXISTS os_excecoes_area (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        os_id UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
        matricula VARCHAR(30) NOT NULL, colaborador_nome VARCHAR(200),
        autorizado_por_id UUID REFERENCES users(id),
        autorizado_por_nome VARCHAR(200),
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(os_id, matricula)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_os_excecoes_area_os ON os_excecoes_area (os_id)",
    # Fase 5.2 — MFA TOTP
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_backup_codes TEXT",  # JSON array de hashes
    # Fase 5.1 — SSO OIDC
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_provider VARCHAR(20)",     # google|azure|saml
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS oidc_client_id TEXT",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS oidc_client_secret TEXT",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS oidc_discovery_url TEXT",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS saml_metadata_url TEXT",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sso_required BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_sub VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_provider VARCHAR(20)",
    # Fase 5.3 — RBAC customizável
    """CREATE TABLE IF NOT EXISTS papeis (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        nome VARCHAR(80) NOT NULL,
        descricao TEXT,
        is_preset BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(organization_id, nome)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_papeis_org ON papeis (organization_id)",
    """CREATE TABLE IF NOT EXISTS permissoes (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        recurso VARCHAR(80) NOT NULL,
        acao VARCHAR(40) NOT NULL,
        descricao TEXT,
        UNIQUE(recurso, acao)
    )""",
    """CREATE TABLE IF NOT EXISTS papel_permissoes (
        papel_id UUID NOT NULL REFERENCES papeis(id) ON DELETE CASCADE,
        permissao_id UUID NOT NULL REFERENCES permissoes(id) ON DELETE CASCADE,
        PRIMARY KEY(papel_id, permissao_id)
    )""",
    """CREATE TABLE IF NOT EXISTS usuario_papeis (
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        papel_id UUID NOT NULL REFERENCES papeis(id) ON DELETE CASCADE,
        granted_at TIMESTAMPTZ DEFAULT now(),
        granted_by UUID REFERENCES users(id),
        PRIMARY KEY(user_id, papel_id)
    )""",
    # Fase 5.5 — LGPD
    """CREATE TABLE IF NOT EXISTS lgpd_consentimentos (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        organization_id UUID NOT NULL REFERENCES organizations(id),
        finalidade VARCHAR(100) NOT NULL,
        consentiu BOOLEAN NOT NULL,
        ip VARCHAR(45),
        user_agent TEXT,
        registrado_em TIMESTAMPTZ DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_lgpd_consent_user ON lgpd_consentimentos (user_id)",
    """CREATE TABLE IF NOT EXISTS lgpd_solicitacoes (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id),
        organization_id UUID NOT NULL REFERENCES organizations(id),
        tipo VARCHAR(30) NOT NULL,   -- exportacao | exclusao | retificacao
        status VARCHAR(20) DEFAULT 'pendente',
        solicitado_em TIMESTAMPTZ DEFAULT now(),
        processado_em TIMESTAMPTZ,
        resposta TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_lgpd_sol_user ON lgpd_solicitacoes (user_id)",
    # WhatsApp opt-in
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_numero VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_optin BOOLEAN DEFAULT FALSE",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_api_token TEXT",
]

ALTER_TYPES = [
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'superusuario' BEFORE 'admin'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'gerente_industrial'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'supervisor_manutencao'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'lider_manutencao_eletrica'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'lider_manutencao_mecanica'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'analista_manutencao'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'engenheiro_manutencao'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'lider_producao'",
    "ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'supervisor_producao'",
    "ALTER TYPE statusos ADD VALUE IF NOT EXISTS 'aguardando_peca' BEFORE 'aguardando_revisao'",
]
