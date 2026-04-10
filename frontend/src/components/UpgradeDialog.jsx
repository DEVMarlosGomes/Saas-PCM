import { useNavigate } from "react-router-dom";
import { AlertTriangle, Zap, ArrowRight } from "lucide-react";
import { Button } from "./ui/button";

export default function UpgradeDialog({ open, onClose, message }) {
  const navigate = useNavigate();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-4 flex items-center gap-3">
          <div className="p-2 bg-amber-500/20 rounded-lg">
            <AlertTriangle className="h-6 w-6 text-amber-500" />
          </div>
          <div>
            <h3 className="font-heading font-bold text-lg">Limite Atingido</h3>
            <p className="text-xs text-muted-foreground">Plano atual não permite esta ação</p>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          <p className="text-sm text-foreground leading-relaxed">
            {message || "Você atingiu o limite do seu plano atual. Faça upgrade para continuar utilizando todos os recursos."}
          </p>

          <div className="mt-4 p-4 bg-primary/5 border border-primary/10 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold">Benefícios do Upgrade:</span>
            </div>
            <ul className="text-xs text-muted-foreground space-y-1.5 ml-6">
              <li>• Mais equipamentos e usuários</li>
              <li>• OS ilimitadas por mês</li>
              <li>• Relatórios avançados</li>
              <li>• Suporte prioritário</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            Entendi
          </Button>
          <Button size="sm" onClick={() => { onClose(); navigate('/billing'); }}>
            <ArrowRight className="h-4 w-4 mr-2" />
            Ver Planos
          </Button>
        </div>
      </div>
    </div>
  );
}
