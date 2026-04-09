import { useState, useEffect } from "react";
import { getPlanosPreventivos, createPlanoPreventivo, executarPlano, getEquipamentos } from "../lib/api";
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
  Calendar,
  Play,
  Clock,
  AlertTriangle
} from "lucide-react";

export default function PlanosPreventivosPage() {
  const { user } = useAuth();
  const [planos, setPlanos] = useState([]);
  const [equipamentos, setEquipamentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    equipamento_id: "",
    nome: "",
    descricao: "",
    frequencia_dias: "30"
  });

  const canEdit = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const [planosRes, eqRes] = await Promise.all([
        getPlanosPreventivos(),
        getEquipamentos()
      ]);
      setPlanos(planosRes.data);
      setEquipamentos(eqRes.data);
    } catch (error) {
      toast.error("Erro ao carregar planos preventivos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.equipamento_id || !formData.nome || !formData.frequencia_dias) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      await createPlanoPreventivo({
        ...formData,
        frequencia_dias: parseInt(formData.frequencia_dias)
      });
      toast.success("Plano preventivo criado com sucesso");
      setDialogOpen(false);
      setFormData({ equipamento_id: "", nome: "", descricao: "", frequencia_dias: "30" });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar plano");
    }
  };

  const handleExecutar = async (planoId) => {
    try {
      const res = await executarPlano(planoId);
      toast.success(`OS #${res.data.numero} criada com sucesso`);
      loadData();
    } catch (error) {
      toast.error("Erro ao executar plano");
    }
  };

  const getEquipamentoNome = (id) => {
    const eq = equipamentos.find(e => e.id === id);
    return eq ? `${eq.codigo} - ${eq.nome}` : id;
  };

  const isVencido = (proxima) => {
    if (!proxima) return false;
    return new Date(proxima) < new Date();
  };

  const diasParaVencer = (proxima) => {
    if (!proxima) return null;
    const diff = new Date(proxima) - new Date();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="space-y-6" data-testid="planos-preventivos-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Planos Preventivos</h1>
          <p className="text-muted-foreground">{planos.length} planos cadastrados</p>
        </div>
        {canEdit && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-sm" data-testid="new-plano-btn">
                <Plus className="h-4 w-4 mr-2" />
                Novo Plano
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-sm">
              <DialogHeader>
                <DialogTitle className="font-heading">Novo Plano Preventivo</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="equipamento">Equipamento *</Label>
                  <Select
                    value={formData.equipamento_id}
                    onValueChange={(v) => setFormData({ ...formData, equipamento_id: v })}
                  >
                    <SelectTrigger className="rounded-sm" data-testid="plano-equipamento-select">
                      <SelectValue placeholder="Selecione o equipamento" />
                    </SelectTrigger>
                    <SelectContent>
                      {equipamentos.map((eq) => (
                        <SelectItem key={eq.id} value={eq.id}>
                          {eq.codigo} - {eq.nome}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="nome">Nome do Plano *</Label>
                  <Input
                    id="nome"
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    placeholder="Manutenção mensal"
                    className="rounded-sm"
                    data-testid="plano-nome-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="descricao">Descrição</Label>
                  <Input
                    id="descricao"
                    value={formData.descricao}
                    onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                    placeholder="Verificação geral e lubrificação"
                    className="rounded-sm"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="frequencia">Frequência (dias) *</Label>
                  <Select
                    value={formData.frequencia_dias}
                    onValueChange={(v) => setFormData({ ...formData, frequencia_dias: v })}
                  >
                    <SelectTrigger className="rounded-sm" data-testid="plano-frequencia-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="7">Semanal (7 dias)</SelectItem>
                      <SelectItem value="15">Quinzenal (15 dias)</SelectItem>
                      <SelectItem value="30">Mensal (30 dias)</SelectItem>
                      <SelectItem value="60">Bimestral (60 dias)</SelectItem>
                      <SelectItem value="90">Trimestral (90 dias)</SelectItem>
                      <SelectItem value="180">Semestral (180 dias)</SelectItem>
                      <SelectItem value="365">Anual (365 dias)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="rounded-sm">
                    Cancelar
                  </Button>
                  <Button type="submit" className="rounded-sm" data-testid="save-plano-btn">
                    Salvar
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Cards Grid */}
      {loading ? (
        <div className="text-center py-8 text-muted-foreground">Carregando...</div>
      ) : planos.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-border rounded-sm">
          <Calendar className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">Nenhum plano preventivo cadastrado</p>
          {canEdit && (
            <Button className="mt-4 rounded-sm" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Criar primeiro plano
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {planos.map((plano) => {
            const vencido = isVencido(plano.proxima_execucao);
            const dias = diasParaVencer(plano.proxima_execucao);
            
            return (
              <div
                key={plano.id}
                className={`border rounded-sm p-4 ${vencido ? 'border-red-500 bg-red-500/5' : 'border-border bg-card'}`}
                data-testid={`plano-card-${plano.id}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-heading font-semibold">{plano.nome}</h3>
                    <p className="text-sm text-muted-foreground">{getEquipamentoNome(plano.equipamento_id)}</p>
                  </div>
                  {vencido && (
                    <Badge className="bg-red-500 text-white rounded-sm">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Vencido
                    </Badge>
                  )}
                </div>

                {plano.descricao && (
                  <p className="text-sm text-muted-foreground mb-3">{plano.descricao}</p>
                )}

                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Frequência:</span>
                    <span className="font-medium">{plano.frequencia_dias} dias</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Última execução:</span>
                    <span className="font-medium">
                      {plano.ultima_execucao 
                        ? new Date(plano.ultima_execucao).toLocaleDateString('pt-BR')
                        : 'Nunca'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Próxima:</span>
                    <span className={`font-medium ${vencido ? 'text-red-500' : ''}`}>
                      {plano.proxima_execucao 
                        ? new Date(plano.proxima_execucao).toLocaleDateString('pt-BR')
                        : '-'}
                      {dias !== null && !vencido && (
                        <span className="text-xs text-muted-foreground ml-1">
                          ({dias} dias)
                        </span>
                      )}
                    </span>
                  </div>
                </div>

                {canEdit && (
                  <Button
                    className="w-full mt-4 rounded-sm"
                    variant={vencido ? "default" : "outline"}
                    onClick={() => handleExecutar(plano.id)}
                    data-testid={`executar-plano-${plano.id}`}
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Gerar OS Preventiva
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
