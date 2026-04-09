import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Wrench, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

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
      {/* Left side - Background */}
      <div 
        className="hidden lg:flex lg:w-1/2 bg-cover bg-center relative"
        style={{
          backgroundImage: `url('https://static.prod-images.emergentagent.com/jobs/277eff2b-7ed2-44c4-a9ed-8edae04f3ac8/images/d742918958cc5d7f35e06b559dcbe116dcc0c450be2fd9c12f1287a834009065.png')`
        }}
      >
        <div className="absolute inset-0 bg-black/50" />
        <div className="relative z-10 flex flex-col justify-center p-12 text-white">
          <div className="flex items-center gap-3 mb-6">
            <Wrench className="h-10 w-10" />
            <span className="font-heading font-bold text-3xl">PCM</span>
          </div>
          <h1 className="font-heading text-4xl font-bold mb-4">
            Sistema de Gestão de Manutenção Industrial
          </h1>
          <p className="text-lg text-white/80">
            Controle operacional, análise financeira e tomada de decisão inteligente para sua indústria.
          </p>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <Wrench className="h-8 w-8 text-primary" />
            <span className="font-heading font-bold text-2xl">PCM</span>
          </div>

          <h2 className="font-heading text-2xl font-bold mb-2">Entrar</h2>
          <p className="text-muted-foreground mb-6">
            Acesse sua conta para continuar
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                className="rounded-sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Senha</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="login-password-input"
                  className="rounded-sm pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <Button
              type="submit"
              className="w-full rounded-sm"
              disabled={loading}
              data-testid="login-submit-btn"
            >
              {loading ? "Entrando..." : "Entrar"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Não tem uma conta?{" "}
            <Link to="/register" className="text-primary hover:underline" data-testid="register-link">
              Criar conta
            </Link>
          </p>

          <div className="mt-8 p-4 border border-border rounded-sm bg-muted/50">
            <p className="text-xs text-muted-foreground mb-2">Conta de demonstração:</p>
            <p className="text-sm font-mono">admin@demo.pcm / admin123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
