import { useState, useEffect, useCallback } from "react";
import { getAuditoria } from "../lib/api";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, FileText, Filter, Plus, Edit, Trash2, Loader2,
  Shield, Clock, CheckCircle, ArrowRight, Wrench, Settings, Users,
  Calendar,
} from "lucide-react";

const acaoConfig = {
  create: { label: "Criação", icon: Plus, color: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  update: { label: "Atualização", icon: Edit, color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  delete: { label: "Exclusão", icon: Trash2, color: "bg-red-500/10 text-red-500 border-red-500/20" },
  auto_approve: { label: "Auto-Aprovação", icon: CheckCircle, color: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
};

const entidadeConfig = {
  equipamento: { label: "Equipamento", icon: Settings },
  ordem_servico: { label: "Ordem de Serviço", icon: Wrench },
  usuario: { label: "Usuário", icon: Users },
  grupo: { label: "Grupo", icon: FileText },
  plano_preventivo: { label: "Plano Preventivo", icon: Calendar },
};

export default function AuditoriaPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterEntidade, setFilterEntidade] = useState("all");
  const [expandedLog, setExpandedLog] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 100 };
      if (filterEntidade && filterEntidade !== "all") params.entidade = filterEntidade;
      const res = await getAuditoria(params);
      setLogs(res.data || []);
    } catch (error) {
      toast.error("Erro ao carregar auditoria");
    } finally {
      setLoading(false);
    }
  }, [filterEntidade]);

  useEffect(() => { loadData(); }, [loadData]);

  const parseChanges = (dados_novos) => {
    if (!dados_novos) return null;
    try {
      const parsed = typeof dados_novos === 'string' ? JSON.parse(dados_novos) : dados_novos;
      return parsed;
    } catch { return null; }
  };

  // Group logs by date
  const groupedLogs = logs.reduce((acc, log) => {
    const date = new Date(log.created_at).toLocaleDateString('pt-BR');
    if (!acc[date]) acc[date] = [];
    acc[date].push(log);
    return acc;
  }, {});

  return (
    <div className="space-y-6" data-testid="auditoria-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            Auditoria
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {logs.length} registros — Rastreabilidade completa
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={filterEntidade} onValueChange={setFilterEntidade}>
            <SelectTrigger className="w-[180px] rounded-lg h-10" data-testid="filter-entidade-select">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Filtrar" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              {Object.entries(entidadeConfig).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={loadData} className="rounded-lg h-10 w-10" data-testid="refresh-auditoria-btn">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : logs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 border border-dashed border-border rounded-xl">
          <Shield className="h-10 w-10 text-muted-foreground mb-3 opacity-40" />
          <p className="font-medium text-muted-foreground">Nenhum registro de auditoria</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedLogs).map(([date, dayLogs]) => (
            <div key={date}>
              {/* Date Header */}
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-semibold text-muted-foreground bg-muted px-3 py-1 rounded-full">
                  {date}
                </span>
                <div className="flex-1 h-px bg-border/50" />
                <span className="text-[10px] text-muted-foreground">{dayLogs.length} evento{dayLogs.length > 1 ? 's' : ''}</span>
              </div>

              {/* Day Events */}
              <div className="space-y-2 ml-1 border-l-2 border-border/30 pl-4">
                {dayLogs.map((log) => {
                  const acao = acaoConfig[log.acao] || acaoConfig.update;
                  const AcaoIcon = acao.icon;
                  const entidade = entidadeConfig[log.entidade] || { label: log.entidade, icon: FileText };
                  const EntidadeIcon = entidade.icon;
                  const changes = parseChanges(log.dados_novos);
                  const isExpanded = expandedLog === log.id;

                  return (
                    <div
                      key={log.id}
                      className={`relative border border-border/50 rounded-xl bg-card p-4 card-hover transition-all ${isExpanded ? 'ring-1 ring-primary/20' : ''}`}
                      data-testid={`auditoria-row-${log.id}`}
                    >
                      {/* Timeline dot */}
                      <div className="absolute -left-[21px] top-5 w-2.5 h-2.5 rounded-full bg-card border-2 border-primary" />

                      <div className="flex items-center gap-3">
                        {/* Icon */}
                        <div className="p-2 rounded-lg bg-muted/50 shrink-0">
                          <EntidadeIcon className="h-4 w-4 text-muted-foreground" />
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium">{entidade.label}</span>
                            <Badge className={`${acao.color} text-[10px] border rounded`}>
                              <AcaoIcon className="h-2.5 w-2.5 mr-1" />
                              {acao.label}
                            </Badge>
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
                            <Clock className="h-2.5 w-2.5" />
                            {new Date(log.created_at).toLocaleTimeString('pt-BR')}
                            <span className="opacity-50">•</span>
                            <code className="bg-muted px-1 rounded text-[9px]">{log.entidade_id?.slice(0, 8)}...</code>
                          </p>
                        </div>

                        {/* Expand button if changes exist */}
                        {changes && Object.keys(changes).length > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs rounded-lg"
                            onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                          >
                            <ArrowRight className={`h-3 w-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                            Detalhes
                          </Button>
                        )}
                      </div>

                      {/* Change Details */}
                      {isExpanded && changes && (
                        <div className="mt-3 pt-3 border-t border-border/30 space-y-2 animate-fade-in">
                          {Object.entries(changes).map(([field, value]) => (
                            <div key={field} className="rounded-lg bg-muted/30 p-2.5">
                              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{field}</p>
                              {typeof value === 'object' && value?.de !== undefined ? (
                                <div className="flex items-center gap-2 text-xs">
                                  <span className="bg-red-500/10 text-red-500 px-2 py-0.5 rounded line-through">{value.de || '(vazio)'}</span>
                                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                                  <span className="bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded">{value.para}</span>
                                </div>
                              ) : (
                                <p className="text-xs">{typeof value === 'string' ? value : JSON.stringify(value)}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
