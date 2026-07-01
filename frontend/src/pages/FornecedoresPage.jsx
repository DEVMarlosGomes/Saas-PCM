import React, { useState, useEffect, useCallback } from 'react';
import { getFornecedores, createFornecedor, updateFornecedor } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

const R_LIDER = ['admin', 'gerente_industrial', 'supervisor_manutencao',
  'lider', 'lider_manutencao_eletrica', 'lider_manutencao_mecanica'];

function FornecedorModal({ fornecedor, onClose, onSave }) {
  const editando = !!fornecedor?.id;
  const [form, setForm] = useState({
    nome: fornecedor?.nome || '',
    cnpj: fornecedor?.cnpj || '',
    contato: fornecedor?.contato || '',
    email: fornecedor?.email || '',
    telefone: fornecedor?.telefone || '',
    observacoes: fornecedor?.observacoes || '',
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true); setErr('');
    try {
      if (editando) {
        await updateFornecedor(fornecedor.id, form);
      } else {
        await createFornecedor(form);
      }
      onSave();
    } catch (e) {
      setErr(e.response?.data?.detail || 'Erro ao salvar fornecedor.');
    } finally {
      setLoading(false);
    }
  }

  const F = ({ label, field, placeholder, type = 'text' }) => (
    <div>
      <label className="text-xs text-gray-400 mb-1 block">{label}</label>
      <input type={type} placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
        value={form[field]} onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))} />
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg">
        <div className="flex items-center justify-between p-5 border-b border-gray-700">
          <h2 className="text-white font-semibold">{editando ? 'Editar Fornecedor' : 'Novo Fornecedor'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <F label="Razão Social / Nome *" field="nome" placeholder="Ex: Rolamentos São Paulo Ltda" />
          <div className="grid grid-cols-2 gap-3">
            <F label="CNPJ" field="cnpj" placeholder="00.000.000/0001-00" />
            <F label="Telefone" field="telefone" placeholder="(11) 9 9999-9999" />
          </div>
          <F label="Nome do Contato" field="contato" placeholder="Ex: João Silva" />
          <F label="E-mail" field="email" placeholder="compras@fornecedor.com" type="email" />
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Observações</label>
            <textarea rows={3}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm resize-none"
              placeholder="Condições de pagamento, prazo de entrega, etc."
              value={form.observacoes} onChange={e => setForm(f => ({ ...f, observacoes: e.target.value }))} />
          </div>
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

export default function FornecedoresPage() {
  const { user } = useAuth();
  const isLider = R_LIDER.includes(user?.role);

  const [fornecedores, setFornecedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editForn, setEditForn] = useState(null);
  const [mostrarInativos, setMostrarInativos] = useState(false);
  const [err402, setErr402] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getFornecedores({ apenas_ativos: !mostrarInativos });
      setFornecedores(r.data);
    } catch (e) {
      if (e.response?.status === 402) setErr402(true);
    } finally {
      setLoading(false);
    }
  }, [mostrarInativos]);

  useEffect(() => { carregar(); }, [carregar]);

  if (err402) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="text-4xl">🔒</div>
        <p className="text-gray-400 text-center max-w-sm">
          Módulo de Almoxarifado disponível a partir do plano <strong className="text-amber-400">Profissional</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Fornecedores</h1>
          <p className="text-gray-400 text-sm mt-0.5">Cadastro de fornecedores de peças e insumos</p>
        </div>
        {isLider && (
          <button onClick={() => { setEditForn(null); setShowModal(true); }}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium">
            + Novo Fornecedor
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <input
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm placeholder-gray-500 w-full max-w-xs"
          placeholder="Buscar fornecedor…"
          value={busca} onChange={e => setBusca(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer whitespace-nowrap">
          <input type="checkbox" checked={mostrarInativos} onChange={e => setMostrarInativos(e.target.checked)}
            className="accent-amber-500" />
          Mostrar inativos
        </label>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {fornecedores
            .filter(f => !busca || f.nome.toLowerCase().includes(String(busca).toLowerCase()))
            .map(f => (
              <div key={f.id}
                className={`bg-gray-900 border rounded-xl p-5 space-y-3 ${f.ativo ? 'border-gray-700' : 'border-gray-800 opacity-60'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-white font-semibold truncate">{f.nome}</h3>
                    {f.cnpj && <p className="text-gray-500 text-xs mt-0.5">{f.cnpj}</p>}
                  </div>
                  <span className={`ml-2 px-2 py-0.5 rounded text-xs border ${f.ativo ? 'bg-green-900/30 text-green-400 border-green-800' : 'bg-gray-800 text-gray-500 border-gray-700'}`}>
                    {f.ativo ? 'Ativo' : 'Inativo'}
                  </span>
                </div>

                <div className="space-y-1 text-sm">
                  {f.contato && (
                    <div className="flex items-center gap-2 text-gray-400">
                      <span className="text-gray-600">👤</span> {f.contato}
                    </div>
                  )}
                  {f.email && (
                    <div className="flex items-center gap-2 text-gray-400">
                      <span className="text-gray-600">✉️</span>
                      <a href={`mailto:${f.email}`} className="hover:text-blue-400 truncate">{f.email}</a>
                    </div>
                  )}
                  {f.telefone && (
                    <div className="flex items-center gap-2 text-gray-400">
                      <span className="text-gray-600">📞</span> {f.telefone}
                    </div>
                  )}
                  {f.observacoes && (
                    <p className="text-gray-500 text-xs mt-2 line-clamp-2">{f.observacoes}</p>
                  )}
                </div>

                {isLider && (
                  <div className="flex gap-2 pt-1 border-t border-gray-800">
                    <button onClick={() => { setEditForn(f); setShowModal(true); }}
                      className="flex-1 text-xs text-blue-400 hover:text-blue-300 py-1 rounded hover:bg-gray-800">
                      Editar
                    </button>
                    {f.ativo && (
                      <button onClick={async () => {
                        await updateFornecedor(f.id, { ativo: false });
                        carregar();
                      }} className="flex-1 text-xs text-red-400 hover:text-red-300 py-1 rounded hover:bg-gray-800">
                        Desativar
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          {fornecedores.length === 0 && (
            <div className="col-span-3 text-center py-12">
              <div className="text-4xl mb-3">🏭</div>
              <p className="text-gray-400">Nenhum fornecedor cadastrado.</p>
              {isLider && (
                <button onClick={() => { setEditForn(null); setShowModal(true); }}
                  className="mt-3 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm">
                  Cadastrar primeiro fornecedor
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {showModal && (
        <FornecedorModal fornecedor={editForn}
          onClose={() => { setShowModal(false); setEditForn(null); }}
          onSave={() => { setShowModal(false); setEditForn(null); carregar(); }} />
      )}
    </div>
  );
}
