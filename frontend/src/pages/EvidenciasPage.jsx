import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  getChecklistTemplates, createChecklistTemplate, updateChecklistTemplate, desativarChecklistTemplate,
} from '../lib/api';

const R_LIDER = [
  'admin', 'gerente_industrial', 'supervisor_manutencao',
  'lider', 'lider_manutencao_eletrica', 'lider_manutencao_mecanica',
  'analista_manutencao', 'engenheiro_manutencao',
];

const TIPOS_OS = [
  { value: '', label: 'Todos os tipos' },
  { value: 'corretiva', label: 'Corretiva' },
  { value: 'preventiva', label: 'Preventiva' },
  { value: 'preditiva', label: 'Preditiva' },
];

// ─── Template Modal ───────────────────────────────────────────────────────────

function TemplateModal({ template, onClose, onSave }) {
  const editando = !!template?.id;
  const [nome, setNome] = useState(template?.nome || '');
  const [tipoOs, setTipoOs] = useState(template?.tipo_os || '');
  const [obrigatorio, setObrigatorio] = useState(template?.obrigatorio_ao_fechar ?? true);
  const [itens, setItens] = useState(
    (template?.itens || []).length > 0
      ? template.itens.map(i => ({ id: i.id, descricao: i.descricao, obrigatorio: i.obrigatorio ?? true }))
      : [{ id: 1, descricao: '', obrigatorio: true }]
  );
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const nextId = useRef(Math.max(...itens.map(i => i.id), 0) + 1);

  function addItem() {
    const id = nextId.current++;
    setItens(p => [...p, { id, descricao: '', obrigatorio: true }]);
  }

  function removeItem(id) {
    setItens(p => p.filter(i => i.id !== id));
  }

  function updateItem(id, field, value) {
    setItens(p => p.map(i => i.id === id ? { ...i, [field]: value } : i));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErr('');
    if (!nome.trim()) { setErr('Nome é obrigatório.'); return; }
    if (itens.some(i => !i.descricao.trim())) { setErr('Todos os itens precisam de descrição.'); return; }
    setLoading(true);
    try {
      const payload = {
        nome: nome.trim(),
        tipo_os: tipoOs || null,
        itens: itens.map(i => ({ id: i.id, descricao: i.descricao.trim(), obrigatorio: i.obrigatorio })),
        obrigatorio_ao_fechar: obrigatorio,
      };
      if (editando) {
        await updateChecklistTemplate(template.id, payload);
      } else {
        await createChecklistTemplate(payload);
      }
      onSave();
    } catch (e) {
      setErr(e.response?.data?.detail || 'Erro ao salvar template.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-700 shrink-0">
          <h2 className="text-white font-semibold">{editando ? 'Editar Template' : 'Novo Template de Checklist'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-5 space-y-4 overflow-y-auto flex-1">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Nome do Template *</label>
              <input className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                value={nome} onChange={e => setNome(e.target.value)} placeholder="Ex: Checklist NR-12 — Prensa" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Tipo de OS</label>
                <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  value={tipoOs} onChange={e => setTipoOs(e.target.value)}>
                  {TIPOS_OS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input type="checkbox" checked={obrigatorio} onChange={e => setObrigatorio(e.target.checked)}
                    className="accent-amber-500" />
                  Obrigatório ao fechar OS
                </label>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-400">Itens do Checklist *</label>
                <button type="button" onClick={addItem}
                  className="text-xs text-amber-400 hover:text-amber-300">+ Adicionar item</button>
              </div>
              <div className="space-y-2">
                {itens.map((item, idx) => (
                  <div key={item.id} className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
                    <span className="text-xs text-gray-500 w-5 shrink-0">{idx + 1}.</span>
                    <input
                      className="flex-1 bg-transparent text-white text-sm placeholder-gray-500 outline-none"
                      placeholder="Descrição do item..."
                      value={item.descricao}
                      onChange={e => updateItem(item.id, 'descricao', e.target.value)}
                    />
                    <label className="flex items-center gap-1 text-xs text-gray-400 cursor-pointer shrink-0">
                      <input type="checkbox" checked={item.obrigatorio}
                        onChange={e => updateItem(item.id, 'obrigatorio', e.target.checked)}
                        className="accent-amber-500" />
                      Obrig.
                    </label>
                    {itens.length > 1 && (
                      <button type="button" onClick={() => removeItem(item.id)}
                        className="text-gray-600 hover:text-red-400 text-lg leading-none shrink-0">×</button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {err && <p className="text-red-400 text-sm">{err}</p>}
          </div>

          <div className="flex gap-2 p-5 border-t border-gray-700 shrink-0">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 text-sm">
              Cancelar
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium disabled:opacity-50">
              {loading ? 'Salvando…' : 'Salvar Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function EvidenciasPage() {
  const { user } = useAuth();
  const isLider = R_LIDER.includes(user?.role);

  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editTemplate, setEditTemplate] = useState(null);
  const [err402, setErr402] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getChecklistTemplates({ tipo_os: filtroTipo || undefined });
      setTemplates(r.data);
    } catch (e) {
      if (e.response?.status === 402) setErr402(true);
    } finally {
      setLoading(false);
    }
  }, [filtroTipo]);

  useEffect(() => { carregar(); }, [carregar]);

  async function handleDesativar(id) {
    if (!window.confirm('Desativar este template? Os checklists já executados serão mantidos.')) return;
    try {
      await desativarChecklistTemplate(id);
      carregar();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erro ao desativar template.');
    }
  }

  if (err402) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="text-4xl">🔒</div>
        <p className="text-gray-400 text-center max-w-sm">
          Módulo de Evidências disponível a partir do plano{' '}
          <strong className="text-amber-400">Profissional</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Evidências & Compliance</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Templates de checklist, anexos de OS e assinatura digital de encerramento
          </p>
        </div>
        {isLider && (
          <button onClick={() => { setEditTemplate(null); setShowModal(true); }}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium">
            + Novo Template
          </button>
        )}
      </div>

      {/* Info sobre funcionalidades */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { emoji: '📎', title: 'Anexos de OS', desc: 'Fotos e PDFs anexados diretamente na OS, com validação de tipo e armazenamento seguro no S3.' },
          { emoji: '✅', title: 'Checklists Digitais', desc: 'Templates configuráveis por tipo de OS. Pode ser obrigatório antes de fechar a OS.' },
          { emoji: '🔏', title: 'Assinatura Digital', desc: 'Ao fechar uma OS, o sistema gera automaticamente um hash SHA-256 do estado imutável como assinatura.' },
        ].map(card => (
          <div key={card.title} className="bg-gray-900 border border-gray-700 rounded-xl p-4">
            <div className="text-2xl mb-2">{card.emoji}</div>
            <h3 className="text-white font-semibold text-sm mb-1">{card.title}</h3>
            <p className="text-gray-400 text-xs">{card.desc}</p>
          </div>
        ))}
      </div>

      {/* Filtros */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-400 font-medium">Templates de Checklist</span>
        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm"
          value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)}
        >
          {TIPOS_OS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      {/* Lista de templates */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : templates.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-gray-400 mb-4">Nenhum template de checklist cadastrado.</p>
          {isLider && (
            <button onClick={() => { setEditTemplate(null); setShowModal(true); }}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm">
              Criar primeiro template
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map(t => (
            <div key={t.id} className="bg-gray-900 border border-gray-700 rounded-xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-white font-semibold">{t.nome}</h3>
                    {t.tipo_os && (
                      <span className="px-2 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300 border border-blue-800">
                        {t.tipo_os}
                      </span>
                    )}
                    {t.obrigatorio_ao_fechar && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-900/30 text-red-400 border border-red-800">
                        Obrigatório ao fechar
                      </span>
                    )}
                  </div>

                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {(t.itens || []).map((item, idx) => (
                      <div key={item.id} className="flex items-center gap-2 text-sm">
                        <span className="w-5 h-5 rounded border border-gray-600 bg-gray-800 flex items-center justify-center text-xs text-gray-400 shrink-0">
                          {idx + 1}
                        </span>
                        <span className={`${item.obrigatorio ? 'text-gray-200' : 'text-gray-400'}`}>
                          {item.descricao}
                        </span>
                        {!item.obrigatorio && (
                          <span className="text-xs text-gray-600">(opcional)</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {isLider && (
                  <div className="flex flex-col gap-1 shrink-0">
                    <button onClick={() => { setEditTemplate(t); setShowModal(true); }}
                      className="text-xs text-blue-400 hover:text-blue-300 px-3 py-1 rounded hover:bg-gray-800">
                      Editar
                    </button>
                    <button onClick={() => handleDesativar(t.id)}
                      className="text-xs text-red-400 hover:text-red-300 px-3 py-1 rounded hover:bg-gray-800">
                      Desativar
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Nota sobre uso de anexos na OS */}
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-sm text-gray-400">
        <strong className="text-gray-300">Dica:</strong> Para adicionar fotos e PDFs a uma OS específica,
        abra o detalhe da OS na página de{' '}
        <a href="/ordens-servico" className="text-amber-400 hover:underline">Ordens de Serviço</a>{' '}
        e use a aba <em>Evidências</em>.
      </div>

      {showModal && (
        <TemplateModal
          template={editTemplate}
          onClose={() => { setShowModal(false); setEditTemplate(null); }}
          onSave={() => { setShowModal(false); setEditTemplate(null); carregar(); }}
        />
      )}
    </div>
  );
}
