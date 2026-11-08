import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { ElectronicAssetOut, MarketValueUpdateOut, Page, PortfolioOut } from '../types';
import Icon from '../components/Icon';
import PlatzWahl from '../components/PlatzWahl';
import { GRUND_NAMEN, sachEtikettenDrucken } from '../plaetze';
import { fotoAuswaehlen, fotoSenden, fotoUrl } from '../fotos';
import { useBereich, weg } from '../bereich/kontext';

// Bereich „Technik & Sachen" (vorher „Wertsachen"): Einzelstücke mit Wert,
// Kategorien, Verkaufsempfehlungen, Marktwert über marktwatch. Hat die Saganta-
// Assets-App abgelöst (RICHTUNG.md, Stufe 2). Platz und Verbleib seit Stufe 3;
// Vermisst und Abgang (Verkauft, Weg) seit Stufe 7a, Verliehen folgt mit 7b.
// Seit Stufe 4: Kennung S-0001 je Stück, Foto, Etiketten für Stücke ohne Strichcode.

function fmtEur(v: number | null | undefined): string {
  return v == null ? '–' : `${Math.round(v).toLocaleString('de-DE')} €`;
}

function fmtDelta(v: number): string {
  return `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('de-DE')} €`;
}

/** Wo die Sache gerade ist, in einem Wort. */
function verbleibText(a: ElectronicAssetOut): string {
  if (a.verbleib === 'eingelagert') return 'eingelagert';
  if (a.verbleib === 'vermisst') return 'vermisst';
  return a.shopfloor_grund ? GRUND_NAMEN[a.shopfloor_grund] ?? a.shopfloor_grund : 'nicht eingelagert';
}

// Zustand im Formular: eingelagert, vermisst, einer der Gründe oder „nicht eingelagert".
type Zustand = 'eingelagert' | 'vermisst' | 'ohne' | keyof typeof GRUND_NAMEN;

function zustandVon(a: ElectronicAssetOut): Zustand {
  if (a.verbleib === 'eingelagert') return 'eingelagert';
  if (a.verbleib === 'vermisst') return 'vermisst';
  return (a.shopfloor_grund as Zustand) ?? 'ohne';
}

function PlatzForm({ a, gruende, onFertig }: {
  a: ElectronicAssetOut;
  /** Die Shopfloor-Gruende des Bereichs (Owner: je Bereich). */
  gruende: { schluessel: string; name: string }[];
  onFertig: (fehler?: string) => void;
}) {
  const [platzId, setPlatzId] = useState<number | null>(a.platz_id ?? null);
  const [zustand, setZustand] = useState<Zustand>(zustandVon(a));

  async function speichern() {
    const body: Record<string, unknown> = { platz_id: platzId };
    if (zustand === 'eingelagert' || zustand === 'vermisst') body.verbleib = zustand;
    else body.shopfloor_grund = zustand === 'ohne' ? null : zustand;
    try {
      await api.put(`/electronics/${a.id}`, body);
      onFertig();
    } catch (err) {
      onFertig(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="inline-form">
      <PlatzWahl wert={platzId} onWahl={setPlatzId} label="Gehört an den Platz" />
      <div className="form-group">
        <label className="form-label">Gerade</label>
        <select className="form-select" value={zustand} onChange={(e) => setZustand(e.target.value as Zustand)}>
          <option value="eingelagert" disabled={platzId == null}>an seinem Platz</option>
          {gruende.map((g) => <option key={g.schluessel} value={g.schluessel}>{g.name}</option>)}
          <option value="ohne">noch nicht eingelagert</option>
          <option value="vermisst">vermisst</option>
        </select>
      </div>
      <div className="inline-form-actions">
        <button className="btn btn-sm btn-primary" onClick={speichern}
          disabled={zustand === 'eingelagert' && platzId == null}>Speichern</button>
        <button className="btn btn-sm btn-secondary" onClick={() => onFertig()}>Abbrechen</button>
      </div>
    </div>
  );
}

function heute(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function fmtDatum(iso: string | null | undefined): string {
  if (!iso) return '';
  const [j, m, t] = iso.split('-');
  return `${t}.${m}.${j}`;
}

/** Verkauft oder Weg (Stufe 7a). Die Sache bleibt erhalten und steht danach unter „Abgegangen". */
function AbgangForm({ a, onFertig }: { a: ElectronicAssetOut; onFertig: (fehler?: string) => void }) {
  // Lange Vermisstes kommt mit „Weg" vorbelegt: das ist die Frage, die der Vorschlag stellt.
  const [abgang, setAbgang] = useState<'verkauft' | 'weg'>(a.ausbuchen_vorschlagen ? 'weg' : 'verkauft');
  const [am, setAm] = useState(heute());
  const [erloes, setErloes] = useState('');
  const [plattform, setPlattform] = useState('');
  const [laeuft, setLaeuft] = useState(false);

  async function buchen() {
    if (laeuft) return;
    setLaeuft(true);
    const body: Record<string, unknown> = { abgang, am };
    if (abgang === 'verkauft') {
      const betrag = erloes.trim() ? Number(erloes.replace(',', '.')) : null;
      if (betrag != null && (Number.isNaN(betrag) || betrag < 0)) {
        setLaeuft(false);
        onFertig('Der Erlös ist keine Zahl.');
        return;
      }
      body.erloes = betrag;
      body.plattform = plattform.trim() || null;
    }
    try {
      await api.post(`/electronics/${a.id}/abgang`, body);
      onFertig();
    } catch (err) {
      setLaeuft(false);
      onFertig(fehlertext(err));
    }
  }

  return (
    <div className="inline-form">
      <div className="inline-form-title">{a.kennung} {a.name} geht ab</div>
      <div className="form-group">
        <label className="form-label">Wie</label>
        <select className="form-select" value={abgang} onChange={(e) => setAbgang(e.target.value as 'verkauft' | 'weg')}>
          <option value="verkauft">Verkauft</option>
          <option value="weg">Weg (verschenkt, entsorgt, verloren)</option>
        </select>
      </div>
      <div className="form-group">
        <label className="form-label">Am</label>
        <input className="form-input" type="date" value={am} max={heute()} onChange={(e) => setAm(e.target.value)} />
      </div>
      {abgang === 'verkauft' && (
        <>
          <div className="form-group">
            <label className="form-label">Erlös in € (freiwillig)</label>
            <input className="form-input" inputMode="decimal" value={erloes} onChange={(e) => setErloes(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Wo verkauft (freiwillig)</label>
            <input className="form-input" maxLength={60} value={plattform} placeholder="z. B. Kleinanzeigen"
              onChange={(e) => setPlattform(e.target.value)} />
          </div>
        </>
      )}
      <div className="inline-form-actions">
        <button className="btn btn-sm btn-primary" onClick={buchen} disabled={laeuft || !am}>
          {laeuft ? '…' : abgang === 'verkauft' ? 'Als verkauft buchen' : 'Als weg buchen'}
        </button>
        <button className="btn btn-sm btn-secondary" onClick={() => onFertig()}>Abbrechen</button>
      </div>
    </div>
  );
}

export default function WertsachenPage() {
  const [assets, setAssets] = useState<ElectronicAssetOut[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<number | null>(null);
  const [bearbeitet, setBearbeitet] = useState<number | null>(null);
  const [gehtAb, setGehtAb] = useState<number | null>(null);
  const [abgaenge, setAbgaenge] = useState<ElectronicAssetOut[]>([]);
  const [nimmtZurueck, setNimmtZurueck] = useState<number | null>(null);
  const [fotoLaeuft, setFotoLaeuft] = useState<number | null>(null);
  const { schluessel, bereich } = useBereich();
  // Dieselbe Seite traegt Filme & Medien (Bauart `exemplar`): ohne Marktwert
  // und Verkaufsvorschlag (der Verkauf bleibt in medien), gruppiert nach Medium.
  const exemplar = bereich?.bauart === 'exemplar';

  const load = useCallback(async () => {
    setError(null);
    try {
      const b = encodeURIComponent(schluessel);
      const [page, pf, weg_] = await Promise.all([
        api.get<Page<ElectronicAssetOut>>(`/electronics?limit=500&bereich=${b}`),
        exemplar ? Promise.resolve(null) : api.get<PortfolioOut>('/electronics/portfolio'),
        api.get<Page<ElectronicAssetOut>>(`/electronics?limit=500&bereich=${b}&abgegangen=true`),
      ]);
      setAssets(page.items);
      setPortfolio(pf);
      // Neueste zuerst: gesucht wird meist, was gerade weggegangen ist.
      setAbgaenge([...weg_.items].sort((x, y) => (y.abgang_am ?? '').localeCompare(x.abgang_am ?? '')));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [schluessel, exemplar]);

  useEffect(() => {
    load();
  }, [load]);

  // Verweise aus medien zeigen auf `/b/medien#S-0001`. Der Browser sucht den
  // Anker, bevor die Liste geladen ist; deshalb hier, sobald sie steht.
  useEffect(() => {
    const ziel = decodeURIComponent(window.location.hash.slice(1));
    if (loading || !ziel) return;
    document.getElementById(ziel)?.scrollIntoView({ block: 'center', behavior: 'instant' });
  }, [loading]);

  async function refreshMarket(id: number) {
    setRefreshing(id);
    try {
      await api.post<MarketValueUpdateOut>(`/electronics/${id}/refresh-market-value?force=true`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(null);
    }
  }

  async function zuruecknehmen(id: number) {
    setNimmtZurueck(id);
    try {
      await api.del(`/electronics/${id}/abgang`);
      await load();
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setNimmtZurueck(null);
    }
  }

  async function foto(id: number) {
    setFotoLaeuft(id);
    try {
      const neu = await fotoSenden(id, await fotoAuswaehlen());
      setAssets((alle) => alle.map((a) => (a.id === neu.id ? neu : a)));
    } catch (err) {
      const text = fehlertext(err);
      if (text !== 'Kein Bild gewählt') setError(text);
    } finally {
      setFotoLaeuft(null);
    }
  }

  // Etiketten nur fuer Stuecke ohne Strichcode (Owner 2026-11-01, wie medien).
  const ohneStrichcode = assets.filter((a) => !a.barcode);

  if (loading) return <div className="page loading">Laden...</div>;

  const grouped = new Map<string, ElectronicAssetOut[]>();
  for (const a of assets) {
    const k = exemplar ? a.medium || 'Ohne Medium' : a.category || 'Ohne Kategorie';
    const bucket = grouped.get(k) ?? [];
    bucket.push(a);
    grouped.set(k, bucket);
  }
  for (const list of grouped.values()) {
    list.sort(
      (a, b) => (b.effective_market_value ?? -Infinity) - (a.effective_market_value ?? -Infinity),
    );
  }
  const categories = Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <div className="page">
      <h1 className="page-title">{bereich?.name ?? 'Technik & Sachen'}</h1>

      {error && <div className="error">{error}</div>}

      <div className="lauf-knoepfe">
        <Link to={weg(schluessel, 'lauf')} className="btn btn-primary">Einbuchen mit Scanner</Link>
        {ohneStrichcode.length > 0 && (
          <button type="button" className="btn btn-secondary"
            onClick={() => sachEtikettenDrucken(ohneStrichcode).catch((e) => setError(fehlertext(e)))}>
            {ohneStrichcode.length} {ohneStrichcode.length === 1 ? 'Etikett' : 'Etiketten'} drucken
          </button>
        )}
      </div>

      {portfolio && portfolio.total_assets > 0 && (
        <div className="summary-tiles">
          <div className="summary-tile">
            <div className="tile-value">{fmtEur(portfolio.market_value_total)}</div>
            <div className="tile-label">Marktwert</div>
            {portfolio.valued_count < portfolio.total_assets && (
              <div className="tile-fuss">{portfolio.valued_count} von {portfolio.total_assets} bewertet</div>
            )}
          </div>
          <div className="summary-tile">
            <div className="tile-value">{fmtEur(portfolio.purchase_total)}</div>
            <div className="tile-label">Einkaufswert</div>
          </div>
          <div className="summary-tile">
            <div
              className="tile-value"
              style={{
                // Ohne Vergleichswert kein Gruen: ein farbiger Strich las sich wie ein Gewinn.
                color:
                  portfolio.delta_count === 0
                    ? 'var(--tinte-still)'
                    : portfolio.delta_vs_purchase >= 0
                      ? 'var(--color-success, #4caf50)'
                      : 'var(--color-danger)',
              }}
            >
              {portfolio.delta_count > 0 ? fmtDelta(portfolio.delta_vs_purchase) : '–'}
            </div>
            <div className="tile-label">Gegen Einkauf</div>
          </div>
        </div>
      )}

      {portfolio && portfolio.resale_recommendations.length > 0 && (
        <div className="low-stock-section">
          <div className="expiry-group-header">
            <span className="expiry-dot" style={{ background: 'var(--color-warning)' }} />
            Verkaufen lohnt sich ({portfolio.resale_recommendations.length})
          </div>
          {portfolio.resale_recommendations.map((r) => (
            <div
              key={r.asset_id}
              className="low-stock-item"
              style={{ borderLeft: '4px solid var(--color-warning)' }}
            >
              <div className="low-stock-item-info">
                <span className="low-stock-item-name">{r.name}</span>
                <span className="low-stock-item-detail">{r.reason}</span>
              </div>
              <span style={{ flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
                {fmtEur(r.market_value_eur)}
              </span>
            </div>
          ))}
        </div>
      )}

      {assets.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="geraet" /></div>
          <div className="empty-state-text">
            Noch keine Stücke erfasst. <Link to={weg(schluessel, 'lauf')}>Einbuchen</Link> mit
            Scanner oder nach Namen.
          </div>
        </div>
      )}

      {categories.map(([cat, list]) => (
        <div key={cat} className="expiry-section">
          <div className="expiry-group">
            <div className="expiry-group-header">{cat} ({list.length})</div>
            {list.map((a) => (
              <div key={a.id} id={a.kennung} className="sache-anker">
              <div className="expiry-item sache-zeile">
                {fotoUrl(a) && <img className="sache-bild" src={fotoUrl(a)!} alt="" loading="lazy" />}
                <div className="sache-info">
                  <div className="sache-kopf">
                    <span className="platz-kennung">{a.kennung}</span>
                    <span className="sache-name">
                      {exemplar && bereich?.titel_verweis && a.titel_id != null
                        ? <a href={bereich.titel_verweis.replace('{titel_id}', String(a.titel_id))}
                            title="Titel in medien öffnen">{a.name}</a>
                        : a.name}
                    </span>
                    {!exemplar && <span className="sache-wert">{fmtEur(a.effective_market_value)}</span>}
                  </div>
                  {/* Jedes Teil bricht als Ganzes um, nie „10" / „€" auf zwei Zeilen. */}
                  <div className="sache-detail">
                    <span className={a.in_active_use ? 'sache-verbleib einsatz'
                      : a.verbleib === 'vermisst' ? 'sache-verbleib vermisst' : 'sache-verbleib'}>
                      {verbleibText(a)}
                    </span>
                    {a.verbleib === 'vermisst' && a.vermisst_seit && (
                      <span className="sache-teil">seit {fmtDatum(a.vermisst_seit.slice(0, 10))}</span>
                    )}
                    {(exemplar
                      ? [a.titel_id == null ? 'Titel aus medien folgt' : null, a.teil, a.edition, a.condition]
                      : [[a.brand, a.model].filter(Boolean).join(' ')]
                    ).concat([
                      a.platz_pfad,
                      a.sell_decision !== 'behalten' ? a.sell_decision : null,
                      a.purchase_price != null ? `gekauft für ${fmtEur(a.purchase_price)}` : null,
                    ]).filter(Boolean).map((t) => <span key={t as string} className="sache-teil">{t}</span>)}
                  </div>
                  {a.ausbuchen_vorschlagen && (
                    // Nur ein Vorschlag: gebucht wird erst mit dem Knopf im Formular.
                    <div className="sache-vorschlag">
                      Seit über 30 Tagen vermisst.{' '}
                      {exemplar ? 'In medien als weg buchen, das Lager übernimmt es.' : (
                        <button type="button" className="sache-griff" onClick={() => {
                          setBearbeitet(null);
                          setGehtAb(a.id);
                        }}>Als weg buchen?</button>
                      )}
                    </div>
                  )}
                  <div className="sache-aktionen">
                    <button type="button" className="sache-griff" onClick={() => {
                      setGehtAb(null);
                      setBearbeitet(bearbeitet === a.id ? null : a.id);
                    }}
                      aria-expanded={bearbeitet === a.id}>
                      <Icon name="kiste" className="knopf-icon" /> Platz &amp; Verbleib
                    </button>
                    <button type="button" className="sache-griff" onClick={() => foto(a.id)} disabled={fotoLaeuft === a.id}>
                      <Icon name="kamera" className="knopf-icon" /> {fotoLaeuft === a.id ? '…' : a.foto ? 'Neues Foto' : 'Foto'}
                    </button>
                    {!exemplar && (
                      <button type="button" className="sache-griff" onClick={() => refreshMarket(a.id)} disabled={refreshing === a.id}>
                        <Icon name="erneuern" className="knopf-icon" /> {refreshing === a.id ? '…' : 'Marktwert abrufen'}
                      </button>
                    )}
                    {/* Filme gehen in medien ab (Owner: der Verkauf bleibt dort), das Lager holt es ab. */}
                    {!exemplar && (
                      <button type="button" className="sache-griff" onClick={() => {
                        setBearbeitet(null);
                        setGehtAb(gehtAb === a.id ? null : a.id);
                      }} aria-expanded={gehtAb === a.id}>
                        <Icon name="minus" className="knopf-icon" /> Abgang
                      </button>
                    )}
                  </div>
                </div>
              </div>
              {bearbeitet === a.id && (
                <PlatzForm
                  key={`platz-${a.id}`}
                  a={a}
                  gruende={bereich?.gruende ?? Object.entries(GRUND_NAMEN).map(([k, v]) => ({ schluessel: k, name: v }))}
                  onFertig={(f) => {
                    setBearbeitet(null);
                    if (f) setError(f);
                    else load();
                  }}
                />
              )}
              {gehtAb === a.id && (
                <AbgangForm
                  a={a}
                  onFertig={(f) => {
                    if (f) {
                      setError(f);
                      return;
                    }
                    setGehtAb(null);
                    setError(null);
                    load();
                  }}
                />
              )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* „Was hatte ich mal": die Zeile bleibt (Owner), sie steht nur nicht mehr in den Listen. */}
      {abgaenge.length > 0 && (
        <details className="expiry-section abgaenge">
          <summary className="expiry-group-header">Abgegangen ({abgaenge.length})</summary>
          <div className="expiry-group">
            {abgaenge.map((a) => (
              <div key={a.id} className="expiry-item sache-zeile">
                <div className="sache-info">
                  <div className="sache-kopf">
                    <span className="platz-kennung">{a.kennung}</span>
                    <span className="sache-name">{a.name}</span>
                    {a.erloes != null && <span className="sache-wert">{fmtEur(a.erloes)}</span>}
                  </div>
                  <div className="sache-detail">
                    {[
                      `${a.abgang === 'verkauft' ? 'verkauft' : 'weg'} am ${fmtDatum(a.abgang_am)}`,
                      a.abgang_plattform,
                      a.purchase_price != null ? `gekauft für ${fmtEur(a.purchase_price)}` : null,
                    ].filter(Boolean).map((t) => <span key={t as string} className="sache-teil">{t}</span>)}
                  </div>
                  <div className="sache-aktionen">
                    {exemplar ? (
                      <span className="sache-teil">Zurücknehmen in medien</span>
                    ) : (
                      <button type="button" className="sache-griff" onClick={() => zuruecknehmen(a.id)}
                        disabled={nimmtZurueck === a.id}>
                        <Icon name="erneuern" className="knopf-icon" /> {nimmtZurueck === a.id ? '…' : 'Zurücknehmen'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
