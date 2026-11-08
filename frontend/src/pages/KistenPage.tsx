import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { PlatzOut } from '../types';
import { useBereich } from '../bereich/kontext';
import { etikettenDrucken, ladePlaetze } from '../plaetze';
import Kopf from '../bereich/Kopf';
import LoadError from '../components/LoadError';
import Icon from '../components/Icon';

/* Bereiche der Bauart „kiste" (Kleidung, Saison): nur Kisten mit
   Inhaltsangabe, keine Einzelstücke (Owner 2026-11-01). Eine Kiste ist ein
   Platz; sie steht in einem Fach oder direkt im Raum, nie in einer Kiste. */

export default function KistenPage() {
  const { schluessel, bereich } = useBereich();
  const [alle, setAlle] = useState<PlatzOut[]>([]);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [eltern, setEltern] = useState('');
  const [inhalt, setInhalt] = useState('');

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      setAlle(await ladePlaetze());
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  const kisten = alle.filter((p) => p.art === 'kiste' && p.bereich === schluessel);
  const stellflaechen = alle.filter((p) => p.art === 'raum' || p.art === 'fach');

  async function anlegen(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post('/plaetze', {
        name: name.trim(), art: 'kiste', eltern_id: Number(eltern),
        inhalt: inhalt.trim() || null, bereich: schluessel,
      });
      setName('');
      setInhalt('');
      await laden();
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }

  if (laedt) return <div className="page loading">Kisten werden geladen</div>;

  return (
    <div className="page">
      <Kopf titel="Kisten" />
      {fehler && <LoadError was="Die Kisten" fehler={fehler} onRetry={laden} />}

      {kisten.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="kiste" /></div>
          <div className="empty-state-text">Noch keine Kiste in {bereich?.name ?? 'diesem Bereich'}.</div>
        </div>
      ) : (
        <div className="expiry-group">
          {kisten.map((k) => (
            <Link key={k.id} to={`/plaetze/${k.id}`} className="expiry-item">
              <div className="expiry-item-info">
                <span className="expiry-item-name">{k.kennung} · {k.name}</span>
                <span className="expiry-item-detail">
                  {k.pfad.split(' › ').slice(0, -1).join(' › ')}
                  {' · '}
                  {k.inhalt ? k.inhalt : <em>noch keine Inhaltsangabe</em>}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <form className="card" onSubmit={anlegen}>
        <div className="inline-form-title">Neue Kiste</div>
        {stellflaechen.length === 0 ? (
          <div className="form-hinweis">
            Eine Kiste steht in einem Raum oder Fach. Zuerst unter <Link to="/plaetze">Plätze</Link> einen
            Raum anlegen.
          </div>
        ) : (
          <>
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="form-input" value={name} placeholder="z. B. Winterjacken"
                onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Steht in</label>
              <select className="form-select" value={eltern} onChange={(e) => setEltern(e.target.value)}>
                <option value="">bitte wählen</option>
                {stellflaechen.map((p) => <option key={p.id} value={p.id}>{p.pfad} · {p.kennung}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Inhalt</label>
              <textarea className="form-input" rows={3} value={inhalt}
                placeholder="Was drin ist" onChange={(e) => setInhalt(e.target.value)} />
            </div>
            <button className="btn btn-primary btn-block" type="submit" disabled={!name.trim() || !eltern}>
              Kiste anlegen
            </button>
          </>
        )}
      </form>

      {kisten.length > 0 && (
        <button type="button" className="btn btn-secondary btn-block"
          onClick={() => etikettenDrucken(kisten).catch((e) => setFehler(fehlertext(e)))}>
          Etiketten für {kisten.length === 1 ? 'die Kiste' : `alle ${kisten.length} Kisten`} drucken
        </button>
      )}
    </div>
  );
}
