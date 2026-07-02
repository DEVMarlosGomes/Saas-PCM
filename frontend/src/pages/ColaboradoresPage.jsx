import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getColaboradores, createColaborador, updateColaborador, deleteColaborador } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import {
  HardHat, Plus, Search, Edit2, Trash2, Loader2,
  X, CheckCircle2, XCircle, Badge as BadgeIcon,
} from "lucide-react";
import { HelpTooltip } from "../components/shared/HelpTooltip";

export default function ColaboradoresPage() {
  const { user: currentUser } = useAuth();
  const [colaboradores, setColaboradores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({ nome: "", matricula: "", cargo: "", setor: "" });

  const isAdmin = currentUser?.role === "admin";

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const res = await getColaboradores();
      setColaboradores(res.data || []);
    } catch {
      toast.error("Erro ao carregar colaboradores");
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ nome: "", matricula: "", cargo: "", setor: "" });
    setShowModal(true);
  };

  const openEdit = (col) => {
    setEditingId(col.id);
    setForm({ nome: col.nome, matricula: col.matricula, cargo: col.cargo || "", setor: col.setor || "" });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.nome.trim() || !form.matricula.trim()) {
      toast.error("Nome e matrícula são obrigatórios");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        nome: form.nome.trim(),
        matricula: form.matricula.trim(),
        cargo: form.cargo.trim() || null,
        setor: form.setor.trim() || null,
      };
      if (editingId) {
        await updateColaborador(editingId, payload);
        toast.success("Colaborador atualizado!");
      } else {
        await createColaborador(payload);
        toast.success("Colaborador cadastrado!");
      }
      setShowModal(false);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao salvar colaborador");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (col) => {
    if (!window.confirm(`Desativar "${col.nome}" (matrícula ${col.matricula})?`)) return;
    try {
      await deleteColaborador(col.id);
      toast.success("Colaborador desativado");
      loadData();
    } catch {
      toast.error("Erro ao desativar colaborador");
    }
  };

  const handleToggleAtivo = async (col) => {
    try {
      await updateColaborador(col.id, { ativo: !col.ativo });
      toast.success(col.ativo ? "Colaborador desativado" : "Colaborador reativado");
      loadData();
    } catch {
      toast.error("Erro ao atualizar colaborador");
    }
  };

  const filtered = colaboradores.filter((c) => {
    const q = searchQuery.toLowerCase();
    return (
      c.nome.toLowerCase().includes(q) ||
      c.matricula.toLowerCase().includes(q) ||
      (c.cargo || "").toLowerCase().includes(q) ||
      (c.setor || "").toLowerCase().includes(q)
    );
  });

  const ativos = filtered.filter((c) => c.ativo);
  const inativos = filtered.filter((c) => !c.ativo);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="font-heading text-2xl font-bold">Colaboradores</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Técnicos de manutenção cadastrados para assinar ordens de serviço
          </p>
        </div>
        {isAdmin && (
          <Button onClick={openCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            Novo Colaborador
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Total</p>
          <p className="text-2xl font-bold">{colaboradores.length}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Ativos</p>
          <p className="text-2xl font-bold text-emerald-500">{colaboradores.filter((c) => c.ativo).length}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Inativos</p>
          <p className="text-2xl font-bold text-muted-foreground">{colaboradores.filter((c) => !c.ativo).length}</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por nome, matrícula, cargo ou setor..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Ativos */}
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Ativos ({ativos.length})
            </h3>
            {ativos.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground text-sm">
                Nenhum colaborador ativo encontrado.
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {ativos.map((col) => (
                  <ColaboradorCard
                    key={col.id}
                    col={col}
                    isAdmin={isAdmin}
                    onEdit={() => openEdit(col)}
                    onDelete={() => handleDelete(col)}
                    onToggle={() => handleToggleAtivo(col)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Inativos */}
          {inativos.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Inativos ({inativos.length})
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {inativos.map((col) => (
                  <ColaboradorCard
                    key={col.id}
                    col={col}
                    isAdmin={isAdmin}
                    onEdit={() => openEdit(col)}
                    onDelete={() => handleDelete(col)}
                    onToggle={() => handleToggleAtivo(col)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setShowModal(false)}
        >
          <div
            className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                  <HardHat className="h-4 w-4 text-primary" />
                </div>
                <h3 className="font-heading font-bold text-base">
                  {editingId ? "Editar Colaborador" : "Novo Colaborador"}
                </h3>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <Label htmlFor="nome">Nome completo *</Label>
                <Input
                  id="nome"
                  placeholder="Ex: João Silva"
                  value={form.nome}
                  onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="matricula" className="flex items-center">
                  Matrícula / Registro *
                  <span className="ml-1 text-xs text-muted-foreground">(usada para assinar OS)</span>
                  <HelpTooltip text="Código único do colaborador — é o número digitado ao iniciar ou concluir uma OS. Deve ser o mesmo do crachá físico ou sistema de RH." />
                </Label>
                <Input
                  id="matricula"
                  placeholder="Ex: TEC-001 ou 12345"
                  value={form.matricula}
                  onChange={(e) => setForm((f) => ({ ...f, matricula: e.target.value }))}
                  className="mt-1 font-mono"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="cargo">Cargo / Função</Label>
                  <Input
                    id="cargo"
                    placeholder="Ex: Eletricista"
                    value={form.cargo}
                    onChange={(e) => setForm((f) => ({ ...f, cargo: e.target.value }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="setor">Setor</Label>
                  <Input
                    id="setor"
                    placeholder="Ex: Manutenção"
                    value={form.setor}
                    onChange={(e) => setForm((f) => ({ ...f, setor: e.target.value }))}
                    className="mt-1"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1" disabled={saving}>
                  {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  {editingId ? "Salvar Alterações" : "Cadastrar"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function ColaboradorCard({ col, isAdmin, onEdit, onDelete, onToggle }) {
  return (
    <div className={`bg-card border border-border rounded-xl p-4 flex flex-col gap-3 transition-opacity ${!col.ativo ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <HardHat className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-sm truncate">{col.nome}</p>
            {col.cargo && <p className="text-xs text-muted-foreground truncate">{col.cargo}</p>}
          </div>
        </div>
        {col.ativo ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
        ) : (
          <XCircle className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20 font-semibold">
          # {col.matricula}
        </span>
        {col.setor && (
          <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-md bg-muted/60 border border-border">
            {col.setor}
          </span>
        )}
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2 pt-1 border-t border-border/50">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs px-2 flex-1 gap-1"
            onClick={onEdit}
          >
            <Edit2 className="h-3 w-3" />
            Editar
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={`h-7 text-xs px-2 flex-1 gap-1 ${col.ativo ? "text-amber-500 hover:text-amber-400" : "text-emerald-500 hover:text-emerald-400"}`}
            onClick={onToggle}
          >
            {col.ativo ? <XCircle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
            {col.ativo ? "Desativar" : "Reativar"}
          </Button>
        </div>
      )}
    </div>
  );
}
