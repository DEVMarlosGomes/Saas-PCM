import { Lock } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

/**
 * Financial access levels:
 *   'full' — admin: all values visible
 *   'none' — lider (different setor), tecnico, operador: values blurred
 *
 * Rules:
 *   admin            → full (all pages, all setores)
 *   lider + setor match OR setor=null passed explicitly as 'own'
 *                    → full for their own setor's data
 *   lider + org-wide (setor=null default)
 *                    → none (org-wide totals hidden)
 *   tecnico/operador → none (always blurred)
 */
export function useFinancialAccess(setor = null) {
  const { user } = useAuth();
  if (!user) return 'none';
  const role = user.role;
  if (role === 'admin' || role === 'superusuario') return 'full';
  if (role === 'lider') {
    if (setor && user.setor && setor.toUpperCase() === user.setor.toUpperCase()) return 'full';
    return 'none';
  }
  return 'none';
}

/**
 * BlurredMoney — visual placeholder shown when access is restricted.
 * size: 'sm' | 'md' | 'lg'
 * color: 'neutral' | 'red' | 'blue'
 */
export function BlurredMoney({ size = 'sm', color = 'neutral', className = '' }) {
  const sizeClass = { lg: 'text-2xl', md: 'text-lg', sm: 'text-sm' }[size] ?? 'text-sm';
  const colorClass = { red: 'text-red-400', blue: 'text-blue-400', neutral: 'text-foreground' }[color] ?? 'text-foreground';
  return (
    <span
      className={`inline-flex items-center gap-1 cursor-not-allowed ${className}`}
      title="Acesso restrito ao seu perfil"
    >
      <span
        className={`font-mono font-semibold ${sizeClass} ${colorClass} select-none`}
        style={{ filter: 'blur(6px)', userSelect: 'none' }}
        aria-hidden="true"
      >
        R$ 9.999,99
      </span>
      <Lock className="h-3 w-3 text-muted-foreground flex-shrink-0" aria-label="Acesso restrito" />
    </span>
  );
}

/**
 * MoneyValue — formats a currency value OR shows BlurredMoney.
 *
 * Usage:
 *   <MoneyValue value={1234.56} />                    // admin-only (no setor)
 *   <MoneyValue value={1234.56} setor="MECÂNICA" />   // lider sees if setor matches
 */
export function MoneyValue({ value, setor = null, className = '', decimals = 2, size = 'sm', color = 'neutral' }) {
  const access = useFinancialAccess(setor);
  if (access === 'full') {
    const formatted = (value ?? 0).toLocaleString('pt-BR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return <span className={className}>R$ {formatted}</span>;
  }
  return <BlurredMoney size={size} color={color} className={className} />;
}

/**
 * FinancialGuard — renders children only when the user has financial access.
 * Falls back to <BlurredMoney> or a custom fallback node.
 *
 * Usage:
 *   <FinancialGuard setor="ELÉTRICA">...sensitive content...</FinancialGuard>
 */
export default function FinancialGuard({ children, setor = null, fallback }) {
  const access = useFinancialAccess(setor);
  if (access === 'full') return children;
  return fallback !== undefined ? fallback : <BlurredMoney />;
}
