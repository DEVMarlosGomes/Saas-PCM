import { useState, useEffect } from "react";
import { getEquipamentos, createEquipamento, getGrupos, getEquipamentoHistorico } from "../lib/api";
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
  Search,
  Settings,
  MapPin,
  DollarSign,
  Activity,
  History,
  X
} from "lucide-react";

const criticidadeColors = {
  1: "bg-gray-500/10 text-gray-600 dark:text-gray-400",
  2: "bg-green-500/10 text-green-600 dark:text-green-400",
  3: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  4: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  5: "bg-red-500/10 text-red-600 dark:text-red-400"
};

export default function EquipamentosPage() {
  const { user } = useAuth();
  const [equipamentos, setEquipamentos] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [historyDialog, setHistoryDialog] = useState({ open: false, data: null });
  const [formData, setFormData] = useState({
    codigo: "",
    nome: "",
    descricao: "",
    localizacao: "",
    valor_hora: "",
    grupo_id: "",
    criticidade: "3"
  });

  const canEdit = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const [eqRes, grRes] = await Promise.all([
        getEquipamentos(),
        getGrupos()
      ]);
      setEquipamentos(eqRes.data);
      setGrupos(grRes.data);
    } catch (error) {
      toast.error("Erro ao carregar equipamentos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

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
        grupo_id: formData.grupo_id || null
      });
      toast.success("Equipamento criado com sucesso");
      setDialogOpen(false);
      setFormData({ codigo: "", nome: "", descricao: "", localizacao: "", valor_hora: "", grupo_id: "", criticidade: "3" });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar equipamento");
    }
  };

  const handleViewHistory = async (equipamento) => {
    try {
      const res = await getEquipamentoHistorico(equipamento.id);
      setHistoryDialog({ open: true, data: res.data });
    } catch (error) {
      toast.error("Erro ao carregar histórico");
    }
  };

  const filteredEquipamentos = equipamentos.filter(eq => 
    eq.codigo.toLowerCase().includes(search.toLowerCase()) ||
    eq.nome.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="equipamentos-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Equipamentos</h1>
          <p className="text-muted-foreground">{equipamentos.length} equipamentos cadastrados</p>
        </div>
        {canEdit && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-sm" data-testid="new-equipamento-btn">
                <Plus className="h-4 w-4 mr-2" />
                Novo Equipamento
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-sm">
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
                      className="rounded-sm"
                      data-testid="equipamento-codigo-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="criticidade">Criticidade</Label>
                    <Select
                      value={formData.criticidade}
                      onValueChange={(v) => setFormData({ ...formData, criticidade: v })}
                    >
                      <SelectTrigger className="rounded-sm" data-testid="equipamento-criticidade-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1 - Muito Baixa</SelectItem>
                        <SelectItem value="2">2 - Baixa</SelectItem>
                        <SelectItem value="3">3 - Média</SelectItem>
                        <SelectItem value="4">4 - Alta</SelectItem>
                        <SelectItem value="5">5 - Crítica</SelectItem>
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
                    className="rounded-sm"
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
                    className="rounded-sm"
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
                      className="rounded-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="valor_hora">Valor/Hora (R$)</Label>
                    <Input
                      id="valor_hora"
                      type="number"
                      step="0.01"
                      value={formData.valor_hora}
                      onChange={(e) => setFormData({ ...formData, valor_hora: e.target.value })}
                      placeholder="500.00"
                      className="rounded-sm"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="grupo">Grupo</Label>
                  <Select
                    value={formData.grupo_id}
                    onValueChange={(v) => setFormData({ ...formData, grupo_id: v })}
                  >
                    <SelectTrigger className="rounded-sm">
                      <SelectValue placeholder="Selecione um grupo" />
                    </SelectTrigger>
                    <SelectContent>
                      {grupos.map((g) => (
                        <SelectItem key={g.id} value={g.id}>{g.nome}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="rounded-sm">
                    Cancelar
                  </Button>
                  <Button type="submit" className="rounded-sm" data-testid="save-equipamento-btn">
                    Salvar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por código ou nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9 rounded-sm"
          data-testid="search-equipamentos-input"
        />
      </div>

      {/* Table */}
      <div className="border border-border rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full table-dense">
            <thead className="bg-muted">
              <tr>
                <th className="text-left font-medium p-3">Código</th>
                <th className="text-left font-medium p-3">Nome</th>
                <th className="text-left font-medium p-3 hidden md:table-cell">Localização</th>
                <th className="text-left font-medium p-3 hidden lg:table-cell">Valor/Hora</th>
                <th className="text-center font-medium p-3">Criticidade</th>
                <th className="text-right font-medium p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center p-8 text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : filteredEquipamentos.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center p-8 text-muted-foreground">
                    Nenhum equipamento encontrado
                  </td>
                </tr>
              ) : (
                filteredEquipamentos.map((eq) => (
                  <tr key={eq.id} className="border-t border-border hover:bg-muted/50" data-testid={`equipamento-row-${eq.codigo}`}>
                    <td className="p-3">
                      <span className="font-mono text-sm">{eq.codigo}</span>
                    </td>
                    <td className="p-3">
                      <div className="font-medium">{eq.nome}</div>
                      {eq.descricao && (
                        <div className="text-xs text-muted-foreground truncate max-w-[200px]">{eq.descricao}</div>
                      )}
                    </td>
                    <td className="p-3 hidden md:table-cell">
                      {eq.localizacao ? (
                        <div className="flex items-center gap-1 text-sm">
                          <MapPin className="h-3 w-3" />
                          {eq.localizacao}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="p-3 hidden lg:table-cell">
                      {eq.valor_hora > 0 ? (
                        <div className="flex items-center gap-1 text-sm">
                          <DollarSign className="h-3 w-3" />
                          R$ {eq.valor_hora.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="p-3 text-center">
                      <Badge className={`${criticidadeColors[eq.criticidade]} rounded-sm`}>
                        {eq.criticidade}
                      </Badge>
                    </td>
                    <td className="p-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewHistory(eq)}
                        data-testid={`view-history-${eq.codigo}`}
                      >
                        <History className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* History Dialog */}
      <Dialog open={historyDialog.open} onOpenChange={(open) => setHistoryDialog({ open, data: null })}>
        <DialogContent className="rounded-sm max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">
              Histórico - {historyDialog.data?.equipamento?.nome}
            </DialogTitle>
          </DialogHeader>
          {historyDialog.data && (
            <div className="space-y-4">
              {/* Stats */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Total de OS</p>
                  <p className="text-xl font-heading font-bold">{historyDialog.data.estatisticas.total_os}</p>
                </div>
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Corretivas</p>
                  <p className="text-xl font-heading font-bold text-red-500">{historyDialog.data.estatisticas.corretivas}</p>
                </div>
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Preventivas</p>
                  <p className="text-xl font-heading font-bold text-green-500">{historyDialog.data.estatisticas.preventivas}</p>
                </div>
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Custo Total</p>
                  <p className="text-lg font-heading font-bold">R$ {historyDialog.data.estatisticas.custo_total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p>
                </div>
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Custo Parada</p>
                  <p className="text-lg font-heading font-bold text-orange-500">R$ {historyDialog.data.estatisticas.custo_parada_total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p>
                </div>
                <div className="p-3 border border-border rounded-sm">
                  <p className="text-xs text-muted-foreground">Horas Parado</p>
                  <p className="text-lg font-heading font-bold">{historyDialog.data.estatisticas.tempo_total_parado_horas.toFixed(1)}h</p>
                </div>
              </div>

              {/* Timeline */}
              <div>
                <h3 className="font-medium mb-2">Últimas Ordens de Serviço</h3>
                <div className="space-y-2">
                  {historyDialog.data.ordens.map((os) => (
                    <div key={os.id} className="p-3 border border-border rounded-sm flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm">OS #{os.numero}</span>
                          <Badge className={`rounded-sm ${os.tipo === 'corretiva' ? 'bg-red-500/10 text-red-600' : 'bg-green-500/10 text-green-600'}`}>
                            {os.tipo}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground truncate max-w-[300px]">{os.descricao}</p>
                      </div>
                      <div className="text-right">
                        <Badge className={`rounded-sm status-${os.status.replace('_', '-')}`}>{os.status}</Badge>
                        <p className="text-xs text-muted-foreground mt-1">
                          {new Date(os.created_at).toLocaleDateString('pt-BR')}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
