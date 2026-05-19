import { useState, useEffect } from "react";
import { Label } from "../ui/label";
import { getGrupos, getSubgrupos } from "../../lib/api";

/**
 * Dropdown encadeado Grupo → Subgrupo para uso em formulários de OS.
 * Props:
 *   grupoId, subgrupoId — valores controlados
 *   onGrupoChange(id) — callback ao mudar grupo
 *   onSubgrupoChange(id) — callback ao mudar subgrupo
 *   disabled — boolean
 */
export default function SeletorGrupoSubgrupo({
  grupoId,
  subgrupoId,
  onGrupoChange,
  onSubgrupoChange,
  disabled = false,
}) {
  const [grupos, setGrupos] = useState([]);
  const [subgrupos, setSubgrupos] = useState([]);
  const [todosSubgrupos, setTodosSubgrupos] = useState([]);

  useEffect(() => {
    Promise.all([getGrupos(), getSubgrupos()])
      .then(([g, s]) => {
        setGrupos(g.data || []);
        setTodosSubgrupos(s.data || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (grupoId) {
      setSubgrupos(todosSubgrupos.filter(s => s.grupo_id === grupoId));
    } else {
      setSubgrupos([]);
    }
    onSubgrupoChange("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grupoId, todosSubgrupos]);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div className="space-y-1.5">
        <Label className="text-sm">Grupo</Label>
        <select
          className="w-full h-10 rounded-lg border border-border bg-background text-sm px-3 disabled:opacity-50"
          value={grupoId || ""}
          onChange={e => onGrupoChange(e.target.value)}
          disabled={disabled}
          data-testid="select-grupo"
        >
          <option value="">Selecione o grupo...</option>
          {grupos.map(g => (
            <option key={g.id} value={g.id}>{g.nome}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label className="text-sm">Subgrupo</Label>
        <select
          className="w-full h-10 rounded-lg border border-border bg-background text-sm px-3 disabled:opacity-50"
          value={subgrupoId || ""}
          onChange={e => onSubgrupoChange(e.target.value)}
          disabled={disabled || !grupoId}
          data-testid="select-subgrupo"
        >
          <option value="">Selecione o subgrupo...</option>
          {subgrupos.map(s => (
            <option key={s.id} value={s.id}>{s.nome}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
