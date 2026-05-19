import { useAuth } from '../../contexts/AuthContext';

/**
 * Renders children only for users with financial visibility (ADMIN).
 * Renders fallback (default: em-dash) for all other roles.
 */
export default function FinancialGuard({ children, fallback = '—' }) {
  const { user } = useAuth();

  if (!user || user.role !== 'admin') {
    return <span className="text-muted-foreground text-sm">{fallback}</span>;
  }

  return children;
}
