import { useState, useEffect } from "react";
import { getAuditoria } from "../lib/api";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw,
  FileText,
  Filter,
  Plus,
  Edit,
  Trash2
} from "lucide-react";

const acaoConfig = {
  create: { label: "Criação", icon: Plus, color: "bg-green-500/10 text-green-600 dark:text-green-400" },
  update: { label: "Atualização", icon: Edit, color: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  delete: { label: "Exclusão", icon: Trash2, color: "bg-red-500/10 text-red-600 dark:text-red-400" }
};

const entidadeLabels = {
  equipamento: "Equipamento",
  ordem_servico: "Ordem de Serviço",
  usuario: "Usuário",
  grupo: "Grupo",
  plano_preventivo: "Plano Preventivo"
};

export default function AuditoriaPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterEntidade, setFilterEntidade] = useState("all");

  const loadData = async () => {
    setLoading(true);
    try {
      const params = { limit: 100 };
      if (filterEntidade && filterEntidade !== "all") params.entidade = filterEntidade;
      const res = await getAuditoria(params);
      setLogs(res.data);
    } catch (error) {
      toast.error("Erro ao carregar auditoria");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterEntidade]);

  return (
    <div className="space-y-6" data-testid="auditoria-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Auditoria</h1>
          <p className="text-muted-foreground">Histórico de alterações do sistema</p>
        </div>
        <div className="flex gap-2">
          <Select value={filterEntidade} onValueChange={setFilterEntidade}>
            <SelectTrigger className="w-[180px] rounded-sm" data-testid="filter-entidade-select">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Filtrar por tipo" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="equipamento">Equipamento</SelectItem>
              <SelectItem value="ordem_servico">Ordem de Serviço</SelectItem>
              <SelectItem value="usuario">Usuário</SelectItem>
              <SelectItem value="grupo">Grupo</SelectItem>
              <SelectItem value="plano_preventivo">Plano Preventivo</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={loadData} className="rounded-sm" data-testid="refresh-auditoria-btn">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="text-center py-8 text-muted-foreground">Carregando...</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-border rounded-sm">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">Nenhum registro de auditoria encontrado</p>
        </div>
      ) : (
        <div className="border border-border rounded-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full table-dense">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left font-medium p-3">Data/Hora</th>
                  <th className="text-left font-medium p-3">Entidade</th>
                  <th className="text-center font-medium p-3">Ação</th>
                  <th className="text-left font-medium p-3 hidden lg:table-cell">ID</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const AcaoIcon = acaoConfig[log.acao]?.icon || Edit;
                  return (
                    <tr key={log.id} className="border-t border-border hover:bg-muted/50" data-testid={`auditoria-row-${log.id}`}>
                      <td className="p-3">
                        <div className="text-sm font-medium">
                          {new Date(log.created_at).toLocaleDateString('pt-BR')}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(log.created_at).toLocaleTimeString('pt-BR')}
                        </div>
                      </td>
                      <td className="p-3">
                        <span className="font-medium">
                          {entidadeLabels[log.entidade] || log.entidade}
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        <Badge className={`${acaoConfig[log.acao]?.color} rounded-sm`}>
                          <AcaoIcon className="h-3 w-3 mr-1" />
                          {acaoConfig[log.acao]?.label || log.acao}
                        </Badge>
                      </td>
                      <td className="p-3 hidden lg:table-cell">
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {log.entidade_id.slice(0, 8)}...
                        </code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
