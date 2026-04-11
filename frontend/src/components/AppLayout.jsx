import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { Button } from "./ui/button";
import {
  LayoutDashboard,
  Settings,
  Wrench,
  ClipboardList,
  Calendar,
  Users,
  FileText,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
  CreditCard,
  Building2,
  ChevronLeft,
  ChevronRight,
  Bell,
  Search,
  Shield,
} from "lucide-react";
import { useState, useEffect } from "react";

const navSections = [
  {
    label: "Principal",
    items: [
      { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    ],
  },
  {
    label: "Operacional",
    items: [
      { to: "/equipamentos", icon: Settings, label: "Equipamentos" },
      { to: "/ordens-servico", icon: Wrench, label: "Ordens de Serviço" },
      { to: "/planos-preventivos", icon: Calendar, label: "PCM Preventiva" },
    ],
  },
  {
    label: "Gestão",
    items: [
      { to: "/usuarios", icon: Users, label: "Usuários", roles: ["admin", "lider"] },
      { to: "/auditoria", icon: FileText, label: "Auditoria", roles: ["admin", "lider"] },
    ],
  },
  {
    label: "Assinatura",
    items: [
      { to: "/billing", icon: CreditCard, label: "Planos & Billing", roles: ["admin"] },
      { to: "/settings", icon: Building2, label: "Configurações", roles: ["admin"] },
    ],
  },
];

const roleLabels = {
  admin: "Administrador",
  lider: "Líder Técnico",
  tecnico: "Técnico",
  operador: "Operador",
};

const roleBadgeColors = {
  admin: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  lider: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  tecnico: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  operador: "bg-amber-500/10 text-amber-500 border-amber-500/20",
};

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const canAccess = (item) => {
    if (!item.roles) return true;
    return item.roles.includes(user?.role);
  };

  const getInitials = (name) => {
    if (!name) return "?";
    return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
  };

  // Page title from current route
  const getPageTitle = () => {
    const path = location.pathname.replace("/", "");
    const map = {
      dashboard: "Dashboard",
      equipamentos: "Equipamentos",
      "ordens-servico": "Ordens de Serviço",
      "planos-preventivos": "PCM Preventiva",
      usuarios: "Usuários",
      auditoria: "Auditoria",
      billing: "Planos & Billing",
      settings: "Configurações",
    };
    return map[path] || "PCM";
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border/50 shrink-0">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-primary-foreground">
          <Wrench className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="animate-fade-in">
            <span className="font-heading font-bold text-lg tracking-tight">PCM</span>
            <span className="text-[10px] font-medium text-muted-foreground block -mt-0.5">Manutenção Industrial</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-5">
        {navSections.map((section) => {
          const visibleItems = section.items.filter(canAccess);
          if (visibleItems.length === 0) return null;

          return (
            <div key={section.label}>
              {!collapsed && (
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2 px-3">
                  {section.label}
                </p>
              )}
              <div className="space-y-0.5">
                {visibleItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      `relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                        isActive
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      } ${collapsed ? "justify-center" : ""}`
                    }
                    data-testid={`nav-${item.to.slice(1)}`}
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary" />
                        )}
                        <item.icon className={`h-[18px] w-[18px] shrink-0 ${isActive ? '' : 'group-hover:scale-110 transition-transform'}`} />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      {/* User section at bottom */}
      <div className="border-t border-border/50 p-3 shrink-0">
        {!collapsed ? (
          <div className="flex items-center gap-3 px-2 py-2">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-primary/10 text-primary text-sm font-bold shrink-0">
              {getInitials(user?.nome)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.nome}</p>
              <span className={`inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-md border font-medium ${roleBadgeColors[user?.role] || ''}`}>
                {roleLabels[user?.role]}
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
              onClick={handleLogout}
              title="Sair"
              data-testid="logout-btn"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-primary/10 text-primary text-sm font-bold">
              {getInitials(user?.nome)}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
              onClick={handleLogout}
              title="Sair"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background gradient-mesh">
      {/* Desktop Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 hidden lg:flex flex-col bg-card/80 backdrop-blur-xl border-r border-border/50 transition-all duration-300 ${
          collapsed ? "w-[68px]" : "w-[260px]"
        }`}
      >
        <SidebarContent />
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 flex items-center justify-center w-6 h-6 rounded-full bg-card border border-border shadow-sm text-muted-foreground hover:text-foreground transition-colors"
          title={collapsed ? "Expandir" : "Recolher"}
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
      </aside>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-[280px] bg-card border-r border-border transform transition-transform duration-300 lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <SidebarContent />
      </aside>

      {/* Main Content */}
      <div className={`transition-all duration-300 ${collapsed ? "lg:ml-[68px]" : "lg:ml-[260px]"}`}>
        {/* Top Header Bar */}
        <header className="sticky top-0 z-30 h-16 border-b border-border/50 bg-background/80 backdrop-blur-xl">
          <div className="flex items-center justify-between h-full px-4 lg:px-6">
            <div className="flex items-center gap-3">
              {/* Mobile menu button */}
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden h-9 w-9"
                onClick={() => setMobileOpen(!mobileOpen)}
                data-testid="mobile-menu-toggle"
              >
                {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>

              {/* Page title */}
              <div>
                <h1 className="font-heading text-lg font-bold leading-none">{getPageTitle()}</h1>
              </div>
            </div>

            {/* Right side actions */}
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-muted-foreground hover:text-foreground"
                onClick={toggleTheme}
                data-testid="theme-toggle"
              >
                {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
              </Button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-4 lg:p-6 max-w-[1600px] mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
