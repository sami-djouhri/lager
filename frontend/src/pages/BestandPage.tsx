import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { StockEntryOut, Page, AusbuchenSammelRequest } from '../types';
import StockCard from '../components/StockCard';
import LoadError from '../components/LoadError';
import Icon from '../components/Icon';
import { fristName, useBereich, weg } from '../bereich/kontext';
import Kopf from '../bereich/Kopf';

type Grund = AusbuchenSammelRequest['reason'];

const GRUENDE: { value: NonNullable<Grund>; label: string }[] = [
  { value: 'abgelaufen', label: 'Abgelaufen' },
  { value: 'weggeworfen', label: 'Weggeworfen' },
  { value: 'verbraucht', label: 'Verbraucht' },
];

/** Wie das Backend: abgelaufen ist, was VOR heute ablief. Heute ist noch gut. */
const istAbgelaufen = (e: StockEntryOut) => e.days_until_expiry != null && e.days_until_expiry < 0;

export default function BestandPage() {
  const { schluessel, bereich } = useBereich();
  const [params, setParams] = useSearchParams();
  const [entries, setEntries] = useState<StockEntryOut[]>([]);
  const [search, setSearch] = useState('');
  const [location, setLocation] = useState('Alle');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // null = kein Auswahlmodus. Die Auswahl haelt Posten-Kennungen, nicht
  // Produkte: drei abgelaufene Joghurts sind genau diese drei Posten.
  const [auswahl, setAuswahl] = useState<Set<number> | null>(null);
  const [grund, setGrund] = useState<NonNullable<Grund>>('abgelaufen');
  const [bucht, setBucht] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);
  const navigate = useNavigate();

  const melden = (msg: string, type: string) => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ only_positive: 'true', limit: '500', bereich: schluessel });
      const data = await api.get<Page<StockEntryOut>>(`/stock?${params}`);
      setEntries(data.items);
      return data.items;
    } catch (err) {
      setError(fehlertext(err));
      return [];
    } finally {
      setLoading(false);
    }
  }, [schluessel]);

  // `?auswahl=abgelaufen` (Einstieg von der Uebersicht) oeffnet den
  // Auswahlmodus mit allen abgelaufenen Posten vorgewaehlt. Der Parameter
  // wird danach entfernt, sonst waehlte jedes Neuladen sie wieder.
  const vorwahl = params.get('auswahl');
  useEffect(() => {
    load().then((items) => {
      if (vorwahl === 'abgelaufen') {
        setAuswahl(new Set(items.filter(istAbgelaufen).map((e) => e.id)));
        setGrund('abgelaufen');
        setParams({}, { replace: true });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  // Die Chips kommen aus den Plaetzen, an denen in diesem Bereich etwas
  // liegt, nicht aus einer Vorschlagsliste: sonst gaebe es Chips ohne Treffer.
  const ortName = (e: StockEntryOut) => e.platz_pfad || e.location;
  const orte = ['Alle', ...Array.from(new Set(entries.map(ortName))).sort((a, b) => a.localeCompare(b))];
  const filtered = entries
    .filter((e) => location === 'Alle' || ortName(e) === location)
    .filter((e) => !search || (e.product_name ?? '').toLowerCase().includes(search.toLowerCase()));
  const abgelaufenSichtbar = filtered.filter(istAbgelaufen);

  function handleConsume(entry: StockEntryOut) {
    navigate(`${weg(schluessel, 'ausbuchen')}?product_id=${entry.product_id}`);
  }

  function umschalten(entry: StockEntryOut) {
    setAuswahl((alt) => {
      const neu = new Set(alt ?? []);
      if (neu.has(entry.id)) neu.delete(entry.id);
      else neu.add(entry.id);
      return neu;
    });
  }

  /** Waehlt die sichtbaren Posten (nach Suche und Ort) dazu. */
  function dazuWaehlen(liste: StockEntryOut[]) {
    setAuswahl((alt) => new Set([...(alt ?? []), ...liste.map((e) => e.id)]));
  }

  async function ausbuchen() {
    if (!auswahl || auswahl.size === 0) return;
    setBucht(true);
    try {
      const body: AusbuchenSammelRequest = { entry_ids: [...auswahl], reason: grund, source: 'manual' };
      await api.post('/stock/ausbuchen', body);
      const n = auswahl.size;
      const wort = GRUENDE.find((g) => g.value === grund)?.label.toLowerCase() ?? grund;
      melden(`${n} Posten als ${wort} ausgebucht`, 'success');
      setAuswahl(null);
      await load();
    } catch (err) {
      // Alles oder nichts: bei einer veralteten Auswahl ist nichts gebucht.
      // Neu laden und nur behalten, was noch da ist.
      melden(fehlertext(err), 'error');
      const items = await load();
      const da = new Set(items.map((e) => e.id));
      setAuswahl((alt) => new Set([...(alt ?? [])].filter((id) => da.has(id))));
    } finally {
      setBucht(false);
    }
  }

  const imModus = auswahl !== null;

  return (
    <div className={`page${imModus ? ' page-mit-leiste' : ''}`}>
      <Kopf titel="Bestand" />

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

      <div className="form-group">
        <input
          type="text"
          className="form-input"
          placeholder="Suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="filter-chips">
        {orte.map((loc) => (
          <button
            key={loc}
            className={`chip${location === loc ? ' active' : ''}`}
            onClick={() => setLocation(loc)}
          >
            {loc}
          </button>
        ))}
      </div>

      {!loading && !error && entries.length > 0 && (
        <div className="auswahl-kopf">
          {imModus ? (
            <>
              <button className="btn btn-sm btn-secondary" onClick={() => dazuWaehlen(filtered)}>
                Alle sichtbaren
              </button>
              {abgelaufenSichtbar.length > 0 && (
                <button className="btn btn-sm btn-secondary" onClick={() => dazuWaehlen(abgelaufenSichtbar)}>
                  Abgelaufene ({abgelaufenSichtbar.length})
                </button>
              )}
              <button className="btn btn-sm btn-secondary" onClick={() => setAuswahl(new Set())} disabled={auswahl.size === 0}>
                Keine
              </button>
              <button className="btn btn-sm btn-secondary auswahl-ende" onClick={() => setAuswahl(null)}>
                Abbrechen
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-sm btn-secondary" onClick={() => setAuswahl(new Set())}>
                Mehrere auswählen
              </button>
              {abgelaufenSichtbar.length > 0 && (
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => {
                    setGrund('abgelaufen');
                    setAuswahl(new Set(abgelaufenSichtbar.map((e) => e.id)));
                  }}
                >
                  Abgelaufene auswählen ({abgelaufenSichtbar.length})
                </button>
              )}
            </>
          )}
        </div>
      )}

      {loading ? (
        <div className="loading">Laden...</div>
      ) : error ? (
        <LoadError was="Der Bestand" fehler={error} onRetry={load} />
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="kiste" /></div>
          <div className="empty-state-text">Kein Eintrag passt zu den Filtern.</div>
        </div>
      ) : (
        filtered.map((e) => (
          <StockCard
            key={e.id}
            entry={e}
            onConsume={handleConsume}
            frist={fristName(bereich)}
            gewaehlt={auswahl?.has(e.id)}
            onWaehlen={imModus ? umschalten : undefined}
          />
        ))
      )}

      {imModus && (
        <div className="auswahl-leiste" role="region" aria-label="Auswahl ausbuchen">
          <div className="auswahl-leiste-zeile">
            <span className="auswahl-zahl">
              {auswahl.size === 0 ? 'Nichts gewählt' : `${auswahl.size} Posten gewählt`}
            </span>
            <div className="reason-selector">
              {GRUENDE.map((g) => (
                <button
                  key={g.value}
                  type="button"
                  className={`reason-btn${grund === g.value ? ' active' : ''}`}
                  onClick={() => setGrund(g.value)}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>
          <button
            className={`btn btn-block ${grund === 'verbraucht' ? 'btn-primary' : 'btn-danger'}`}
            disabled={auswahl.size === 0 || bucht}
            onClick={ausbuchen}
          >
            {bucht ? 'Bucht aus…' : `Ganz ausbuchen${auswahl.size > 0 ? ` (${auswahl.size})` : ''}`}
          </button>
        </div>
      )}
    </div>
  );
}
