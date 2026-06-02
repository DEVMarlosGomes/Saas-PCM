import { useState, useEffect, useRef } from "react";
import {
  getEquipamentos,
  createEquipamento,
  updateEquipamento,
  deleteEquipamento,
  getGrupos,
  getEquipamentoHistorico,
} from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import {
  useFinancialAccess,
  BlurredMoney,
} from "../components/shared/FinancialGuard";
import UpgradeDialog from "../components/UpgradeDialog";
import { useUpgradeDialog } from "../hooks/useUpgradeDialog";
import {
  Plus,
  Search,
  Settings,
  MapPin,
  DollarSign,
  Activity,
  History,
  AlertTriangle,
  TrendingDown,
  Clock,
  Wrench,
  Loader2,
  X,
  MoreVertical,
  Pencil,
  Trash2,
} from "lucide-react";

const criticidadeConfig = {
  1: { label: "Muito Baixa", color: "bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/15" },
  2: { label: "Baixa", color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/15" },
  3: { label: "Média", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/15" },
  4: { label: "Alta", color: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/15" },
  5: { label: "Crítica", color: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/15" },
};

const EDIT_ROLES = ["admin", "gerente_industrial", "supervisor_manutencao"];
const DELETE_ROLES = ["admin"];

export default function EquipamentosPage() {
  const { user } = useAuth();
  const { upgradeOpen, upgradeMessage, handleApiError, closeUpgrade } = useUpgradeDialog();
  const finAccess = useFinancialAccess();

  const [equipamentos, setEquipamentos] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Novo equipamento
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    codigo: "", nome: "", descricao: "", localizacao: "", valor_hora: "", grupo_id: "", criticidade: "3",
  });

  // Edição
  const [editDialog, setEditDialog] = useState({ open: false, eq: null });
  const [editForm, setEditForm] = useState({
    nome: "", descricao: "", localizacao: "", valor_hora: "", criticidade: "3", grupo_id: "",
  });
  const [editSaving, setEditSaving] = useState(false);

  // Exclusão
  const [deleteDialog, setDeleteDialog] = useState({ open: false, eq: null });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  // Histórico
  const [historyDialog, setHistoryDialog] = useState({ open: false, data: null, loading: false });

  // Dropdown de ações por card
  const [openMenuId, setOpenMenuId] = useState(null);
  const menuRef = useRef(null);

  const canEdit = EDIT_ROLES.includes(user?.role);
  const canDelete = DELETE_ROLES.includes(user?.role);
  const canCreate = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const [eqRes, grRes] = await Promise.all([getEquipamentos(), getGrupos()]);
      setEquipamentos(eqRes.data);
      setGrupos(grRes.data);
    } catch {
      toast.error("Erro ao carregar equipamentos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // Fecha o menu ao clicar fora
  useEffect(() => {
    if (!openMenuId) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [openMenuId]);

  // ─── Criar ────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.codigo || !formData.nome) {
      toast.error("Preencha código e nome");
      return;
    }
    try {
      await createEquipamento({
        ...formData,
        valor_hora: parseFloat(formData.valor_hora) || 0,
        criticidade: parseInt(formData.criticidade),
        grupo_id: formData.grupo_id || null,
      });
      toast.success("Equipamento criado com sucesso");
      setDialogOpen(false);
      resetForm();
      loadData();
    } catch (error) {
      if (!handleApiError(error)) {
        toast.error(error.response?.data?.detail || "Erro ao criar equipamento");
      }
    }
  };

  const resetForm = () => {
    setFormData({ codigo: "", nome: "", descricao: "", localizacao: "", valor_hora: "", grupo_id: "", criticidade: "3" });
  };

  // ─── Editar ───────────────────────────────────────────────
  const openEdit = (eq) => {
    setOpenMenuId(null);
    setEditForm({
      nome: eq.nome || "",
      descricao: eq.descricao || "",
      localizacao: eq.localizacao || "",
      valor_hora: eq.valor_hora != null ? String(eq.valor_hora) : "",
      criticidade: String(eq.criticidade || 3),
      grupo_id: eq.grupo_id || "",
    });
    setEditDialog({ open: true, eq });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editForm.nome) {
      toast.error("Nome é obrigatório");
      return;
    }
    setEditSaving(true);
    try {
      await updateEquipamento(editDialog.eq.id, {
        codigo: editDialog.eq.codigo,
        nome: editForm.nome,
        descricao: editForm.descricao || null,
        localizacao: editForm.localizacao || null,
        valor_hora: parseFloat(editForm.valor_hora) || 0,
        criticidade: parseInt(editForm.criticidade),
        grupo_id: editForm.grupo_id || null,
        subgrupo_id: editDialog.eq.subgrupo_id || null,
      });
      toast.success("Equipamento atualizado com sucesso");
      setEditDialog({ open: false, eq: null });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao atualizar equipamento");
    } finally {
      setEditSaving(false);
    }
  };

  // ─── Excluir ──────────────────────────────────────────────
  const openDelete = (eq) => {
    setOpenMenuId(null);
    setDeleteError(null);
    setDeleteDialog({ open: true, eq });
  };

  const handleDelete = async () => {
    if (!deleteDialog.eq) return;
    setDeleteLoading(true);
    setDeleteError(null);
    try {
      await deleteEquipamento(deleteDialog.eq.id);
      toast.success("Equipamento excluído com sucesso");
      setDeleteDialog({ open: false, eq: null });
      loadData();
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (error.response?.status === 409 && detail?.error === "equipamento_com_os_ativa") {
        setDeleteError(detail.message);
      } else {
        toast.error(detail?.message || detail || "Erro ao excluir equipamento");
        setDeleteDialog({ open: false, eq: null });
      }
    } finally {
      setDeleteLoading(false);
    }
  };

  // ─── Histórico ────────────────────────────────────────────
  const handleViewHistory = async (equipamento) => {
    setHistoryDialog({ open: true, data: null, loading: true });
    try {
      const res = await getEquipamentoHistorico(equipamento.id);
      setHistoryDialog({ open: true, data: res.data, loading: false });
    } catch {
      toast.error("Erro ao carregar histórico");
      setHistoryDialog({ open: false, data: null, loading: false });
    }
  };

  const filteredEquipamentos = equipamentos.filter((eq) =>
    eq.codigo.toLowerCase().includes(search.toLowerCase()) ||
    eq.nome.toLowerCase().includes(search.toLowerCase())
  );

  const totalRevenuaRisk = equipamentos.reduce((acc, eq) => acc + (eq.valor_hora || 0), 0);

  return (
    <div className="space-y-6" data-testid="equipamentos-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Settings className="h-6 w-6 text-primary" />
            Equipamentos
          </h1>
          <p className="text-muted-foreground text-sm mt-1 flex items-center gap-1.5">
            {equipamentos.length} ativos •{" "}
            {finAccess === "full" ? (
              <span>R$ {totalRevenuaRisk.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}/h em risco</span>
            ) : (
              <><BlurredMoney /><span>/h em risco</span></>
            )}
          </p>
        </div>
        {canCreate && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-lg h-10 shadow-lg shadow-primary/20" data-testid="new-equipamento-btn">
                <Plus className="h-4 w-4 mr-2" />
                Novo Equipamento
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-xl">
              <DialogHeader>
                <DialogTitle className="font-heading">Novo Equipamento</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="codigo">Código *</Label>
                    <Input
                      id="codigo"
                      value={formData.codigo}
                      onChange={(e) => setFormData({ ...formData, codigo: e.target.value })}
                      placeholder="EQ-001"
                      className="rounded-lg h-10"
                      data-testid="equipamento-codigo-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="criticidade">Criticidade</Label>
                    <Select
                      value={formData.criticidade}
                      onValueChange={(v) => setFormData({ ...formData, criticidade: v })}
                    >
                      <SelectTrigger className="rounded-lg h-10" data-testid="equipamento-criticidade-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(criticidadeConfig).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{k} - {v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="nome">Nome *</Label>
                  <Input
                    id="nome"
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    placeholder="Prensa Hidráulica"
                    className="rounded-lg h-10"
                    data-testid="equipamento-nome-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="descricao">Descrição</Label>
                  <Input
                    id="descricao"
                    value={formData.descricao}
                    onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                    placeholder="Descrição do equipamento"
                    className="rounded-lg h-10"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="localizacao">Localização</Label>
                    <Input
                      id="localizacao"
                      value={formData.localizacao}
                      onChange={(e) => setFormData({ ...formData, localizacao: e.target.value })}
                      placeholder="Setor A"
                      className="rounded-lg h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="valor_hora" className="flex items-center gap-1.5">
                      <DollarSign className="h-3.5 w-3.5 text-red-500" />
                      Receita/Hora Parada (R$)
                    </Label>
                    <Input
                      id="valor_hora"
                      type="number"
                      step="0.01"
                      value={formData.valor_hora}
                      onChange={(e) => setFormData({ ...formData, valor_hora: e.target.value })}
                      placeholder="500.00"
                      className="rounded-lg h-10"
                    />
                    <p className="text-[11px] text-muted-foreground">Quanto a empresa perde por hora com a máquina parada</p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="grupo">Grupo</Label>
                  <Select
                    value={formData.grupo_id}
                    onValueChange={(v) => setFormData({ ...formData, grupo_id: v })}
                  >
                    <SelectTrigger className="rounded-lg h-10">
                      <SelectValue placeholder="Selecione um grupo" />
                    </SelectTrigger>
                    <SelectContent>
                      {grupos.map((g) => (
                        <SelectItem key={g.id} value={g.id}>{g.nome}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="rounded-lg">
                    Cancelar
                  </Button>
                  <Button type="submit" className="rounded-lg" data-testid="save-equipamento-btn">
                    Salvar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por código ou nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 h-10 rounded-lg bg-card"
          data-testid="search-equipamentos-input"
        />
      </div>

      {/* Equipment Cards */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : filteredEquipamentos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Settings className="h-10 w-10 mb-3 opacity-40" />
          <p className="font-medium">Nenhum equipamento encontrado</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
          {filteredEquipamentos.map((eq) => {
            const crit = criticidadeConfig[eq.criticidade] || criticidadeConfig[3];
            const menuOpen = openMenuId === eq.id;
            return (
              <div
                key={eq.id}
                className="border border-border/50 rounded-xl bg-card p-5 card-hover group"
                data-testid={`equipamento-card-${eq.codigo}`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{eq.codigo}</span>
                      <Badge className={`${crit.color} text-[10px] border`}>
                        {crit.label}
                      </Badge>
                    </div>
                    <h3 className="font-heading font-semibold text-base mt-1.5 truncate">{eq.nome}</h3>
                    {eq.descricao && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">{eq.descricao}</p>
                    )}
                  </div>

                  {/* Menu de ações */}
                  {(canEdit || canDelete) && (
                    <div className="relative ml-2 shrink-0" ref={menuOpen ? menuRef : null}>
                      <button
                        onClick={() => setOpenMenuId(menuOpen ? null : eq.id)}
                        className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                        data-testid={`equipamento-menu-${eq.codigo}`}
                        aria-label="Ações do equipamento"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                      {menuOpen && (
                        <div className="absolute right-0 top-8 z-50 min-w-[140px] rounded-lg border border-border bg-card shadow-lg py-1 animate-fade-in">
                          {canEdit && (
                            <button
                              onClick={() => openEdit(eq)}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                              data-testid={`equipamento-edit-${eq.codigo}`}
                            >
                              <Pencil className="h-3.5 w-3.5 text-primary" />
                              Editar
                            </button>
                          )}
                          {canDelete && (
                            <button
                              onClick={() => openDelete(eq)}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-red-500/10 hover:text-red-500 transition-colors text-left"
                              data-testid={`equipamento-delete-${eq.codigo}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              Excluir
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="space-y-2 text-sm">
                  {eq.localizacao && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{eq.localizacao}</span>
                    </div>
                  )}
                </div>

                {/* Revenue Impact */}
                <div className={`mt-4 p-3 rounded-lg ${eq.valor_hora > 0 ? "bg-red-500/5 border border-red-500/10" : "bg-muted/50"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
                      <TrendingDown className="h-3.5 w-3.5 text-red-500" />
                      Impacto/Hora Parada
                    </span>
                    <span className={`text-lg font-bold font-heading ${eq.valor_hora > 0 ? "text-red-500" : "text-muted-foreground"}`}>
                      {eq.valor_hora > 0 ? (
                        finAccess === "full"
                          ? `R$ ${eq.valor_hora.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                          : <BlurredMoney size="md" color="red" />
                      ) : (
                        "Não definido"
                      )}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-4 flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 rounded-lg h-9 text-xs"
                    onClick={() => handleViewHistory(eq)}
                    data-testid={`view-history-${eq.codigo}`}
                  >
                    <History className="h-3.5 w-3.5 mr-1.5" />
                    Histórico
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Modal de Edição ─────────────────────────────────── */}
      <Dialog open={editDialog.open} onOpenChange={(v) => { if (!v) setEditDialog({ open: false, eq: null }); }}>
        <DialogContent className="rounded-xl">
          <DialogHeader>
            <DialogTitle className="font-heading">
              Editar Equipamento
              {editDialog.eq && (
                <span className="ml-2 font-mono text-sm font-normal text-muted-foreground">
                  {editDialog.eq.codigo}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-nome">Nome *</Label>
              <Input
                id="edit-nome"
                value={editForm.nome}
                onChange={(e) => setEditForm({ ...editForm, nome: e.target.value })}
                placeholder="Nome do equipamento"
                className="rounded-lg h-10"
                data-testid="edit-equipamento-nome"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-descricao">Descrição</Label>
              <Input
                id="edit-descricao"
                value={editForm.descricao}
                onChange={(e) => setEditForm({ ...editForm, descricao: e.target.value })}
                placeholder="Descrição do equipamento"
                className="rounded-lg h-10"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-localizacao">Localização / Setor</Label>
                <Input
                  id="edit-localizacao"
                  value={editForm.localizacao}
                  onChange={(e) => setEditForm({ ...editForm, localizacao: e.target.value })}
                  placeholder="Setor A"
                  className="rounded-lg h-10"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-valor-hora" className="flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5 text-red-500" />
                  Receita/Hora (R$)
                </Label>
                <Input
                  id="edit-valor-hora"
                  type="number"
                  step="0.01"
                  value={editForm.valor_hora}
                  onChange={(e) => setEditForm({ ...editForm, valor_hora: e.target.value })}
                  placeholder="500.00"
                  className="rounded-lg h-10"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Criticidade</Label>
                <Select
                  value={editForm.criticidade}
                  onValueChange={(v) => setEditForm({ ...editForm, criticidade: v })}
                >
                  <SelectTrigger className="rounded-lg h-10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(criticidadeConfig).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{k} - {v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Grupo</Label>
                <Select
                  value={editForm.grupo_id}
                  onValueChange={(v) => setEditForm({ ...editForm, grupo_id: v })}
                >
                  <SelectTrigger className="rounded-lg h-10">
                    <SelectValue placeholder="Sem grupo" />
                  </SelectTrigger>
                  <SelectContent>
                    {grupos.map((g) => (
                      <SelectItem key={g.id} value={g.id}>{g.nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditDialog({ open: false, eq: null })}
                className="rounded-lg"
                data-testid="edit-equipamento-cancel"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                className="rounded-lg"
                disabled={editSaving}
                data-testid="edit-equipamento-save"
              >
                {editSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Salvar alterações
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Modal de Exclusão ────────────────────────────────── */}
      {deleteDialog.open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={() => { if (!deleteLoading) setDeleteDialog({ open: false, eq: null }); }}
        >
          <div
            className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl animate-slide-in-bottom"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                <Trash2 className="h-5 w-5 text-red-500" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-heading font-bold text-base">Excluir equipamento</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Tem certeza que deseja excluir{" "}
                  <span className="font-semibold text-foreground">{deleteDialog.eq?.nome}</span>?
                  Esta ação não pode ser desfeita.
                </p>

                {/* Erro 409 — OS ativa */}
                {deleteError && (
                  <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                    <p className="text-xs">{deleteError}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="outline"
                className="rounded-lg"
                onClick={() => setDeleteDialog({ open: false, eq: null })}
                disabled={deleteLoading}
                data-testid="delete-equipamento-cancel"
              >
                Cancelar
              </Button>
              {!deleteError && (
                <Button
                  variant="destructive"
                  className="rounded-lg"
                  onClick={handleDelete}
                  disabled={deleteLoading}
                  data-testid="delete-equipamento-confirm"
                >
                  {deleteLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Excluir
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Modal de Histórico ───────────────────────────────── */}
      {historyDialog.open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
          onClick={() => setHistoryDialog({ open: false, data: null, loading: false })}
        >
          <div
            className="bg-card border border-border rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto shadow-2xl animate-slide-in-bottom"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-heading font-bold text-lg">
                Histórico — {historyDialog.data?.equipamento?.nome || "..."}
              </h2>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setHistoryDialog({ open: false, data: null, loading: false })}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {historyDialog.loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : historyDialog.data ? (
              <div className="space-y-5">
                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 stagger-children">
                  <div className="p-3 border border-border/50 rounded-xl text-center">
                    <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider">Total OS</p>
                    <p className="text-2xl font-heading font-bold mt-1">{historyDialog.data.estatisticas.total_os}</p>
                  </div>
                  <div className="p-3 border border-border/50 rounded-xl text-center">
                    <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider">Corretivas</p>
                    <p className="text-2xl font-heading font-bold text-red-500 mt-1">{historyDialog.data.estatisticas.corretivas}</p>
                  </div>
                  <div className="p-3 border border-border/50 rounded-xl text-center">
                    <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider">Preventivas</p>
                    <p className="text-2xl font-heading font-bold text-emerald-500 mt-1">{historyDialog.data.estatisticas.preventivas}</p>
                  </div>
                  <div className="p-3 border border-border/50 rounded-xl text-center">
                    <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider">Custo Manutenção</p>
                    <p className="text-lg font-heading font-bold mt-1">
                      {finAccess === "full"
                        ? `R$ ${historyDialog.data.estatisticas.custo_total?.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}`
                        : <BlurredMoney size="md" />}
                    </p>
                  </div>
                  <div className="p-3 border border-red-500/15 bg-red-500/5 rounded-xl text-center">
                    <p className="text-[11px] text-red-500 uppercase font-semibold tracking-wider flex items-center justify-center gap-1">
                      <TrendingDown className="h-3 w-3" /> Custo Parada
                    </p>
                    <p className="text-lg font-heading font-bold text-red-500 mt-1">
                      {finAccess === "full"
                        ? `R$ ${historyDialog.data.estatisticas.custo_parada_total?.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}`
                        : <BlurredMoney size="md" color="red" />}
                    </p>
                  </div>
                  <div className="p-3 border border-border/50 rounded-xl text-center">
                    <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider flex items-center justify-center gap-1">
                      <Clock className="h-3 w-3" /> Horas Parado
                    </p>
                    <p className="text-lg font-heading font-bold mt-1">
                      {historyDialog.data.estatisticas.tempo_total_parado_horas?.toFixed(1)}h
                    </p>
                  </div>
                </div>

                {/* Timeline */}
                <div>
                  <h3 className="font-heading font-semibold text-sm mb-3">Últimas Ordens de Serviço</h3>
                  <div className="space-y-2">
                    {historyDialog.data.ordens?.map((os) => (
                      <div
                        key={os.id}
                        className="p-3 border border-border/50 rounded-lg flex items-center justify-between hover:bg-muted/30 transition-colors"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-sm font-semibold">OS #{os.numero}</span>
                            <Badge className={`text-[10px] border rounded ${os.tipo === "corretiva" ? "bg-red-500/10 text-red-500 border-red-500/20" : "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"}`}>
                              {os.tipo}
                            </Badge>
                            {os.reincidente && (
                              <Badge className="text-[10px] bg-orange-500/10 text-orange-500 border-orange-500/20 border rounded">
                                Reincidente
                              </Badge>
                            )}
                            {os.tempo_total > 0 && (
                              <span className="text-[10px] font-mono font-semibold text-red-500 bg-red-500/5 px-1.5 py-0.5 rounded flex items-center gap-1">
                                {os.custo_parada != null && finAccess === "full"
                                  ? `R$ ${os.custo_parada.toLocaleString("pt-BR", { minimumFractionDigits: 0 })} parada`
                                  : <BlurredMoney color="red" />}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground truncate mt-1">{os.descricao}</p>
                        </div>
                        <div className="text-right ml-3 shrink-0">
                          <Badge className={`text-[10px] rounded status-${os.status?.replace("_", "-")}`}>
                            {os.status?.replace("_", " ")}
                          </Badge>
                          <p className="text-[10px] text-muted-foreground mt-1">
                            {new Date(os.created_at).toLocaleDateString("pt-BR")}
                          </p>
                        </div>
                      </div>
                    ))}
                    {(!historyDialog.data.ordens || historyDialog.data.ordens.length === 0) && (
                      <p className="text-center text-sm text-muted-foreground py-6">Nenhuma OS registrada</p>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      <UpgradeDialog open={upgradeOpen} onClose={closeUpgrade} message={upgradeMessage} />
    </div>
  );
}
