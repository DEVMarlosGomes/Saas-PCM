import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Wrench, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

export default function RegisterPage() {
  const { register } = useAuth();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationNome, setOrganizationNome] = useState("");
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
    const result = await register(email, password, nome, organizationNome);
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
          backgroundImage: `url('https://images.unsplash.com/photo-1771530789155-b1f03fbf82b5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBpbmR1c3RyaWFsJTIwZmFjaWxpdHl8ZW58MHx8fHwxNzc1NzU4MjUzfDA&ixlib=rb-4.1.0&q=85')`
        }}
      >
        <div className="absolute inset-0 bg-black/50" />
        <div className="relative z-10 flex flex-col justify-center p-12 text-white">
          <div className="flex items-center gap-3 mb-6">
            <Wrench className="h-10 w-10" />
            <span className="font-heading font-bold text-3xl">PCM</span>
          </div>
          <h1 className="font-heading text-4xl font-bold mb-4">
            Comece a controlar sua manutenção
          </h1>
          <ul className="space-y-2 text-white/80">
            <li>• Reduza tempo de máquina parada</li>
            <li>• Controle custos de manutenção</li>
            <li>• Tome decisões baseadas em dados</li>
            <li>• Aumente a disponibilidade dos equipamentos</li>
          </ul>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <Wrench className="h-8 w-8 text-primary" />
            <span className="font-heading font-bold text-2xl">PCM</span>
          </div>

          <h2 className="font-heading text-2xl font-bold mb-2">Criar conta</h2>
          <p className="text-muted-foreground mb-6">
            Cadastre sua empresa gratuitamente
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nome">Seu nome *</Label>
              <Input
                id="nome"
                type="text"
                placeholder="João Silva"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                data-testid="register-nome-input"
                className="rounded-sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="register-email-input"
                className="rounded-sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Senha *</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Mínimo 6 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="register-password-input"
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

            <div className="space-y-2">
              <Label htmlFor="organization">Nome da empresa (opcional)</Label>
              <Input
                id="organization"
                type="text"
                placeholder="Minha Empresa Ltda"
                value={organizationNome}
                onChange={(e) => setOrganizationNome(e.target.value)}
                data-testid="register-org-input"
                className="rounded-sm"
              />
            </div>

            <Button
              type="submit"
              className="w-full rounded-sm"
              disabled={loading}
              data-testid="register-submit-btn"
            >
              {loading ? "Criando conta..." : "Criar conta"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Já tem uma conta?{" "}
            <Link to="/login" className="text-primary hover:underline" data-testid="login-link">
              Entrar
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
