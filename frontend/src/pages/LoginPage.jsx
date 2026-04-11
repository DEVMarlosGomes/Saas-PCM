import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Wrench, Eye, EyeOff, ArrowRight, Zap, Shield, BarChart3 } from "lucide-react";
import { toast } from "sonner";

const features = [
  { icon: BarChart3, title: "Dashboard Inteligente", desc: "KPIs em tempo real para decisão rápida" },
  { icon: Zap, title: "Automação de OS", desc: "Workflow automatizado de manutenção" },
  { icon: Shield, title: "Multi-Tenant Seguro", desc: "Isolamento total entre organizações" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Preencha todos os campos");
      return;
    }
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (!result.success) {
      toast.error(result.error);
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
              Gestão de Manutenção
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                Industrial Inteligente
              </span>
            </h1>
            <p className="text-lg text-white/60 mb-10 leading-relaxed">
              Transforme dados de manutenção em decisões estratégicas. 
              MTTR, MTBF, custos e rankings — tudo em uma plataforma SaaS segura.
            </p>

            {/* Feature cards */}
            <div className="space-y-4">
              {features.map((feature, i) => (
                <div
                  key={i}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white/5 backdrop-blur-sm border border-white/5 hover:bg-white/8 transition-all duration-300"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-500/20 shrink-0">
                    <feature.icon className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{feature.title}</p>
                    <p className="text-xs text-white/40">{feature.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom */}
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

          <h2 className="font-heading text-2xl font-bold mb-1">Bem-vindo de volta</h2>
          <p className="text-muted-foreground text-sm mb-8">
            Entre com suas credenciais para acessar o sistema
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                className="h-11 rounded-lg bg-muted/50 border-border/50 focus:bg-background transition-colors"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm font-medium">Senha</Label>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="login-password-input"
                  className="h-11 rounded-lg pr-10 bg-muted/50 border-border/50 focus:bg-background transition-colors"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-11 rounded-lg text-sm font-semibold shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all duration-300"
              disabled={loading}
              data-testid="login-submit-btn"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Entrando...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Entrar
                  <ArrowRight className="h-4 w-4" />
                </span>
              )}
            </Button>
          </form>

          <div className="mt-8 flex items-center gap-3">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">ou</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Não tem uma conta?{" "}
            <Link
              to="/register"
              className="text-primary font-medium hover:underline underline-offset-4"
              data-testid="register-link"
            >
              Criar conta grátis
            </Link>
          </p>

          {/* Demo credentials */}
          <div className="mt-8 p-4 rounded-lg border border-border bg-muted/30">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <p className="text-xs font-medium text-muted-foreground">Conta de demonstração</p>
            </div>
            <p className="text-sm font-mono text-foreground">admin@demo.pcm</p>
            <p className="text-xs font-mono text-muted-foreground">admin123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
