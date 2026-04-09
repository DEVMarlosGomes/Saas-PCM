import { useState, useEffect } from "react";
import { getUsers, createUser } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import {
  Plus,
  Users,
  Shield,
  User,
  Wrench,
  Settings
} from "lucide-react";

const roleConfig = {
  admin: { label: "Administrador", icon: Shield, color: "bg-purple-500/10 text-purple-600 dark:text-purple-400" },
  lider: { label: "Líder Técnico", icon: Settings, color: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  tecnico: { label: "Técnico", icon: Wrench, color: "bg-green-500/10 text-green-600 dark:text-green-400" },
  operador: { label: "Operador", icon: User, color: "bg-gray-500/10 text-gray-600 dark:text-gray-400" }
};

export default function UsuariosPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    nome: "",
    role: "operador"
  });

  const isAdmin = user?.role === "admin";

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getUsers();
      setUsers(res.data);
    } catch (error) {
      toast.error("Erro ao carregar usuários");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.password || !formData.nome) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    if (formData.password.length < 6) {
      toast.error("A senha deve ter pelo menos 6 caracteres");
      return;
    }
    try {
      await createUser(formData);
      toast.success("Usuário criado com sucesso");
      setDialogOpen(false);
      setFormData({ email: "", password: "", nome: "", role: "operador" });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar usuário");
    }
  };

  return (
    <div className="space-y-6" data-testid="usuarios-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Usuários</h1>
          <p className="text-muted-foreground">{users.length} usuários cadastrados</p>
        </div>
        {isAdmin && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-sm" data-testid="new-user-btn">
                <Plus className="h-4 w-4 mr-2" />
                Novo Usuário
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-sm">
              <DialogHeader>
                <DialogTitle className="font-heading">Novo Usuário</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="nome">Nome *</Label>
                  <Input
                    id="nome"
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    placeholder="Nome completo"
                    className="rounded-sm"
                    data-testid="user-nome-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="usuario@empresa.com"
                    className="rounded-sm"
                    data-testid="user-email-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Senha *</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Mínimo 6 caracteres"
                    className="rounded-sm"
                    data-testid="user-password-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Função</Label>
                  <Select
                    value={formData.role}
                    onValueChange={(v) => setFormData({ ...formData, role: v })}
                  >
                    <SelectTrigger className="rounded-sm" data-testid="user-role-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="operador">Operador</SelectItem>
                      <SelectItem value="tecnico">Técnico</SelectItem>
                      <SelectItem value="lider">Líder Técnico</SelectItem>
                      <SelectItem value="admin">Administrador</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="rounded-sm">
                    Cancelar
                  </Button>
                  <Button type="submit" className="rounded-sm" data-testid="save-user-btn">
                    Salvar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Table */}
      <div className="border border-border rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full table-dense">
            <thead className="bg-muted">
              <tr>
                <th className="text-left font-medium p-3">Nome</th>
                <th className="text-left font-medium p-3">Email</th>
                <th className="text-center font-medium p-3">Função</th>
                <th className="text-center font-medium p-3">Status</th>
                <th className="text-left font-medium p-3 hidden lg:table-cell">Cadastro</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center p-8 text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center p-8 text-muted-foreground">
                    Nenhum usuário encontrado
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const RoleIcon = roleConfig[u.role]?.icon || User;
                  return (
                    <tr key={u.id} className="border-t border-border hover:bg-muted/50" data-testid={`user-row-${u.email}`}>
                      <td className="p-3">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-sm ${roleConfig[u.role]?.color}`}>
                            <RoleIcon className="h-4 w-4" />
                          </div>
                          <span className="font-medium">{u.nome}</span>
                        </div>
                      </td>
                      <td className="p-3 text-muted-foreground">{u.email}</td>
                      <td className="p-3 text-center">
                        <Badge className={`${roleConfig[u.role]?.color} rounded-sm`}>
                          {roleConfig[u.role]?.label}
                        </Badge>
                      </td>
                      <td className="p-3 text-center">
                        <Badge className={`rounded-sm ${u.ativo ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600'}`}>
                          {u.ativo ? 'Ativo' : 'Inativo'}
                        </Badge>
                      </td>
                      <td className="p-3 hidden lg:table-cell text-sm text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString('pt-BR')}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Permissions Info */}
      <div className="border border-border rounded-sm p-4 bg-muted/50">
        <h3 className="font-heading font-semibold mb-3">Permissões por Função</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-4 w-4 text-purple-500" />
              <span className="font-medium">Administrador</span>
            </div>
            <ul className="text-muted-foreground space-y-1">
              <li>• Acesso total ao sistema</li>
              <li>• Gerenciar usuários</li>
              <li>• Ver auditoria</li>
              <li>• Ver indicadores e custos</li>
            </ul>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Settings className="h-4 w-4 text-blue-500" />
              <span className="font-medium">Líder Técnico</span>
            </div>
            <ul className="text-muted-foreground space-y-1">
              <li>• Revisar OS</li>
              <li>• Gerenciar equipamentos</li>
              <li>• Criar planos preventivos</li>
              <li>• Ver auditoria</li>
            </ul>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Wrench className="h-4 w-4 text-green-500" />
              <span className="font-medium">Técnico</span>
            </div>
            <ul className="text-muted-foreground space-y-1">
              <li>• Executar OS</li>
              <li>• Registrar custos</li>
              <li>• Abrir chamados</li>
            </ul>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <User className="h-4 w-4 text-gray-500" />
              <span className="font-medium">Operador</span>
            </div>
            <ul className="text-muted-foreground space-y-1">
              <li>• Abrir chamados</li>
              <li>• Visualizar OS</li>
              <li>• Visualizar equipamentos</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
