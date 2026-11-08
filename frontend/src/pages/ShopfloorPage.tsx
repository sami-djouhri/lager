import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { ShopfloorOut } from '../types';
import { useBereiche, weg } from '../bereich/kontext';
import LoadError from '../components/LoadError';

/* Der Shopfloor: eingebucht, aber nicht an seinem Platz (Vorbild medien).
   Oben steht „noch nicht eingelagert", denn das ist die Arbeit, die ansteht;
   darunter die festen Gründe. Ein Zugang bekommt nie von selbst einen Grund. */

export default function ShopfloorPage() {
  const { bereiche } = useBereiche();
  const [daten, setDaten] = useState<ShopfloorOut | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      setDaten(await api.get<ShopfloorOut>('/shopfloor'));
    } catch (err) {
      setFehler(fehlertext(err));
    }
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  const bereichName = (s: string) => bereiche.find((b) => b.schluessel === s)?.name ?? s;

  return (
    <div className="page">
      <Link to="/plaetze" className="page-bereich">Plätze</Link>
      <h1 className="page-title">Shopfloor</h1>
      <p className="seiten-satz">
        Was eingebucht ist, zählt als vorhanden, auch ohne Platz. Einlagern hilft beim
        Wiederfinden: am Posten oder an der Sache einen Platz wählen.
      </p>

      {fehler && <LoadError was="Der Shopfloor" fehler={fehler} onRetry={laden} />}
      {!daten && !fehler && <div className="loading">Laden...</div>}

      {daten && daten.anzahl === 0 && (
        <div className="empty-state">
          <div className="empty-state-text">Alles ist an seinem Platz.</div>
        </div>
      )}

      {daten && daten.anzahl > 0 && (
        <div className="expiry-section">
          {daten.gruppen.filter((g) => g.dinge.length > 0).map((g) => (
            <div key={g.grund ?? 'ohne'} className="expiry-group">
              <div className="expiry-group-header">{g.name} ({g.dinge.length})</div>
              {g.dinge.map((d) => (
                <Link
                  key={`${d.art}-${d.id}`}
                  to={d.art === 'sache' ? weg(d.bereich) : weg(d.bereich, 'bestand')}
                  className="expiry-item"
                >
                  <div className="expiry-item-info">
                    <span className="expiry-item-name">{d.name}</span>
                    <span className="expiry-item-detail">
                      {[bereichName(d.bereich), d.detail, d.platz_pfad ? `gehört nach ${d.platz_pfad}` : '']
                        .filter(Boolean).join(' · ')}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
