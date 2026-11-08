import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { PlatzOut } from '../types';
import { ART_NAMEN, KINDER_ARTEN, etikettenDrucken, ladePlaetze } from '../plaetze';
import LoadError from '../components/LoadError';
import Icon from '../components/Icon';

/* Eingang „Plätze" neben den Bereichen (Owner 2026-11-01): der Raumbaum,
   Etiketten und von hier aus jeder Platz mit allem, was dort liegt.
   Raum › Regal › Fach › Kiste; die Regel, wer in wem stehen darf, prüft der
   Server, hier werden nur die erlaubten Arten angeboten. */

function belegungText(p: PlatzOut): string {
  const teile: string[] = [];
  if (p.posten) teile.push(`${p.posten} Posten`);
  if (p.sachen) teile.push(p.sachen === 1 ? '1 Sache' : `${p.sachen} Sachen`);
  if (p.art === 'kiste' && p.inhalt) teile.push(p.inhalt);
  return teile.join(' · ');
}

function Neu({ eltern, onFertig }: { eltern: PlatzOut | null; onFertig: () => void }) {
  const arten = eltern ? KINDER_ARTEN[eltern.art] : ['raum'];
  const [art, setArt] = useState(arten[0]);
  const [name, setName] = useState('');
  const [fehler, setFehler] = useState<string | null>(null);

  async function anlegen(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post('/plaetze', { name: name.trim(), art, eltern_id: eltern?.id ?? null });
      setName('');
      onFertig();
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }

  if (!arten.length) return null;
  return (
    <form className="platz-neu" onSubmit={anlegen}>
      {arten.length > 1 ? (
        <select className="form-select" value={art} onChange={(e) => setArt(e.target.value)}>
          {arten.map((a) => <option key={a} value={a}>{ART_NAMEN[a]}</option>)}
        </select>
      ) : (
        <span className="platz-neu-art">{ART_NAMEN[art]}</span>
      )}
      <input
        className="form-input"
        placeholder={eltern ? `Name, z. B. ${art === 'fach' ? 'Fach 1' : art === 'kiste' ? 'Kiste Winter' : 'Regal links'}` : 'Name, z. B. Keller'}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button className="btn btn-sm btn-primary" type="submit" disabled={!name.trim()}>
        Anlegen
      </button>
      {fehler && <div className="error">{fehler}</div>}
    </form>
  );
}

export default function PlaetzePage() {
  const [plaetze, setPlaetze] = useState<PlatzOut[]>([]);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);
  const [gewaehlt, setGewaehlt] = useState<Set<number>>(new Set());
  const [offen, setOffen] = useState<number | null>(null);

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      setPlaetze(await ladePlaetze());
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  function umschalten(id: number) {
    const neu = new Set(gewaehlt);
    if (neu.has(id)) neu.delete(id);
    else neu.add(id);
    setGewaehlt(neu);
  }

  async function drucken() {
    try {
      const liste = plaetze.filter((p) => gewaehlt.size === 0 || gewaehlt.has(p.id));
      await etikettenDrucken(liste);
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }

  if (laedt) return <div className="page loading">Plätze werden geladen</div>;

  const kinder = new Map<number | null, PlatzOut[]>();
  for (const p of plaetze) {
    const k = p.eltern_id ?? null;
    kinder.set(k, [...(kinder.get(k) ?? []), p]);
  }

  // Eine Funktion, keine Komponente: als Komponente im Render definiert,
  // baute React den ganzen Baum bei jedem Haken neu auf.
  function zweig(p: PlatzOut, tiefe: number): JSX.Element {
    const unter = kinder.get(p.id) ?? [];
    return (
      <li key={p.id}>
        <div className="platz-zeile" style={{ paddingLeft: `${tiefe * 18}px` }}>
          {/* Das Label traegt die Tippflaeche: das Kaestchen selbst ist am
              Handy kleiner als ein Daumen. */}
          <label className="platz-haken">
            <input
              type="checkbox"
              aria-label={`${p.kennung} für Etiketten wählen`}
              checked={gewaehlt.has(p.id)}
              onChange={() => umschalten(p.id)}
            />
          </label>
          <Link to={`/plaetze/${p.id}`} className="platz-link">
            <span className="platz-kennung">{p.kennung}</span>
            <span className="platz-name">{p.name}</span>
            <span className="platz-art">{ART_NAMEN[p.art]}</span>
            <span className="platz-belegung">{belegungText(p)}</span>
          </Link>
          {KINDER_ARTEN[p.art].length > 0 && (
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              aria-label={`In ${p.name} anlegen`}
              onClick={() => setOffen(offen === p.id ? null : p.id)}
            >
              <Icon name="plus" className="knopf-icon" />
            </button>
          )}
        </div>
        {offen === p.id && (
          <div style={{ paddingLeft: `${(tiefe + 1) * 18}px` }}>
            <Neu eltern={p} onFertig={() => { setOffen(null); laden(); }} />
          </div>
        )}
        {unter.length > 0 && (
          <ul className="platz-baum">
            {unter.map((u) => zweig(u, tiefe + 1))}
          </ul>
        )}
      </li>
    );
  }

  const raeume = kinder.get(null) ?? [];

  return (
    <div className="page">
      <h1 className="page-title">Plätze</h1>
      <p className="seiten-satz">
        Raum › Regal › Fach, Kisten im Fach oder direkt im Raum. Jeder Platz hat ein Etikett mit
        fester Kennung; sie bleibt, auch wenn der Platz umbenannt wird.
      </p>

      {fehler && <LoadError was="Die Plätze" fehler={fehler} onRetry={laden} />}

      {raeume.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="kiste" /></div>
          <div className="empty-state-text">Noch keine Plätze. Zuerst einen Raum anlegen.</div>
        </div>
      ) : (
        <ul className="platz-baum platz-wurzel">
          {raeume.map((r) => zweig(r, 0))}
        </ul>
      )}

      <div className="card">
        <div className="inline-form-title">Neuer Raum</div>
        <Neu eltern={null} onFertig={laden} />
      </div>

      {plaetze.length > 0 && (
        <button type="button" className="btn btn-secondary btn-block" onClick={drucken}>
          {gewaehlt.size ? `${gewaehlt.size} Etiketten drucken` : `Alle ${plaetze.length} Etiketten drucken`}
        </button>
      )}

      <Link to="/shopfloor" className="bereich-nebenweg">
        <Icon name="lupe" className="knopf-icon" />
        Shopfloor: was eingebucht, aber nicht eingelagert ist
      </Link>
    </div>
  );
}
