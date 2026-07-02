"""
Modelos SQLAlchemy centrais do AURIX.
Todos usam a Base canônica de app.database para que create_all unificado funcione.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPERUSUARIO = "superusuario"
    ADMIN = "admin"
    GERENTE_INDUSTRIAL = "gerente_industrial"
    SUPERVISOR_MANUTENCAO = "supervisor_manutencao"
    LIDER_MANUTENCAO_ELETRICA = "lider_manutencao_eletrica"
    LIDER_MANUTENCAO_MECANICA = "lider_manutencao_mecanica"
    ANALISTA_MANUTENCAO = "analista_manutencao"
    ENGENHEIRO_MANUTENCAO = "engenheiro_manutencao"
    LIDER = "lider"
    TECNICO = "tecnico"
    LIDER_PRODUCAO = "lider_producao"
    SUPERVISOR_PRODUCAO = "supervisor_producao"
    OPERADOR = "operador"


class TipoOS(str, enum.Enum):
    CORRETIVA = "corretiva"
    PREVENTIVA = "preventiva"
    PREDITIVA = "preditiva"


class PrioridadeOS(str, enum.Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class StatusOS(str, enum.Enum):
    ABERTA = "aberta"
    EM_ATENDIMENTO = "em_atendimento"
    AGUARDANDO_PECA = "aguardando_peca"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    REVISADA = "revisada"
    FECHADA = "fechada"


class TipoCusto(str, enum.Enum):
    CONSUMO = "consumo"
    SUBSTITUICAO = "substituicao"
    MAO_OBRA = "mao_obra"


class PlanoSaaS(str, enum.Enum):
    DEMO = "demo"
    ESSENCIAL = "essencial"
    PROFISSIONAL = "profissional"
    AVANCADO = "avancado"
    ENTERPRISE = "enterprise"


# ── Planos / feature flags ──────────────────────────────────────────────────────

PLAN_LIMITS = {
    PlanoSaaS.DEMO: {
        "label": "Demo", "price": 0.0, "preco_mensal": 0.0,
        "max_equipamentos": 5, "max_users": 3, "max_os_mes": 10,
        "stripe_price_id": None, "cta_tipo": "trial", "destaque": False,
        "relatorios": False, "grupos_subgrupos": False, "aprovacao_setor": False,
        "modulo_preditivo": False, "planos_preventivos": False, "api_iot": False,
        "notificacoes_email": False, "exportacao_pdf": False, "sso": False,
        "dashboard_avancado": False, "kanban": False,
        "modulo_estoque": False, "modulo_evidencias": False, "suporte": "none",
    },
    PlanoSaaS.ESSENCIAL: {
        "label": "Essencial", "price": 250.0, "preco_mensal": 250.0,
        "max_equipamentos": 20, "max_users": 10, "max_os_mes": 100,
        "stripe_price_id": "price_essencial_mensal", "cta_tipo": "stripe_checkout", "destaque": False,
        "relatorios": True, "grupos_subgrupos": True, "aprovacao_setor": True,
        "modulo_preditivo": False, "planos_preventivos": False, "api_iot": False,
        "notificacoes_email": True, "exportacao_pdf": False, "sso": False,
        "dashboard_avancado": False, "kanban": False,
        "modulo_estoque": False, "modulo_evidencias": False, "suporte": "email",
    },
    PlanoSaaS.PROFISSIONAL: {
        "label": "Profissional", "price": 490.0, "preco_mensal": 490.0,
        "max_equipamentos": 35, "max_users": 45, "max_os_mes": -1,
        "stripe_price_id": "price_profissional_mensal", "cta_tipo": "stripe_checkout", "destaque": True,
        "relatorios": True, "grupos_subgrupos": True, "aprovacao_setor": True,
        "modulo_preditivo": True, "max_equipamentos_preditivo": 10,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "exportacao_pdf": True, "sso": False,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "modulo_estoque": True, "modulo_evidencias": True, "suporte": "prioritario",
    },
    PlanoSaaS.AVANCADO: {
        "label": "Avançado", "price": 790.0, "preco_mensal": 790.0,
        "max_equipamentos": 50, "max_users": 100, "max_os_mes": -1,
        "stripe_price_id": "price_avancado_mensal", "cta_tipo": "stripe_checkout", "destaque": False,
        "relatorios": True, "relatorios_personalizados": True, "grupos_subgrupos": True,
        "aprovacao_setor": True, "modulo_preditivo": True, "max_equipamentos_preditivo": 30,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "notificacoes_whatsapp": True,
        "exportacao_pdf": True, "integracoes_basicas": True, "sso": False,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "analise_pareto": True,
        "modulo_estoque": True, "modulo_evidencias": True, "suporte": "prioritario",
    },
    PlanoSaaS.ENTERPRISE: {
        "label": "Enterprise", "price": 1290.0, "preco_mensal": 1290.0,
        "max_equipamentos": -1, "max_users": -1, "max_os_mes": -1,
        "stripe_price_id": None, "cta_tipo": "contato", "destaque": False,
        "relatorios": True, "relatorios_personalizados": True, "grupos_subgrupos": True,
        "aprovacao_setor": True, "modulo_preditivo": True, "max_equipamentos_preditivo": -1,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "notificacoes_whatsapp": True,
        "exportacao_pdf": True, "integracoes_avancadas": True, "sso": True,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "analise_pareto": True,
        "modulo_estoque": True, "modulo_evidencias": True,
        "onboarding_personalizado": True, "sla_customizado": True, "suporte": "dedicado",
    },
}


# ── Models ─────────────────────────────────────────────────────────────────────

_now = lambda: datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    cnpj = Column(String(20), unique=True, nullable=True)
    plano = Column(SQLEnum(PlanoSaaS), default=PlanoSaaS.DEMO)
    limite_equipamentos = Column(Integer, default=5)
    limite_usuarios = Column(Integer, default=3)
    limite_os_mes = Column(Integer, default=10)
    ativo = Column(Boolean, default=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), default="active")
    api_key = Column(String(64), nullable=True, unique=True)
    plano_trial_expira_em = Column(DateTime(timezone=True), nullable=True)
    contato_enterprise_solicitado = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nome = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.OPERADOR)
    setor = Column(String(100), nullable=True)
    is_lider = Column(Boolean, default=False)
    employee_id = Column(String(20), nullable=True)
    generic_session_sector = Column(String(100), nullable=True)
    ativo = Column(Boolean, default=True)
    valor_hora = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Subgrupo(Base):
    __tablename__ = "subgrupos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Equipamento(Base):
    __tablename__ = "equipamentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    localizacao = Column(String(255), nullable=True)
    valor_hora = Column(Float, default=0.0)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=True)
    subgrupo_id = Column(UUID(as_uuid=True), ForeignKey("subgrupos.id"), nullable=True)
    ativo = Column(Boolean, default=True)
    criticidade = Column(Integer, default=1)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=True)
    nivel = Column(String(20), nullable=True, default="maquina")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (Index("idx_equipamento_org", "organization_id"),)


class OrdemServico(Base):
    __tablename__ = "ordens_servico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=True)
    subgrupo_id = Column(UUID(as_uuid=True), ForeignKey("subgrupos.id"), nullable=True)
    tipo = Column(SQLEnum(TipoOS), default=TipoOS.CORRETIVA)
    prioridade = Column(SQLEnum(PrioridadeOS), default=PrioridadeOS.MEDIA)
    status = Column(SQLEnum(StatusOS), default=StatusOS.ABERTA)
    descricao = Column(Text, nullable=False)
    solucao = Column(Text, nullable=True)
    solicitante_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tecnico_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    inicio_atendimento = Column(DateTime(timezone=True), nullable=True)
    fim_atendimento = Column(DateTime(timezone=True), nullable=True)
    revisado_at = Column(DateTime(timezone=True), nullable=True)
    fechado_at = Column(DateTime(timezone=True), nullable=True)
    tempo_resposta = Column(Integer, nullable=True)
    tempo_reparo = Column(Integer, nullable=True)
    tempo_total = Column(Integer, nullable=True)
    dentro_sla = Column(Boolean, default=True)
    falha_tipo = Column(String(100), nullable=True)
    falha_modo = Column(String(100), nullable=True)
    falha_causa = Column(String(100), nullable=True)
    failure_group = Column(String(50), nullable=True)
    reincidente = Column(Boolean, default=False)
    bloco_parada_id = Column(UUID(as_uuid=True), nullable=True)
    downtime_start = Column(DateTime(timezone=True), nullable=True)
    occurrences = Column(Text, nullable=True)
    technician_employee_id = Column(String(20), nullable=True)
    area_manutencao = Column(String(50), nullable=True)
    subarea_manutencao = Column(String(80), nullable=True)
    review_deadline = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    auto_approved = Column(Boolean, default=False)
    solicitante_cracha = Column(String(30), nullable=True)
    solicitante_nome = Column(String(200), nullable=True)
    solicitante_user_id = Column(UUID(as_uuid=True), nullable=True)
    relatorio_o_que_foi_realizado = Column(Text, nullable=True)
    relatorio_analise_problema = Column(Text, nullable=True)
    relatorio_preenchido_em = Column(DateTime(timezone=True), nullable=True)
    relatorio_preenchido_por = Column(UUID(as_uuid=True), nullable=True)
    custo_mao_obra = Column(Float, nullable=True)
    horas_trabalhadas = Column(Float, nullable=True)
    valor_hora_tecnico = Column(Float, nullable=True)
    custo_total_pecas = Column(Float, nullable=True, default=0)
    assinatura_hash = Column(String(64), nullable=True)
    assinado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assinado_em = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=True)

    __table_args__ = (Index("idx_os_org", "organization_id"),)


class CustoOS(Base):
    __tablename__ = "custos_os"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    ordem_servico_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id"), nullable=False)
    tipo = Column(SQLEnum(TipoCusto), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Float, nullable=False)
    quantidade = Column(Float, default=1.0)
    criado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Setor(Base):
    __tablename__ = "setores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    senha_tecnico_hash = Column(String(255), nullable=False)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_setor_org", "organization_id"),)


class PlanoPreventivo(Base):
    __tablename__ = "planos_preventivos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    frequencia_dias = Column(Integer, nullable=False)
    ultima_execucao = Column(DateTime(timezone=True), nullable=True)
    proxima_execucao = Column(DateTime(timezone=True), nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class AuditoriaLog(Base):
    __tablename__ = "auditoria_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    entidade = Column(String(100), nullable=False)
    entidade_id = Column(UUID(as_uuid=True), nullable=False)
    acao = Column(String(50), nullable=False)
    dados_anteriores = Column(Text, nullable=True)
    dados_novos = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String(255), nullable=False, index=True)
    attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    plan = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="usd")
    payment_status = Column(String(50), default="pending")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class OSEquipe(Base):
    __tablename__ = "os_equipe"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    nome_membro = Column(String(200), nullable=False)
    cracha = Column(String(30), nullable=True)
    especialidade = Column(String(100), nullable=True)
    adicionado_em = Column(DateTime(timezone=True), default=_now)
    adicionado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class Colaborador(Base):
    __tablename__ = "colaboradores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    matricula = Column(String(30), nullable=False)
    cargo = Column(String(100), nullable=True)
    setor = Column(String(100), nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_colaboradores_org", "organization_id"),)


class OSHistorico(Base):
    __tablename__ = "os_historico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id"), nullable=False)
    status_novo = Column(String(50), nullable=False)
    etapa_label = Column(String(200), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_now)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_nome = Column(String(200), nullable=True)

    __table_args__ = (Index("idx_os_historico_os", "os_id"),)


class OSExcecaoArea(Base):
    __tablename__ = "os_excecoes_area"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False)
    matricula = Column(String(30), nullable=False)
    colaborador_nome = Column(String(200), nullable=True)
    autorizado_por_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    autorizado_por_nome = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    destinatario_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tipo = Column(String(50), nullable=False)
    titulo = Column(String(255), nullable=False)
    mensagem = Column(Text, nullable=False)
    os_id = Column(UUID(as_uuid=True), nullable=True)
    lida = Column(Boolean, default=False)
    criada_em = Column(DateTime(timezone=True), default=_now)
    lida_em = Column(DateTime(timezone=True), nullable=True)


class ConfiguracaoMonitoramento(Base):
    __tablename__ = "configuracoes_monitoramento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    unidade = Column(String(20), nullable=True)
    threshold_atencao = Column(Float, nullable=False)
    threshold_critico = Column(Float, nullable=False)
    tendencia_janela_dias = Column(Integer, default=7)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class LeituraSensor(Base):
    __tablename__ = "leituras_sensor"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    valor = Column(Float, nullable=False)
    unidade = Column(String(20), nullable=True)
    fonte = Column(String(50), default="manual")
    registrado_por = Column(UUID(as_uuid=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_now)
    processado = Column(Boolean, default=False)


class AlertaPreditivo(Base):
    __tablename__ = "alertas_preditivos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    severidade = Column(String(20), nullable=False)
    valor_atual = Column(Float, nullable=False)
    threshold_violado = Column(Float, nullable=False)
    tendencia = Column(String(20), default="ESTAVEL")
    rul_estimado_dias = Column(Integer, nullable=True)
    descricao = Column(Text, nullable=False)
    status = Column(String(20), default="ABERTO")
    os_gerada_id = Column(UUID(as_uuid=True), nullable=True)
    ignorado_por = Column(UUID(as_uuid=True), nullable=True)
    motivo_ignorado = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), default=_now)
    resolvido_em = Column(DateTime(timezone=True), nullable=True)
