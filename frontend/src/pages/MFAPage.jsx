import React, { useState, useCallback } from 'react';
import { Shield, QrCode, Key, CheckCircle, AlertTriangle, Copy, Eye, EyeOff } from 'lucide-react';
import { mfaSetup, mfaEnable, mfaDisable, mfaBackupCount } from '../lib/api';

export default function MFAPage() {
  const [step, setStep] = useState('idle'); // idle | scanning | codes | done | disabling
  const [qrUri, setQrUri] = useState('');
  const [code, setCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [backupCount, setBackupCount] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadBackupCount = useCallback(async () => {
    try {
      const { data } = await mfaBackupCount();
      setBackupCount(data.remaining);
    } catch {
      setBackupCount(null);
    }
  }, []);

  React.useEffect(() => { loadBackupCount(); }, [loadBackupCount]);

  const handleSetup = async () => {
    setError(''); setLoading(true);
    try {
      const { data } = await mfaSetup();
      setQrUri(data.provisioning_uri);
      setStep('scanning');
    } catch (e) {
      setError(e.response?.data?.detail || 'Erro ao iniciar configuração MFA');
    } finally { setLoading(false); }
  };

  const handleEnable = async () => {
    if (code.length !== 6) { setError('Digite os 6 dígitos do código'); return; }
    setError(''); setLoading(true);
    try {
      const { data } = await mfaEnable(code);
      setBackupCodes(data.backup_codes);
      setStep('codes');
    } catch (e) {
      setError(e.response?.data?.detail || 'Código inválido ou expirado');
    } finally { setLoading(false); }
  };

  const handleDisable = async () => {
    setError(''); setLoading(true);
    try {
      await mfaDisable(disablePassword, disableCode);
      setStep('idle');
      setBackupCount(null);
      setDisablePassword(''); setDisableCode('');
    } catch (e) {
      setError(e.response?.data?.detail || 'Senha ou código incorretos');
    } finally { setLoading(false); }
  };

  const copyAll = () => {
    navigator.clipboard.writeText(backupCodes.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const qrImageUrl = qrUri
    ? `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUri)}`
    : null;

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      <div className="flex items-center gap-3 mb-8">
        <Shield className="w-7 h-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Autenticação em Dois Fatores</h1>
          <p className="text-slate-400 text-sm mt-1">TOTP via Google Authenticator, Authy ou similar</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 mb-6 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Estado: MFA ativo */}
      {backupCount !== null && step === 'idle' && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 text-green-400 font-semibold mb-2">
            <CheckCircle className="w-5 h-5" />
            MFA Ativo
          </div>
          <p className="text-slate-300 text-sm">
            {backupCount} código(s) de recuperação restantes.
          </p>
          <button
            onClick={() => setStep('disabling')}
            className="mt-4 text-sm text-red-400 hover:text-red-300 underline"
          >
            Desativar MFA
          </button>
        </div>
      )}

      {/* Estado: MFA não ativo */}
      {backupCount === null && step === 'idle' && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <p className="text-slate-300 mb-4">
            MFA adiciona uma camada extra de proteção. Após ativar, será necessário um código
            do seu app autenticador em cada login.
          </p>
          <button
            onClick={handleSetup}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
          >
            <QrCode className="w-4 h-4" />
            {loading ? 'Aguarde...' : 'Configurar MFA'}
          </button>
        </div>
      )}

      {/* Passo 1: Escanear QR */}
      {step === 'scanning' && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
          <h2 className="text-lg font-semibold text-white">1. Escaneie o QR Code</h2>
          <p className="text-slate-400 text-sm">
            Abra seu app autenticador (Google Authenticator, Authy) e escaneie:
          </p>
          {qrImageUrl && (
            <div className="flex justify-center">
              <img src={qrImageUrl} alt="QR Code MFA" className="rounded-lg border-4 border-white" width={200} height={200} />
            </div>
          )}
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-white mb-2">2. Digite o código gerado</h3>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="000000"
              className="w-full bg-slate-900 border border-slate-600 text-white text-center text-2xl tracking-[0.5em] rounded-lg px-4 py-3 focus:border-blue-500 focus:outline-none"
            />
            <button
              onClick={handleEnable}
              disabled={loading || code.length !== 6}
              className="mt-3 w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              {loading ? 'Verificando...' : 'Ativar MFA'}
            </button>
          </div>
        </div>
      )}

      {/* Passo 2: Backup codes */}
      {step === 'codes' && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle className="w-5 h-5" />
            <h2 className="text-lg font-semibold text-white">MFA Ativado!</h2>
          </div>
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
            <p className="text-amber-400 text-sm font-medium">
              Guarde estes códigos em local seguro. Eles não serão exibidos novamente.
              Use um deles caso perca acesso ao seu autenticador.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {backupCodes.map((c, i) => (
              <div key={i} className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-center">
                <span className="font-mono text-sm text-slate-200">{c}</span>
              </div>
            ))}
          </div>
          <button
            onClick={copyAll}
            className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            <Copy className="w-4 h-4" />
            {copied ? 'Copiado!' : 'Copiar todos'}
          </button>
          <button
            onClick={() => { setStep('idle'); setBackupCount(backupCodes.length); setCode(''); }}
            className="w-full bg-green-600 hover:bg-green-500 text-white py-2.5 rounded-lg font-medium transition-colors"
          >
            Concluir
          </button>
        </div>
      )}

      {/* Desativar MFA */}
      {step === 'disabling' && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">Desativar MFA</h2>
          <p className="text-slate-400 text-sm">Confirme sua senha e um código TOTP válido:</p>

          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              placeholder="Sua senha atual"
              className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-2.5 pr-10 focus:border-blue-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={disableCode}
            onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ''))}
            placeholder="Código TOTP (6 dígitos)"
            className="w-full bg-slate-900 border border-slate-600 text-white text-center text-xl tracking-widest rounded-lg px-4 py-2.5 focus:border-blue-500 focus:outline-none"
          />

          <div className="flex gap-3">
            <button
              onClick={() => setStep('idle')}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={handleDisable}
              disabled={loading || !disablePassword || disableCode.length !== 6}
              className="flex-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              {loading ? 'Aguarde...' : 'Desativar'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
