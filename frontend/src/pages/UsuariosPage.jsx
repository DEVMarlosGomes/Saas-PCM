import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getUsers, createUser, updateUser, deleteUser } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import {
  Users,
  Plus,
  Search,
  Shield,
  Wrench,
  Crown,
  User,
  MoreVertical,
  Edit2,
  Trash2,
  Loader2,
  UserPlus,
  X,
  CheckCircle2,
  XCircle,
  Mail,
  Calendar,
} from "lucide-react";

const roleConfig = {
  admin: { label: "Administrador", icon: Crown, color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  lider: { label: "Líder Técnico", icon: Shield, color: "bg-purple-500/10 text-purple-500 border-purple-500/20" },
  tecnico: { label: "Técnico", icon: Wrench, color: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  operador: { label: "Operador", icon: User, color: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
};

const roles = ["admin", "lider", "tecnico", "operador"];

export default function UsuariosPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [actionMenuId, setActionMenuId] = useState(null);

  // Create form
  const [newEmail, setNewEmail] = useState("");
  const [newNome, setNewNome] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("operador");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const res = await getUsers();
      setUsers(res.data || []);
    } catch (error) {
      toast.error("Erro ao carregar usuários");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newEmail || !newNome || !newPassword) {
      toast.error("Preencha todos os campos");
      return;
    }
    setCreating(true);
    try {
      await createUser({ email: newEmail, nome: newNome, password: newPassword, role: newRole });
      toast.success("Usuário criado com sucesso!");
      setShowCreateModal(false);
      resetCreateForm();
      loadUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar usuário");
    } finally {
      setCreating(false);
    }
  };

  const handleUpdate = async (userId, updates) => {
    setSaving(true);
    try {
      await updateUser(userId, updates);
      toast.success("Usuário atualizado!");
      setEditingUser(null);
      loadUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao atualizar");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (userId) => {
    if (!window.confirm("Deseja realmente desativar este usuário?")) return;
    try {
      await deleteUser(userId);
      toast.success("Usuário desativado");
      loadUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao desativar");
    }
  };

  const resetCreateForm = () => {
    setNewEmail("");
    setNewNome("");
    setNewPassword("");
    setNewRole("operador");
  };

  const filteredUsers = users.filter(u =>
    u.nome?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isAdmin = currentUser?.role === "admin";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="usuarios-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            Gestão de Usuários
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {users.length} usuário{users.length !== 1 ? 's' : ''} na organização
          </p>
        </div>
        {isAdmin && (
          <Button onClick={() => setShowCreateModal(true)} className="rounded-lg h-10 shadow-lg shadow-primary/20">
            <UserPlus className="h-4 w-4 mr-2" />
            Novo Usuário
          </Button>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por nome ou email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 h-10 rounded-lg bg-card"
        />
      </div>

      {/* Users Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        {filteredUsers.map((u) => {
          const rc = roleConfig[u.role] || roleConfig.operador;
          const RoleIcon = rc.icon;
          const isEditing = editingUser === u.id;

          return (
            <div
              key={u.id}
              className={`border border-border/50 rounded-xl bg-card p-5 card-hover relative ${!u.ativo ? 'opacity-50' : ''}`}
            >
              {/* Action menu */}
              {isAdmin && u.id !== currentUser?.id && (
                <div className="absolute top-3 right-3">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setActionMenuId(actionMenuId === u.id ? null : u.id)}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                  {actionMenuId === u.id && (
                    <div className="absolute right-0 top-9 bg-card border border-border rounded-lg shadow-xl py-1 z-10 min-w-[140px] animate-fade-in">
                      <button
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-muted transition-colors"
                        onClick={() => { setEditingUser(u.id); setActionMenuId(null); }}
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                        Editar cargo
                      </button>
                      <button
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-500 hover:bg-red-500/10 transition-colors"
                        onClick={() => { handleDeactivate(u.id); setActionMenuId(null); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Desativar
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Avatar */}
              <div className="flex items-center gap-3 mb-4">
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-lg shrink-0">
                  {u.nome?.[0]?.toUpperCase() || "?"}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold truncate">{u.nome}</p>
                  <p className="text-xs text-muted-foreground truncate flex items-center gap-1">
                    <Mail className="h-3 w-3" />
                    {u.email}
                  </p>
                </div>
              </div>

              {/* Role */}
              {isEditing ? (
                <div className="space-y-2 mb-3">
                  <Label className="text-xs">Alterar cargo:</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {roles.map((r) => (
                      <button
                        key={r}
                        className={`text-xs px-2 py-1.5 rounded-md border transition-colors ${
                          r === u.role
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'border-border bg-muted/50 hover:bg-muted text-foreground'
                        }`}
                        onClick={() => handleUpdate(u.id, { role: r })}
                        disabled={saving}
                      >
                        {roleConfig[r]?.label}
                      </button>
                    ))}
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setEditingUser(null)} className="w-full mt-1">
                    Cancelar
                  </Button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border font-medium ${rc.color}`}>
                    <RoleIcon className="h-3 w-3" />
                    {rc.label}
                  </span>
                  <span className={`flex items-center gap-1 text-xs font-medium ${u.ativo ? 'text-emerald-500' : 'text-red-400'}`}>
                    {u.ativo ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                    {u.ativo ? 'Ativo' : 'Inativo'}
                  </span>
                </div>
              )}

              {/* Footer */}
              <p className="text-[11px] text-muted-foreground mt-3 flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Desde {u.created_at ? new Date(u.created_at).toLocaleDateString('pt-BR') : '—'}
              </p>
            </div>
          );
        })}
      </div>

      {filteredUsers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Users className="h-10 w-10 mb-3 opacity-40" />
          <p className="font-medium">Nenhum usuário encontrado</p>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-heading font-bold text-lg">Novo Usuário</h2>
              <Button variant="ghost" size="icon" onClick={() => setShowCreateModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label>Nome</Label>
                <Input value={newNome} onChange={(e) => setNewNome(e.target.value)} className="h-10 rounded-lg" placeholder="Nome completo" />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} className="h-10 rounded-lg" placeholder="email@empresa.com" />
              </div>
              <div className="space-y-2">
                <Label>Senha</Label>
                <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="h-10 rounded-lg" placeholder="Senha temporária" />
              </div>
              <div className="space-y-2">
                <Label>Cargo</Label>
                <div className="grid grid-cols-2 gap-2">
                  {roles.map((r) => (
                    <button
                      key={r}
                      type="button"
                      className={`text-sm px-3 py-2 rounded-lg border transition-all ${
                        r === newRole
                          ? 'bg-primary text-primary-foreground border-primary shadow-lg shadow-primary/20'
                          : 'border-border bg-muted/50 hover:bg-muted'
                      }`}
                      onClick={() => setNewRole(r)}
                    >
                      {roleConfig[r]?.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1 rounded-lg" onClick={() => setShowCreateModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 rounded-lg" disabled={creating}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                  Criar Usuário
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
