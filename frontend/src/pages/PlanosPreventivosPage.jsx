import { useState, useEffect } from "react";
import { getPlanosPreventivos, createPlanoPreventivo, executarPlano, getEquipamentos } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import {
  Plus,
  Calendar,
  Play,
  Clock,
  AlertTriangle,
  Loader2,
  X,
  CheckCircle2,
  Timer,
  Zap,
  Shield,
} from "lucide-react";

const frequencyLabels = {
  7: "Semanal",
  15: "Quinzenal",
  30: "Mensal",
  60: "Bimestral",
  90: "Trimestral",
  180: "Semestral",
  365: "Anual",
};

export default function PlanosPreventivosPage() {
  const { user } = useAuth();
  const [planos, setPlanos] = useState([]);
  const [equipamentos, setEquipamentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [executing, setExecuting] = useState(null);
  const [formData, setFormData] = useState({
    equipamento_id: "", nome: "", descricao: "", frequencia_dias: "30"
  });

  const canEdit = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const [planosRes, eqRes] = await Promise.all([getPlanosPreventivos(), getEquipamentos()]);
      setPlanos(planosRes.data);
      setEquipamentos(eqRes.data);
    } catch (error) {
      toast.error("Erro ao carregar planos preventivos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

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
      toast.success("Plano preventivo criado!");
      setShowCreateModal(false);
      setFormData({ equipamento_id: "", nome: "", descricao: "", frequencia_dias: "30" });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar plano");
    }
  };

  const handleExecutar = async (planoId) => {
    setExecuting(planoId);
    try {
      const res = await executarPlano(planoId);
      toast.success(`✅ OS #${res.data.numero} criada automaticamente!`);
      loadData();
    } catch (error) {
      toast.error("Erro ao executar plano");
    } finally {
      setExecuting(null);
    }
  };

  const getEquipamentoNome = (id) => {
    const eq = equipamentos.find(e => e.id === id);
    return eq ? `${eq.codigo} - ${eq.nome}` : id;
  };

  const isVencido = (proxima) => proxima ? new Date(proxima) < new Date() : false;

  const diasParaVencer = (proxima) => {
    if (!proxima) return null;
    return Math.ceil((new Date(proxima) - new Date()) / (1000 * 60 * 60 * 24));
  };

  const vencidosCount = planos.filter(p => isVencido(p.proxima_execucao)).length;
  const proximosCount = planos.filter(p => {
    const dias = diasParaVencer(p.proxima_execucao);
    return dias !== null && dias >= 0 && dias <= 7;
  }).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="planos-preventivos-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Calendar className="h-6 w-6 text-primary" />
            PCM Preventiva
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {planos.length} planos ativos • Reduza manutenção corretiva
          </p>
        </div>
        {canEdit && (
          <Button onClick={() => setShowCreateModal(true)} className="rounded-lg h-10 shadow-lg shadow-primary/20" data-testid="new-plano-btn">
            <Plus className="h-4 w-4 mr-2" />
            Novo Plano
          </Button>
        )}
      </div>

      {/* Summary Banners */}
      {(vencidosCount > 0 || proximosCount > 0) && (
        <div className="flex flex-wrap gap-3">
          {vencidosCount > 0 && (
            <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-red-500/8 border border-red-500/15 animate-slide-in-bottom">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium text-red-600 dark:text-red-400">
                {vencidosCount} plano{vencidosCount > 1 ? 's' : ''} vencido{vencidosCount > 1 ? 's' : ''}
              </span>
            </div>
          )}
          {proximosCount > 0 && (
            <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-amber-500/8 border border-amber-500/15 animate-slide-in-bottom">
              <Clock className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
                {proximosCount} plano{proximosCount > 1 ? 's' : ''} vence{proximosCount > 1 ? 'm' : ''} em até 7 dias
              </span>
            </div>
          )}
        </div>
      )}

      {/* Cards Grid */}
      {planos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 border border-dashed border-border rounded-xl">
          <div className="p-4 rounded-full bg-muted mb-4">
            <Calendar className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="font-heading font-semibold text-lg">Nenhum plano preventivo</p>
          <p className="text-sm text-muted-foreground mt-1">Crie planos para reduzir falhas inesperadas</p>
          {canEdit && (
            <Button className="mt-4 rounded-lg" onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Criar primeiro plano
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
          {planos.map((plano) => {
            const vencido = isVencido(plano.proxima_execucao);
            const dias = diasParaVencer(plano.proxima_execucao);
            const urgente = dias !== null && dias >= 0 && dias <= 3;
            const isExecuting = executing === plano.id;

            return (
              <div
                key={plano.id}
                className={`border rounded-xl bg-card p-5 card-hover transition-all ${
                  vencido ? 'border-red-500/30 ring-1 ring-red-500/10' :
                  urgente ? 'border-amber-500/30' : 'border-border/50'
                }`}
                data-testid={`plano-card-${plano.id}`}
              >
                {/* Status Badge */}
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-heading font-semibold truncate">{plano.nome}</h3>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">
                      {getEquipamentoNome(plano.equipamento_id)}
                    </p>
                  </div>
                  {vencido ? (
                    <Badge className="bg-red-500 text-white rounded-lg text-[10px] ml-2 shrink-0 animate-pulse-soft">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Vencido
                    </Badge>
                  ) : urgente ? (
                    <Badge className="bg-amber-500/15 text-amber-500 border-amber-500/20 border rounded-lg text-[10px] ml-2 shrink-0">
                      <Clock className="h-3 w-3 mr-1" />
                      {dias}d
                    </Badge>
                  ) : (
                    <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 border rounded-lg text-[10px] ml-2 shrink-0">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      OK
                    </Badge>
                  )}
                </div>

                {plano.descricao && (
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{plano.descricao}</p>
                )}

                {/* Info Grid */}
                <div className="space-y-2.5 text-sm">
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Timer className="h-3.5 w-3.5" /> Frequência
                    </span>
                    <span className="font-semibold">
                      {frequencyLabels[plano.frequencia_dias] || `${plano.frequencia_dias} dias`}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Última execução
                    </span>
                    <span className="font-semibold">
                      {plano.ultima_execucao
                        ? new Date(plano.ultima_execucao).toLocaleDateString('pt-BR')
                        : 'Nunca'}
                    </span>
                  </div>
                  <div className={`flex items-center justify-between p-2 rounded-lg ${vencido ? 'bg-red-500/5' : 'bg-muted/30'}`}>
                    <span className={`flex items-center gap-1.5 ${vencido ? 'text-red-500' : 'text-muted-foreground'}`}>
                      <Calendar className="h-3.5 w-3.5" /> Próxima
                    </span>
                    <span className={`font-semibold ${vencido ? 'text-red-500' : ''}`}>
                      {plano.proxima_execucao
                        ? new Date(plano.proxima_execucao).toLocaleDateString('pt-BR')
                        : '—'}
                    </span>
                  </div>
                </div>

                {/* Action Button — Large, operator-friendly */}
                {canEdit && (
                  <Button
                    className={`w-full mt-4 rounded-lg h-11 text-sm font-semibold transition-all ${
                      vencido
                        ? 'bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20'
                        : 'shadow-lg shadow-primary/10'
                    }`}
                    variant={vencido ? "default" : "outline"}
                    onClick={() => handleExecutar(plano.id)}
                    disabled={isExecuting}
                    data-testid={`executar-plano-${plano.id}`}
                  >
                    {isExecuting ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Zap className="h-4 w-4 mr-2" />
                    )}
                    {isExecuting ? "Gerando OS..." : "Gerar OS Preventiva"}
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Shield className="h-5 w-5" />
                </div>
                <h2 className="font-heading font-bold text-lg">Novo Plano Preventivo</h2>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setShowCreateModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Equipamento *</Label>
                <Select
                  value={formData.equipamento_id}
                  onValueChange={(v) => setFormData({ ...formData, equipamento_id: v })}
                >
                  <SelectTrigger className="rounded-lg h-10" data-testid="plano-equipamento-select">
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
                <Label>Nome do Plano *</Label>
                <Input
                  value={formData.nome}
                  onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                  placeholder="Manutenção mensal"
                  className="rounded-lg h-10"
                  data-testid="plano-nome-input"
                />
              </div>

              <div className="space-y-2">
                <Label>Descrição</Label>
                <Input
                  value={formData.descricao}
                  onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                  placeholder="Verificação geral e lubrificação"
                  className="rounded-lg h-10"
                />
              </div>

              <div className="space-y-2">
                <Label>Frequência *</Label>
                <div className="grid grid-cols-4 gap-2">
                  {Object.entries(frequencyLabels).map(([days, label]) => (
                    <button
                      key={days}
                      type="button"
                      className={`text-xs px-2 py-2.5 rounded-lg border transition-all font-medium ${
                        formData.frequencia_dias === days
                          ? 'bg-primary text-primary-foreground border-primary shadow-lg shadow-primary/20'
                          : 'border-border bg-muted/50 hover:bg-muted'
                      }`}
                      onClick={() => setFormData({ ...formData, frequencia_dias: days })}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1 rounded-lg" onClick={() => setShowCreateModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 rounded-lg" data-testid="save-plano-btn">
                  <Shield className="h-4 w-4 mr-2" />
                  Criar Plano
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
