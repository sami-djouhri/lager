import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ladePlaetze } from '../plaetze';
import type { PlatzOut } from '../types';

/* Platz auswaehlen, mit „noch nicht einlagern" an erster Stelle: eingebucht
   ist wichtiger als eingelagert (Owner 2026-11-01). Leer = Shopfloor. */

interface Props {
  wert: number | null;
  onWahl: (platzId: number | null) => void;
  label?: string;
}

export default function PlatzWahl({ wert, onWahl, label = 'Lagerplatz' }: Props) {
  const [plaetze, setPlaetze] = useState<PlatzOut[] | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    ladePlaetze().then(setPlaetze).catch((e) => setFehler(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      <select
        className="form-select"
        value={wert ?? ''}
        onChange={(e) => onWahl(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Noch nicht einlagern (Shopfloor)</option>
        {(plaetze ?? []).map((p) => (
          <option key={p.id} value={p.id}>
            {p.pfad} · {p.kennung}
          </option>
        ))}
      </select>
      {fehler && <div className="error">Plätze nicht geladen: {fehler}</div>}
      {plaetze && plaetze.length === 0 && (
        <div className="form-hinweis">
          Noch keine Plätze. Unter <Link to="/plaetze">Plätze</Link> Räume, Regale und Kisten
          anlegen.
        </div>
      )}
    </div>
  );
}
