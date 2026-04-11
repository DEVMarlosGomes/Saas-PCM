import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Wrench, Eye, EyeOff, ArrowRight, Building2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

const benefits = [
  "10 equipamentos grátis",
  "5 usuários inclusos",
  "50 OS por mês",
  "Dashboard de KPIs",
  "Sem cartão de crédito",
];

export default function RegisterPage() {
  const { register } = useAuth();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgNome, setOrgNome] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!nome || !email || !password) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    if (password.length < 6) {
      toast.error("A senha deve ter pelo menos 6 caracteres");
      return;
    }
    setLoading(true);
    const result = await register(email, password, nome, orgNome);
    setLoading(false);
    if (!result.success) {
      toast.error(result.error);
    } else {
      toast.success("Conta criada com sucesso!");
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left side - Premium gradient */}
      <div className="hidden lg:flex lg:w-[55%] login-gradient relative overflow-hidden">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.03) 1px, transparent 0)`,
          backgroundSize: '40px 40px'
        }} />

        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Top Logo */}
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-white/10 backdrop-blur-sm border border-white/10">
              <Wrench className="h-6 w-6 text-white" />
            </div>
            <div>
              <span className="font-heading font-bold text-xl text-white">PCM</span>
              <span className="text-white/40 text-xs block">SaaS Platform</span>
            </div>
          </div>

          {/* Center Content */}
          <div className="max-w-lg">
            <h1 className="font-heading text-4xl xl:text-5xl font-bold text-white leading-tight mb-6">
              Comece
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-blue-400">
                Gratuitamente
              </span>
            </h1>
            <p className="text-lg text-white/60 mb-10 leading-relaxed">
              Crie sua conta e comece a gerenciar a manutenção industrial da sua empresa em minutos.
            </p>

            {/* Benefits */}
            <div className="space-y-3">
              {benefits.map((benefit, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 animate-slide-in-left"
                  style={{ animationDelay: `${i * 80}ms` }}
                >
                  <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                  <span className="text-white/70 text-sm">{benefit}</span>
                </div>
              ))}
            </div>

            <div className="mt-10 p-5 rounded-xl bg-white/5 backdrop-blur-sm border border-white/5">
              <div className="flex items-center gap-2 mb-2">
                <Building2 className="h-5 w-5 text-blue-400" />
                <span className="text-sm font-semibold text-white">Multi-Tenant SaaS</span>
              </div>
              <p className="text-xs text-white/40 leading-relaxed">
                Cada organização tem seus dados completamente isolados.
                Segurança enterprise desde o plano gratuito.
              </p>
            </div>
          </div>

          <p className="text-xs text-white/20">
            © 2026 PCM SaaS — Planejamento e Controle de Manutenção
          </p>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <div className="w-full max-w-[380px]">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary text-primary-foreground">
              <Wrench className="h-5 w-5" />
            </div>
            <div>
              <span className="font-heading font-bold text-xl">PCM</span>
              <span className="text-muted-foreground text-xs block">SaaS Platform</span>
            </div>
          </div>

          <h2 className="font-heading text-2xl font-bold mb-1">Criar conta</h2>
          <p className="text-muted-foreground text-sm mb-8">
            Preencha os dados para começar a usar o PCM
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nome" className="text-sm font-medium">Seu nome *</Label>
              <Input
                id="nome"
                type="text"
                placeholder="João Silva"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                data-testid="register-nome-input"
                className="h-11 rounded-lg bg-muted/50 border-border/50 focus:bg-background transition-colors"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">Email *</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="register-email-input"
                className="h-11 rounded-lg bg-muted/50 border-border/50 focus:bg-background transition-colors"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">Senha *</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Mínimo 6 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="register-password-input"
                  className="h-11 rounded-lg pr-10 bg-muted/50 border-border/50 focus:bg-background transition-colors"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 text-muted-foreground"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="org" className="text-sm font-medium">
                Nome da empresa <span className="text-muted-foreground font-normal">(opcional)</span>
              </Label>
              <Input
                id="org"
                type="text"
                placeholder="Minha Indústria LTDA"
                value={orgNome}
                onChange={(e) => setOrgNome(e.target.value)}
                data-testid="register-org-input"
                className="h-11 rounded-lg bg-muted/50 border-border/50 focus:bg-background transition-colors"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-11 rounded-lg text-sm font-semibold shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all duration-300 mt-2"
              disabled={loading}
              data-testid="register-submit-btn"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Criando conta...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Criar conta grátis
                  <ArrowRight className="h-4 w-4" />
                </span>
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Já tem uma conta?{" "}
            <Link
              to="/login"
              className="text-primary font-medium hover:underline underline-offset-4"
              data-testid="login-link"
            >
              Entrar
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
