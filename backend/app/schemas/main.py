"""
Schemas Pydantic para os modelos principais do AURIX.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from ..models.core import TipoOS, PrioridadeOS, StatusOS, TipoCusto, UserRole


class OrganizationCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    nome: str
    cnpj: Optional[str]
    plano: str
    limite_equipamentos: int
    limite_usuarios: int
    limite_os_mes: int
    ativo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    nome: str
    organization_nome: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    nome: str
    role: str
    setor: Optional[str] = None
    is_lider: bool = False
    employee_id: Optional[str] = None
    generic_session_sector: Optional[str] = None
    organization_id: str
    ativo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nome: str
    role: UserRole = UserRole.OPERADOR
    setor: Optional[str] = None
    is_lider: bool = False
    employee_id: Optional[str] = None


class TechnicianSessionRequest(BaseModel):
    sector: str
    employee_id: str


class TecnicoLoginRequest(BaseModel):
    senha_generica: str
    sector_id: str
    employee_id: str


class SetorCreate(BaseModel):
    nome: str
    senha_tecnico: str


class SetorResponse(BaseModel):
    id: str
    nome: str
    organization_id: str
    ativo: bool


class GrupoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None


class GrupoResponse(BaseModel):
    id: str
    nome: str
    descricao: Optional[str]
    organization_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SubgrupoCreate(BaseModel):
    grupo_id: str
    nome: str
    descricao: Optional[str] = None


class SubgrupoResponse(BaseModel):
    id: str
    grupo_id: str
    nome: str
    descricao: Optional[str]
    organization_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EquipamentoCreate(BaseModel):
    codigo: str
    nome: str
    descricao: Optional[str] = None
    localizacao: Optional[str] = None
    valor_hora: float = 0.0
    grupo_id: Optional[str] = None
    subgrupo_id: Optional[str] = None
    criticidade: int = 1
    parent_id: Optional[str] = None
    nivel: Optional[str] = "maquina"


class EquipamentoResponse(BaseModel):
    id: str
    codigo: str
    nome: str
    descricao: Optional[str]
    localizacao: Optional[str]
    valor_hora: float
    grupo_id: Optional[str]
    subgrupo_id: Optional[str]
    criticidade: int
    ativo: bool
    organization_id: str
    created_at: datetime
    parent_id: Optional[str] = None
    nivel: Optional[str] = "maquina"
    model_config = ConfigDict(from_attributes=True)


class OSCreate(BaseModel):
    equipamento_id: str
    grupo_id: Optional[str] = None
    subgrupo_id: Optional[str] = None
    tipo: TipoOS = TipoOS.CORRETIVA
    prioridade: PrioridadeOS = PrioridadeOS.MEDIA
    descricao: str
    falha_tipo: Optional[str] = None
    falha_modo: Optional[str] = None
    falha_causa: Optional[str] = None
    failure_group: Optional[str] = None
    solicitante_cracha: Optional[str] = None
    solicitante_nome: Optional[str] = None
    area_manutencao: Optional[str] = None
    subarea_manutencao: Optional[str] = None


class OSUpdate(BaseModel):
    status: Optional[StatusOS] = None
    tecnico_id: Optional[str] = None
    solucao: Optional[str] = None
    falha_tipo: Optional[str] = None
    falha_modo: Optional[str] = None
    falha_causa: Optional[str] = None
    failure_group: Optional[str] = None
    review_notes: Optional[str] = None
    relatorio_o_que_foi_realizado: Optional[str] = None
    relatorio_analise_problema: Optional[str] = None
    matricula_tecnico: Optional[str] = None
    area_tecnico: Optional[str] = None
    area_manutencao: Optional[str] = None
    subarea_manutencao: Optional[str] = None


class ColaboradorCreate(BaseModel):
    nome: str
    matricula: str
    cargo: Optional[str] = None
    setor: Optional[str] = None


class ColaboradorUpdate(BaseModel):
    nome: Optional[str] = None
    matricula: Optional[str] = None
    cargo: Optional[str] = None
    setor: Optional[str] = None
    ativo: Optional[bool] = None


class ColaboradorResponse(BaseModel):
    id: str
    nome: str
    matricula: str
    cargo: Optional[str] = None
    setor: Optional[str] = None
    ativo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OSHistoricoResponse(BaseModel):
    id: str
    os_id: str
    status_novo: str
    etapa_label: str
    timestamp: datetime
    user_id: Optional[str] = None
    user_nome: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class OSResponse(BaseModel):
    id: str
    numero: int
    equipamento_id: str
    equipamento_nome: Optional[str] = None
    equipamento_codigo: Optional[str] = None
    equipamento_localizacao: Optional[str] = None
    grupo_id: Optional[str]
    grupo_nome: Optional[str] = None
    subgrupo_id: Optional[str]
    tipo: str
    prioridade: str
    status: str
    descricao: str
    solucao: Optional[str]
    solicitante_id: str
    solicitante_nome: Optional[str] = None
    tecnico_id: Optional[str]
    tecnico_nome: Optional[str] = None
    tecnico_employee_id: Optional[str] = None
    technician_employee_id: Optional[str] = None
    revisor_id: Optional[str]
    revisor_nome: Optional[str] = None
    created_at: datetime
    inicio_atendimento: Optional[datetime]
    fim_atendimento: Optional[datetime]
    downtime_start: Optional[datetime] = None
    tempo_resposta: Optional[int]
    response_time_min: Optional[int] = None
    tempo_reparo: Optional[int]
    tempo_total: Optional[int]
    dentro_sla: bool
    falha_tipo: Optional[str]
    falha_modo: Optional[str]
    falha_causa: Optional[str]
    failure_group: Optional[str] = None
    reincidente: bool
    occurrences: Optional[str] = None
    occurrences_count: int = 0
    organization_id: str
    custo_parada: Optional[float] = None
    equipamento_setor: Optional[str] = None
    review_deadline: Optional[datetime] = None
    review_notes: Optional[str] = None
    auto_approved: bool = False
    solicitante_cracha: Optional[str] = None
    solicitante_user_id: Optional[str] = None
    relatorio_o_que_foi_realizado: Optional[str] = None
    relatorio_analise_problema: Optional[str] = None
    relatorio_preenchido_em: Optional[datetime] = None
    relatorio_preenchido_por_nome: Optional[str] = None
    custo_mao_obra: Optional[float] = None
    horas_trabalhadas: Optional[float] = None
    valor_hora_tecnico: Optional[float] = None
    area_manutencao: Optional[str] = None
    subarea_manutencao: Optional[str] = None
    excecoes_area_matriculas: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class OSExcecaoAreaResponse(BaseModel):
    id: str
    os_id: str
    matricula: str
    colaborador_nome: Optional[str] = None
    autorizado_por_nome: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OSEquipeCreate(BaseModel):
    cracha: Optional[str] = None
    nome_membro: Optional[str] = None
    especialidade: Optional[str] = None


class OSEquipeResponse(BaseModel):
    id: str
    os_id: str
    user_id: Optional[str] = None
    nome_membro: str
    cracha: Optional[str] = None
    especialidade: Optional[str] = None
    adicionado_em: datetime
    adicionado_por: Optional[str] = None
    adicionado_por_nome: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CustoMaoObraUpdate(BaseModel):
    horas_trabalhadas: float
    valor_hora_tecnico: float


class CustoCreate(BaseModel):
    ordem_servico_id: str
    tipo: TipoCusto
    descricao: str
    valor: float
    quantidade: float = 1.0


class CustoResponse(BaseModel):
    id: str
    ordem_servico_id: str
    tipo: str
    descricao: str
    valor: float
    quantidade: float
    organization_id: str
    criado_por: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PlanoCreate(BaseModel):
    equipamento_id: str
    nome: str
    descricao: Optional[str] = None
    frequencia_dias: int


class PlanoResponse(BaseModel):
    id: str
    equipamento_id: str
    nome: str
    descricao: Optional[str]
    frequencia_dias: int
    ultima_execucao: Optional[datetime]
    proxima_execucao: Optional[datetime]
    ativo: bool
    organization_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DashboardKPIs(BaseModel):
    total_os_mes: int
    os_abertas: int
    os_atrasadas: int
    mttr: float
    mtbf: float
    disponibilidade: float
    custo_total_mes: float
    custo_parada_mes: float
    avg_tempo_resposta: float
    preventiva_vs_corretiva: dict
    top_equipamentos_falhas: List[dict]
    top_equipamentos_custos: List[dict]
    top_equipamentos_downtime: List[dict]


class BillingPlanResponse(BaseModel):
    plano: str
    subscription_status: str
    limits: dict
    usage: dict
    usage_percent: dict


class CheckoutRequest(BaseModel):
    plan: str
    origin_url: str
