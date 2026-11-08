import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { PlatzInhaltOut, PlatzOut } from '../types';
import { ART_NAMEN, GRUND_NAMEN, etikettenDrucken, ladePlaetze } from '../plaetze';
import { useBereiche, weg } from '../bereich/kontext';
import LoadError from '../components/LoadError';

/* Ein Platz und alles, was dort liegt, über alle Bereiche hinweg (ein Fach
   ist in echt gemischt). Umbenennen ändert das Etikett nicht; Umziehen nimmt
   den Inhalt mit, ohne eine einzige Buchung. */

// Wohin eine Art umziehen darf (dieselbe Regel wie der Server).
const ZIEL_ARTEN: Record<string, string[]> = {
  raum: [],
  regal: ['raum'],
  fach: ['regal'],
  kiste: ['raum', 'fach'],
};

export default function PlatzPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { bereiche } = useBereiche();
  const [daten, setDaten] = useState<PlatzInhaltOut | null>(null);
  const [alle, setAlle] = useState<PlatzOut[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [meldung, setMeldung] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [inhalt, setInhalt] = useState('');
  const [bereich, setBereich] = useState('');
  const [ziel, setZiel] = useState('');

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      const [d, a] = await Promise.all([api.get<PlatzInhaltOut>(`/plaetze/${id}`), ladePlaetze()]);
      setDaten(d);
      setAlle(a);
      setName(d.platz.name);
      setInhalt(d.platz.inhalt ?? '');
      setBereich(d.platz.bereich ?? '');
      setZiel(d.platz.eltern_id ? String(d.platz.eltern_id) : '');
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }, [id]);

  useEffect(() => {
    laden();
  }, [laden]);

  async function speichern(felder: Record<string, unknown>, text: string) {
    setMeldung(null);
    try {
      await api.put(`/plaetze/${id}`, felder);
      setMeldung(text);
      await laden();
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }

  async function loeschen() {
    if (!daten || !window.confirm(`${daten.platz.kennung} „${daten.platz.name}“ löschen? Die Kennung wird nie neu vergeben.`)) return;
    try {
      await api.del(`/plaetze/${id}`);
      navigate('/plaetze');
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }

  if (fehler && !daten) return <div className="page"><LoadError was="Der Platz" fehler={fehler} onRetry={laden} /></div>;
  if (!daten) return <div className="page loading">Platz wird geladen</div>;

  const p = daten.platz;
  const ziele = alle.filter((a) => ZIEL_ARTEN[p.art].includes(a.art));
  const kistenBereiche = bereiche.filter((b) => b.bauart === 'kiste');
  const bereichName = (s: string) => bereiche.find((b) => b.schluessel === s)?.name ?? s;
  const leer = daten.dinge.length === 0 && daten.unterplaetze.length === 0;

  return (
    <div className="page">
      <Link to="/plaetze" className="page-bereich">Plätze</Link>
      <h1 className="page-title">
        <span className="platz-kennung">{p.kennung}</span> {p.name}
      </h1>
      <p className="seiten-satz">{ART_NAMEN[p.art]}{p.pfad !== p.name ? ` · ${p.pfad}` : ''}</p>

      {fehler && <div className="error">{fehler}</div>}
      {meldung && <div className="toast success">{meldung}</div>}

      {daten.unterplaetze.length > 0 && (
        <div className="expiry-group">
          <div className="expiry-group-header">Darin</div>
          {daten.unterplaetze.map((u) => (
            <Link key={u.id} to={`/plaetze/${u.id}`} className="expiry-item">
              <div className="expiry-item-info">
                <span className="expiry-item-name">{u.kennung} · {u.name}</span>
                <span className="expiry-item-detail">{ART_NAMEN[u.art]}{u.inhalt ? ` · ${u.inhalt}` : ''}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="expiry-group">
        <div className="expiry-group-header">Liegt hier ({daten.dinge.length})</div>
        {daten.dinge.length === 0 && <div className="gruppe-leer">Nichts eingelagert. Über „Lagern“ kommt etwas hierher.</div>}
        {daten.dinge.map((d) => (
          <Link
            key={`${d.art}-${d.id}`}
            to={d.art === 'sache' ? weg(d.bereich) : weg(d.bereich, 'bestand')}
            className="expiry-item"
          >
            <div className="expiry-item-info">
              <span className="expiry-item-name">{d.name}</span>
              <span className="expiry-item-detail">
                {[bereichName(d.bereich), d.detail, d.shopfloor_grund ? `gerade: ${GRUND_NAMEN[d.shopfloor_grund]}` : '']
                  .filter(Boolean).join(' · ')}
              </span>
            </div>
          </Link>
        ))}
      </div>

      {p.art === 'kiste' && (
        <div className="card">
          <div className="inline-form-title">Inhalt der Kiste</div>
          <textarea
            className="form-input"
            rows={4}
            value={inhalt}
            placeholder="Was drin ist, z. B. Winterjacken, Schals, zwei Paar Stiefel"
            onChange={(e) => setInhalt(e.target.value)}
          />
          <div className="form-group" style={{ marginTop: 10 }}>
            <label className="form-label">Gehört zum Bereich</label>
            <select className="form-select" value={bereich} onChange={(e) => setBereich(e.target.value)}>
              <option value="">keinem</option>
              {kistenBereiche.map((b) => <option key={b.schluessel} value={b.schluessel}>{b.name}</option>)}
            </select>
          </div>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => speichern({ inhalt, bereich: bereich || null }, 'Inhalt gespeichert')}
          >
            Inhalt speichern
          </button>
        </div>
      )}

      <div className="card">
        <div className="inline-form-title">Umbenennen</div>
        <div className="platz-neu">
          <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} />
          <button
            className="btn btn-sm btn-secondary"
            disabled={!name.trim() || name.trim() === p.name}
            onClick={() => speichern({ name: name.trim() }, 'Umbenannt, das Etikett bleibt gültig')}
          >
            Speichern
          </button>
        </div>
      </div>

      {ZIEL_ARTEN[p.art].length > 0 && (
        <div className="card">
          <div className="inline-form-title">Umziehen</div>
          <div className="platz-neu">
            <select className="form-select" value={ziel} onChange={(e) => setZiel(e.target.value)}>
              {ziele.map((z) => <option key={z.id} value={z.id}>{z.pfad} · {z.kennung}</option>)}
            </select>
            <button
              className="btn btn-sm btn-secondary"
              disabled={!ziel || Number(ziel) === p.eltern_id}
              onClick={() => speichern({ eltern_id: Number(ziel) }, 'Umgezogen, der Inhalt ist mitgekommen')}
            >
              Umziehen
            </button>
          </div>
        </div>
      )}

      <div className="platz-knoepfe">
        <button className="btn btn-secondary" onClick={() => etikettenDrucken([p]).catch((e) => setFehler(fehlertext(e)))}>
          Etikett drucken
        </button>
        <button className="btn btn-danger" disabled={!leer} onClick={loeschen}
          title={leer ? '' : 'Nur ein leerer Platz lässt sich löschen'}>
          Löschen
        </button>
      </div>
    </div>
  );
}
