import React, { useState, useEffect, useCallback } from 'react';
import {
  getPecas, createPeca, updatePeca, desativarPeca,
  getDepositos, createDeposito,
  getSaldoEstoque, getAbaixoPontoPedido, registrarMovimento,
  getMovimentos, getFornecedores,
} from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

const R_ESTOQUE_LIDER = ['admin', 'gerente_industrial', 'supervisor_manutencao',
  'lider', 'lider_manutencao_eletrica', 'lider_manutencao_mecanica',
  'analista_manutencao', 'engenheiro_manutencao'];

function fmt(val, dec = 2) {
  if (val == null) return '—';
  return Number(val).toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function Badge({ cor, children }) {
  const map = {
    red: 'bg-red-900/40 text-red-300 border-red-700',
    yellow: 'bg-yellow-900/40 text-yellow-300 border-yellow-700',
    green: 'bg-green-900/40 text-green-300 border-green-700',
    gray: 'bg-gray-800 text-gray-400 border-gray-700',
  };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-medium ${map[cor] || map.gray}`}>
      {children}
    </span>
  );
}

// ── Modal de Peça ─────────────────────────────────────────────────────────────
function PecaModal({ peca, fornecedores, onClose, onSave }) {
  const editando = !!peca?.id;
  const [form, setForm] = useState({
    codigo: peca?.codigo || '',
    descricao: peca?.descricao || '',
    unidade: peca?.unidade || 'un',
    custo_unitario: peca?.custo_unitario || '',
    ponto_pedido: peca?.ponto_pedido || 0,
    lote_economico: peca?.lote_economico || '',
    fornecedor_principal_id: peca?.fornecedor_principal_id || '',
    permitir_saldo_negativo: peca?.permitir_saldo_negativo || false,
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true); setErr('');
    try {
      const payload = {
        ...form,
        custo_unitario: parseFloat(form.custo_unitario) || 0,
        ponto_pedido: parseFloat(form.ponto_pedido) || 0,
        lote_economico: form.lote_economico ? parseFloat(form.lote_economico) : null,
        fornecedor_principal_id: form.fornecedor_principal_id || null,
      };
      if (editando) {
        await updatePeca(peca.id, payload);
      } else {
        await createPeca(payload);
      }
      onSave();
    } catch (e) {
      setErr(e.response?.data?.detail || 'Erro ao salvar peça.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg">
        <div className="flex items-center justify-between p-5 border-b border-gray-700">
          <h2 className="text-white font-semibold">{editando ? 'Editar Peça' : 'Nova Peça'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Código *</label>
              <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm uppercase"
                value={form.codigo} onChange={e => setForm(f => ({ ...f, codigo: e.target.value.toUpperCase() }))}
                required disabled={editando} placeholder="EX-001" />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Unidade</label>
              <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={form.unidade} onChange={e => setForm(f => ({ ...f, unidade: e.target.value }))}>
                {['un', 'kg', 'm', 'L', 'cx', 'par', 'jg', 'rolo', 'lt'].map(u => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Descrição *</label>
            <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              value={form.descricao} onChange={e => setForm(f => ({ ...f, descricao: e.target.value }))}
              required placeholder="Ex: Rolamento SKF 6205 2RS" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Custo Unitário (R$) *</label>
              <input type="number" step="0.01" min="0" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={form.custo_unitario} onChange={e => setForm(f => ({ ...f, custo_unitario: e.target.value }))} required />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Ponto de Pedido</label>
              <input type="number" step="0.01" min="0" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={form.ponto_pedido} onChange={e => setForm(f => ({ ...f, ponto_pedido: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Lote Econômico</label>
              <input type="number" step="0.01" min="0" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={form.lote_economico} onChange={e => setForm(f => ({ ...f, lote_economico: e.target.value }))} placeholder="—" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Fornecedor Principal</label>
            <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              value={form.fornecedor_principal_id} onChange={e => setForm(f => ({ ...f, fornecedor_principal_id: e.target.value }))}>
              <option value="">— Nenhum —</option>
              {fornecedores.map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
            <input type="checkbox" checked={form.permitir_saldo_negativo}
              onChange={e => setForm(f => ({ ...f, permitir_saldo_negativo: e.target.checked }))}
              className="accent-amber-500" />
            Permitir saldo negativo (alerta mas não bloqueia baixa)
          </label>
          {err && <p className="text-red-400 text-sm">{err}</p>}
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 text-sm">
              Cancelar
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium disabled:opacity-50">
              {loading ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Modal de Movimento Manual ─────────────────────────────────────────────────
function MovimentoModal({ pecas, depositos, onClose, onSave }) {
  const [form, setForm] = useState({ peca_id: '', deposito_id: '', tipo: 'entrada', quantidade: '', custo_unitario: '', motivo: '' });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true); setErr('');
    try {
      const payload = {
        peca_id: form.peca_id,
        deposito_id: form.deposito_id,
        tipo: form.tipo,
        quantidade: parseFloat(form.quantidade),
        custo_unitario: form.custo_unitario ? parseFloat(form.custo_unitario) : undefined,
        motivo: form.motivo || undefined,
      };
      await registrarMovimento(payload);
      onSave();
    } catch (e) {
      setErr(e.response?.data?.detail || 'Erro ao registrar movimento.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-gray-700">
          <h2 className="text-white font-semibold">Registrar Movimento</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Tipo *</label>
            <div className="flex gap-2">
              {[['entrada', '📥 Entrada'], ['saida', '📤 Saída'], ['ajuste', '⚖️ Ajuste']].map(([val, label]) => (
                <button key={val} type="button"
                  onClick={() => setForm(f => ({ ...f, tipo: val }))}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${form.tipo === val ? 'bg-amber-600 border-amber-500 text-white' : 'border-gray-700 text-gray-400 hover:bg-gray-800'}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Peça *</label>
            <select required className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              value={form.peca_id} onChange={e => setForm(f => ({ ...f, peca_id: e.target.value }))}>
              <option value="">Selecione…</option>
              {pecas.map(p => <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Depósito *</label>
            <select required className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              value={form.deposito_id} onChange={e => setForm(f => ({ ...f, deposito_id: e.target.value }))}>
              <option value="">Selecione…</option>
              {depositos.map(d => <option key={d.id} value={d.id}>{d.nome}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                {form.tipo === 'ajuste' ? 'Quantidade Final *' : 'Quantidade *'}
              </label>
              <input required type="number" step="0.001" min="0.001"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={form.quantidade} onChange={e => setForm(f => ({ ...f, quantidade: e.target.value }))} />
            </div>
            {form.tipo === 'entrada' && (
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Custo Unitário (R$) *</label>
                <input required type="number" step="0.01" min="0"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  value={form.custo_unitario} onChange={e => setForm(f => ({ ...f, custo_unitario: e.target.value }))} />
              </div>
            )}
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Motivo</label>
            <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              value={form.motivo} onChange={e => setForm(f => ({ ...f, motivo: e.target.value }))}
              placeholder="Ex: Compra NF 1234, Inventário anual…" />
          </div>
          {err && <p className="text-red-400 text-sm">{err}</p>}
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 text-sm">
              Cancelar
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium disabled:opacity-50">
              {loading ? 'Registrando…' : 'Confirmar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────
export default function EstoquePage() {
  const { user } = useAuth();
  const isLider = R_ESTOQUE_LIDER.includes(user?.role);

  const [aba, setAba] = useState('pecas');
  const [pecas, setPecas] = useState([]);
  const [saldos, setSaldos] = useState([]);
  const [depositos, setDepositos] = useState([]);
  const [fornecedores, setFornecedores] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const [movimentos, setMovimentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState('');
  const [showPecaModal, setShowPecaModal] = useState(false);
  const [editPeca, setEditPeca] = useState(null);
  const [showMovModal, setShowMovModal] = useState(false);
  const [showDepositoModal, setShowDepositoModal] = useState(false);
  const [novoDeposito, setNovoDeposito] = useState({ nome: '', localizacao: '' });
  const [err402, setErr402] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const [rPecas, rSaldos, rDep, rForn, rAlertas, rMov] = await Promise.all([
        getPecas(),
        getSaldoEstoque(),
        getDepositos(),
        getFornecedores(),
        getAbaixoPontoPedido(),
        getMovimentos({ limit: 50 }),
      ]);
      setPecas(rPecas.data);
      setSaldos(rSaldos.data);
      setDepositos(rDep.data);
      setFornecedores(rForn.data);
      setAlertas(rAlertas.data);
      setMovimentos(rMov.data);
    } catch (e) {
      if (e.response?.status === 402) setErr402(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  if (err402) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="text-4xl">🔒</div>
        <h2 className="text-white text-xl font-semibold">Módulo de Almoxarifado</h2>
        <p className="text-gray-400 text-center max-w-sm">
          Este módulo está disponível a partir do plano <strong className="text-amber-400">Profissional</strong>.
          Faça upgrade para acessar controle de estoque, catálogo de peças e rastreabilidade de consumo.
        </p>
        <button onClick={() => window.location.href = '/billing'}
          className="px-6 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium">
          Ver Planos
        </button>
      </div>
    );
  }

  const pecasFiltradas = pecas.filter(p =>
    !busca || p.codigo.toLowerCase().includes(busca.toLowerCase()) ||
    p.descricao.toLowerCase().includes(busca.toLowerCase())
  );

  function getSaldoPeca(pecaId) {
    return saldos.filter(s => s.peca_id === pecaId).reduce((acc, s) => acc + s.quantidade, 0);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Almoxarifado</h1>
          <p className="text-gray-400 text-sm mt-0.5">Gestão de peças, saldos e movimentos</p>
        </div>
        {isLider && (
          <div className="flex gap-2">
            {aba === 'pecas' && (
              <button onClick={() => { setEditPeca(null); setShowPecaModal(true); }}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium">
                + Nova Peça
              </button>
            )}
            {(aba === 'saldos' || aba === 'movimentos') && (
              <button onClick={() => setShowMovModal(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium">
                + Registrar Movimento
              </button>
            )}
            {aba === 'depositos' && (
              <button onClick={() => setShowDepositoModal(true)}
                className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white rounded-lg text-sm font-medium">
                + Novo Depósito
              </button>
            )}
          </div>
        )}
      </div>

      {/* Alertas de ponto de pedido */}
      {alertas.length > 0 && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-red-400 text-lg">⚠️</span>
            <span className="text-red-300 font-medium">{alertas.length} {alertas.length === 1 ? 'item abaixo' : 'itens abaixo'} do ponto de pedido</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {alertas.map(a => (
              <span key={a.peca_id + a.deposito_id}
                className="px-3 py-1 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-xs">
                <span className="font-mono font-bold">{a.peca_codigo}</span> — {a.peca_descricao.substring(0, 30)}
                {a.peca_descricao.length > 30 ? '…' : ''}
                {' '}| Saldo: {fmt(a.quantidade)} {a.peca_unidade} (mín: {fmt(a.ponto_pedido)})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Abas */}
      <div className="flex gap-1 bg-gray-800/50 p-1 rounded-xl w-fit">
        {[['pecas', '📦 Peças'], ['saldos', '📊 Saldos'], ['movimentos', '📋 Movimentos'], ['depositos', '🏪 Depósitos']].map(([id, label]) => (
          <button key={id} onClick={() => setAba(id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${aba === id ? 'bg-amber-600 text-white' : 'text-gray-400 hover:text-white'}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* ── Aba Peças ─────────────────────────────────────────── */}
          {aba === 'pecas' && (
            <div className="space-y-4">
              <input
                className="w-full max-w-sm bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm placeholder-gray-500"
                placeholder="Buscar por código ou descrição…"
                value={busca} onChange={e => setBusca(e.target.value)}
              />
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700 text-gray-400 text-xs">
                      <th className="px-4 py-3 text-left">Código</th>
                      <th className="px-4 py-3 text-left">Descrição</th>
                      <th className="px-4 py-3 text-center">Unidade</th>
                      <th className="px-4 py-3 text-right">Saldo Total</th>
                      <th className="px-4 py-3 text-right">Custo Médio</th>
                      <th className="px-4 py-3 text-right">Valor em Estoque</th>
                      <th className="px-4 py-3 text-center">Status</th>
                      {isLider && <th className="px-4 py-3 text-center">Ações</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {pecasFiltradas.length === 0 && (
                      <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">Nenhuma peça encontrada.</td></tr>
                    )}
                    {pecasFiltradas.map(p => {
                      const saldoTotal = getSaldoPeca(p.id);
                      const abaixo = saldoTotal <= p.ponto_pedido && p.ponto_pedido > 0;
                      const valor = saldoTotal * (parseFloat(p.custo_medio) || 0);
                      return (
                        <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/30">
                          <td className="px-4 py-3 font-mono text-amber-400 font-medium">{p.codigo}</td>
                          <td className="px-4 py-3 text-white max-w-xs">
                            <div>{p.descricao}</div>
                            {p.fornecedor_nome && <div className="text-xs text-gray-500 mt-0.5">{p.fornecedor_nome}</div>}
                          </td>
                          <td className="px-4 py-3 text-center text-gray-400">{p.unidade}</td>
                          <td className={`px-4 py-3 text-right font-mono font-medium ${abaixo ? 'text-red-400' : 'text-white'}`}>
                            {fmt(saldoTotal)} {abaixo && <span className="text-red-500 ml-1">⚠</span>}
                          </td>
                          <td className="px-4 py-3 text-right text-gray-300 font-mono">R$ {fmt(p.custo_medio)}</td>
                          <td className="px-4 py-3 text-right text-gray-300 font-mono">R$ {fmt(valor)}</td>
                          <td className="px-4 py-3 text-center">
                            {abaixo
                              ? <Badge cor="red">Repor</Badge>
                              : saldoTotal === 0
                                ? <Badge cor="yellow">Sem estoque</Badge>
                                : <Badge cor="green">OK</Badge>
                            }
                          </td>
                          {isLider && (
                            <td className="px-4 py-3 text-center">
                              <button onClick={() => { setEditPeca(p); setShowPecaModal(true); }}
                                className="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded">
                                Editar
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Aba Saldos ────────────────────────────────────────── */}
          {aba === 'saldos' && (
            <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400 text-xs">
                    <th className="px-4 py-3 text-left">Peça</th>
                    <th className="px-4 py-3 text-left">Depósito</th>
                    <th className="px-4 py-3 text-right">Quantidade</th>
                    <th className="px-4 py-3 text-right">Custo Médio</th>
                    <th className="px-4 py-3 text-right">Valor Total</th>
                    <th className="px-4 py-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {saldos.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Nenhum saldo registrado.</td></tr>
                  )}
                  {saldos.map((s, i) => (
                    <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/30">
                      <td className="px-4 py-3">
                        <span className="font-mono text-amber-400 text-xs">{s.peca_codigo}</span>
                        <span className="text-gray-300 ml-2">{s.peca_descricao}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-400">{s.deposito_nome}</td>
                      <td className={`px-4 py-3 text-right font-mono font-medium ${s.abaixo_ponto_pedido ? 'text-red-400' : 'text-white'}`}>
                        {fmt(s.quantidade)} {s.peca_unidade}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-300 font-mono">R$ {fmt(s.custo_medio)}</td>
                      <td className="px-4 py-3 text-right text-gray-300 font-mono">R$ {fmt(s.valor_total)}</td>
                      <td className="px-4 py-3 text-center">
                        {s.abaixo_ponto_pedido ? <Badge cor="red">Repor</Badge> : <Badge cor="green">OK</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Aba Movimentos ────────────────────────────────────── */}
          {aba === 'movimentos' && (
            <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400 text-xs">
                    <th className="px-4 py-3 text-left">Data</th>
                    <th className="px-4 py-3 text-left">Peça</th>
                    <th className="px-4 py-3 text-left">Depósito</th>
                    <th className="px-4 py-3 text-center">Tipo</th>
                    <th className="px-4 py-3 text-right">Qtd</th>
                    <th className="px-4 py-3 text-right">Custo Total</th>
                    <th className="px-4 py-3 text-left">Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {movimentos.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Nenhum movimento registrado.</td></tr>
                  )}
                  {movimentos.map(m => {
                    const tipoMap = { entrada: ['green', '📥 Entrada'], saida: ['red', '📤 Saída'], ajuste: ['yellow', '⚖️ Ajuste'] };
                    const [cor, label] = tipoMap[m.tipo] || ['gray', m.tipo];
                    return (
                      <tr key={m.id} className="border-b border-gray-800 hover:bg-gray-800/30">
                        <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                          {new Date(m.criado_em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-amber-400 text-xs">{m.peca_codigo}</span>
                          <span className="text-gray-300 ml-1 text-xs">{m.peca_descricao?.substring(0, 30)}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{m.deposito_nome}</td>
                        <td className="px-4 py-3 text-center"><Badge cor={cor}>{label}</Badge></td>
                        <td className="px-4 py-3 text-right font-mono text-white">{fmt(m.quantidade)}</td>
                        <td className="px-4 py-3 text-right font-mono text-gray-300">
                          {m.custo_total ? `R$ ${fmt(m.custo_total)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs max-w-xs truncate">{m.motivo || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Aba Depósitos ─────────────────────────────────────── */}
          {aba === 'depositos' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {depositos.length === 0 && (
                <p className="text-gray-500 col-span-3 text-center py-8">Nenhum depósito cadastrado.</p>
              )}
              {depositos.map(d => {
                const saldosDep = saldos.filter(s => s.deposito_id === d.id);
                const valorTotal = saldosDep.reduce((acc, s) => acc + parseFloat(s.valor_total || 0), 0);
                return (
                  <div key={d.id} className="bg-gray-900 border border-gray-700 rounded-xl p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="text-white font-medium">{d.nome}</h3>
                        {d.localizacao && <p className="text-gray-500 text-xs mt-0.5">{d.localizacao}</p>}
                      </div>
                      <Badge cor={d.ativo ? 'green' : 'gray'}>{d.ativo ? 'Ativo' : 'Inativo'}</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-gray-500 text-xs">Itens distintos</p>
                        <p className="text-white font-mono font-medium">{saldosDep.length}</p>
                      </div>
                      <div>
                        <p className="text-gray-500 text-xs">Valor em estoque</p>
                        <p className="text-amber-400 font-mono font-medium">R$ {fmt(valorTotal)}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Modais */}
      {showPecaModal && (
        <PecaModal peca={editPeca} fornecedores={fornecedores}
          onClose={() => { setShowPecaModal(false); setEditPeca(null); }}
          onSave={() => { setShowPecaModal(false); setEditPeca(null); carregar(); }} />
      )}
      {showMovModal && (
        <MovimentoModal pecas={pecas} depositos={depositos}
          onClose={() => setShowMovModal(false)}
          onSave={() => { setShowMovModal(false); carregar(); }} />
      )}
      {showDepositoModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-sm p-5">
            <h2 className="text-white font-semibold mb-4">Novo Depósito</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Nome *</label>
                <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  value={novoDeposito.nome} onChange={e => setNovoDeposito(d => ({ ...d, nome: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Localização</label>
                <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="Ex: Prateleira A3, Sala 102…"
                  value={novoDeposito.localizacao} onChange={e => setNovoDeposito(d => ({ ...d, localizacao: e.target.value }))} />
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={() => setShowDepositoModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 text-sm">
                  Cancelar
                </button>
                <button onClick={async () => {
                  if (!novoDeposito.nome) return;
                  await createDeposito(novoDeposito);
                  setShowDepositoModal(false);
                  setNovoDeposito({ nome: '', localizacao: '' });
                  carregar();
                }} className="flex-1 px-4 py-2 rounded-lg bg-green-700 hover:bg-green-600 text-white text-sm font-medium">
                  Criar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
