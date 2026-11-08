import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type {
  EinbuchenIn,
  EinbuchenOut,
  EinkaufOut,
  ElectronicAssetOut,
  ProductOut,
  StockEntryOut,
  ZuruecknehmenOut,
} from '../types';
import { fristName, useBereich, useBereiche, weg } from '../bereich/kontext';
import Kopf from '../bereich/Kopf';
import PlatzWahl from '../components/PlatzWahl';
import ProductSelect from '../components/ProductSelect';
import Scanner, { type ScannerGriff } from '../components/Scanner';
import ZurueckKnopf from '../components/ZurueckKnopf';
import LadenZeichen, { KETTEN, type Kette } from '../components/LadenZeichen';
import { einheit, menge } from '../einheiten';
import { fotoAuswaehlen, fotoSenden, fotoUrl } from '../fotos';
import { MEDIEN, MEDIENTYPEN, ZUSTAENDE } from '../plaetze';

/* Der Einbuch-Lauf (Stufe 4, Vorbild medien).

   Ein Erfassen, kein Pruefen: was durch die Haende geht, wird gebucht, und
   die Quittung darunter laesst Menge, MHD und Preis korrigieren, ohne den
   naechsten Scan aufzuhalten (Owner: MHD als Vorschlag, spaeter korrigieren).

   Der Lauf lebt im Browser (sessionStorage je Bereich): ein Neuladen der
   Seite verliert ihn nicht, und der Server kennt keinen halben Lauf. Erst der
   Abschluss fasst die Dinge zu einem Einkauf mit Gesamtbetrag und Laden
   zusammen. Bei Vorraeten wird dabei nichts verteilt, bei Sachen bekommen die
   Stuecke ohne eigenen Preis den Rest (Owner 2026-11-01). */

type Eintrag = { art: 'posten'; posten: StockEntryOut } | { art: 'sache'; sache: ElectronicAssetOut };

type Frage =
  | { art: 'name'; code: string | null; vorschlag?: { name: string; category?: string | null } | null; hinweis?: string | null }
  | { art: 'menge'; code: string | null; name: string | null; produkt: string; einheit: string }
  | { art: 'bekannt'; code: string | null; vorhanden: ElectronicAssetOut[] };

interface Gespeichert {
  eintraege: Eintrag[];
  platzId: number | null;
  /** Leer = Vorgabe des Dienstes (Gut, bei Filmen Ungeprüft). */
  zustand: string;
  medium?: string;
  medientyp?: string;
}

type TitelTreffer = { id: number; titel: string; medientyp?: string | null; jahr?: string | null };
const EINHEITEN = ['piece', 'g', 'ml'];

const heute = () => new Date().toISOString().slice(0, 10);
const eur = (v: number) => `${v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

/** Komma oder Punkt, leer heisst kein Wert. */
function zahl(text: string): number | null {
  const t = text.trim().replace(',', '.');
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

function laden(schluessel: string): Gespeichert {
  try {
    const roh = sessionStorage.getItem(`lager-lauf-${schluessel}`);
    if (roh) return JSON.parse(roh) as Gespeichert;
  } catch {
    /* kaputter Stand: neu anfangen */
  }
  return { eintraege: [], platzId: null, zustand: '', medium: 'DVD', medientyp: 'Film' };
}

function PostenZeile({ p, frist, onNeu, onZurueck }: {
  p: StockEntryOut;
  frist: string;
  onNeu: (p: StockEntryOut, fehler?: string) => void;
  onZurueck: () => void;
}) {
  const [mengeText, setMengeText] = useState(String(p.quantity));
  const [preisText, setPreisText] = useState(p.preis == null ? '' : String(p.preis).replace('.', ','));

  async function aendern(body: Record<string, unknown>) {
    try {
      onNeu(await api.put<StockEntryOut>(`/stock/${p.id}`, body));
    } catch (err) {
      onNeu(p, fehlertext(err));
    }
  }

  return (
    <div className="lauf-zeile">
      <div className="lauf-zeile-kopf">
        <span className="lauf-name">{p.product_name}</span>
        <span className="lauf-ort">{p.platz_pfad || 'nicht eingelagert'}</span>
        <ZurueckKnopf onZurueck={onZurueck} />
      </div>
      <div className="lauf-felder">
        <label>
          <span>Menge</span>
          <span className="lauf-menge">
            <input
              className="form-input"
              inputMode="decimal"
              value={mengeText}
              onChange={(e) => setMengeText(e.target.value)}
              onBlur={() => {
                const n = zahl(mengeText);
                if (n != null && n > 0 && n !== p.quantity) aendern({ quantity: n, unit: p.unit });
                else setMengeText(String(p.quantity));
              }}
            />
            <select
              className="form-select"
              value={p.unit}
              aria-label="Einheit"
              onChange={(e) => aendern({ unit: e.target.value })}
            >
              {EINHEITEN.map((u) => <option key={u} value={u}>{einheit(u)}</option>)}
            </select>
          </span>
        </label>
        <label>
          <span>{frist}</span>
          <input
            className="form-input"
            type="date"
            value={p.mhd ?? ''}
            onChange={(e) => e.target.value && aendern({ mhd: e.target.value })}
          />
        </label>
        <label>
          <span>Preis</span>
          <input
            className="form-input"
            inputMode="decimal"
            placeholder="leer lassen"
            value={preisText}
            onChange={(e) => setPreisText(e.target.value)}
            onBlur={() => {
              const n = zahl(preisText);
              if (n !== (p.preis ?? null)) aendern({ preis: n });
            }}
          />
        </label>
      </div>
    </div>
  );
}

function SacheZeile({ s, scanner, scannerOffen, onNeu, onZurueck }: {
  s: ElectronicAssetOut;
  scanner: React.RefObject<ScannerGriff>;
  scannerOffen: boolean;
  onNeu: (s: ElectronicAssetOut, fehler?: string) => void;
  onZurueck: () => void;
}) {
  const [preisText, setPreisText] = useState(s.purchase_price == null ? '' : String(s.purchase_price).replace('.', ','));
  const [foto, setFoto] = useState(false);
  const bild = fotoUrl(s);

  async function aendern(body: Record<string, unknown>) {
    try {
      onNeu(await api.put<ElectronicAssetOut>(`/electronics/${s.id}`, body));
    } catch (err) {
      onNeu(s, fehlertext(err));
    }
  }

  async function fotoMachen() {
    setFoto(true);
    try {
      // Im laufenden Scanner aus dem Kamerastrom, sonst ueber die Dateiauswahl.
      const blob = scannerOffen && scanner.current ? await scanner.current.foto() : await fotoAuswaehlen();
      onNeu(await fotoSenden(s.id, blob));
    } catch (err) {
      const text = fehlertext(err);
      if (text !== 'Kein Bild gewählt') onNeu(s, text);
    } finally {
      setFoto(false);
    }
  }

  return (
    <div className="lauf-zeile">
      <div className="lauf-zeile-kopf">
        <span className="platz-kennung">{s.kennung}</span>
        <span className="lauf-name">{s.name}{s.teil ? ` · ${s.teil}` : ''}</span>
        <span className="lauf-ort">{[s.medium, s.platz_pfad || 'nicht eingelagert'].filter(Boolean).join(' · ')}</span>
        <ZurueckKnopf onZurueck={onZurueck} />
      </div>
      <div className="lauf-felder">
        <label>
          <span>Zustand</span>
          <select className="form-select" value={s.condition} onChange={(e) => aendern({ condition: e.target.value })}>
            {[...new Set([...ZUSTAENDE, s.condition])].map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
        <label>
          <span>Preis</span>
          <input
            className="form-input"
            inputMode="decimal"
            placeholder="aus dem Gesamtbetrag"
            value={preisText}
            onChange={(e) => setPreisText(e.target.value)}
            onBlur={() => {
              const n = zahl(preisText);
              // Leeren geht hier nicht ueber `null`: die Sachen-Route liest nur
              // gesetzte Werte. Ein leeres Feld bleibt deshalb einfach stehen.
              if (n != null && n !== s.purchase_price) aendern({ purchase_price: n });
            }}
          />
        </label>
        <div className="lauf-foto">
          {bild && <img src={bild} alt={`Foto von ${s.name}`} />}
          <button type="button" className="btn btn-sm btn-secondary" onClick={fotoMachen} disabled={foto}>
            {foto ? '…' : bild ? 'Neues Foto' : 'Foto'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Titel aus dem medien-Katalog waehlen (Filme & Medien). Der Browser fragt das
    Lager, das Lager fragt medien: den Schluessel dafuer hat nur der Dienst. */
function TitelSuche({ text, onText, onWahl }: {
  text: string;
  onText: (t: string) => void;
  onWahl: (t: TitelTreffer) => void;
}) {
  const [treffer, setTreffer] = useState<TitelTreffer[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    // Ohne Staffel suchen: der Katalog fuehrt „Two and a Half Men", die Huelle
    // sagt „… – Staffel 3".
    const q = text.replace(/\s*[-–:]?\s*(staffel|season)\s*\d+(\s*[-–]\s*\d+)?\s*$/i, '').trim();
    if (q.length < 2) {
      setTreffer([]);
      return;
    }
    const uhr = window.setTimeout(() => {
      api.get<TitelTreffer[]>(`/medien/titel?q=${encodeURIComponent(q)}`)
        .then((t) => { setTreffer(t.slice(0, 8)); setFehler(null); })
        .catch((e) => setFehler(fehlertext(e)));
    }, 250);
    return () => window.clearTimeout(uhr);
  }, [text]);

  return (
    <>
      <input className="form-input" value={text} onChange={(e) => onText(e.target.value)}
        placeholder="Titel auf der Hülle, z. B. Alien oder … – Staffel 3" autoFocus />
      {fehler && <div className="lauf-meldung fehler">{fehler}</div>}
      {treffer.length > 0 && (
        <ul className="lauf-bekannt titel-treffer">
          {treffer.map((t) => (
            <li key={t.id}>
              <button type="button" className="chip" onClick={() => onWahl(t)}>
                {t.titel}{t.jahr ? ` (${t.jahr})` : ''}{t.medientyp ? ` · ${t.medientyp}` : ''}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export default function LaufPage() {
  const { schluessel, bereich } = useBereich();
  const { neuLaden } = useBereiche();
  const istExemplar = bereich?.bauart === 'exemplar';
  const istSache = bereich?.bauart === 'stueck' || istExemplar;
  const frist = fristName(bereich);

  const [stand, setStand] = useState<Gespeichert>(() => laden(schluessel));
  const [frage, setFrage] = useState<Frage | null>(null);
  const [offen, setOffen] = useState(false);
  const [beschaeftigt, setBeschaeftigt] = useState(false);
  const [meldung, setMeldung] = useState<{ text: string; fehler?: boolean } | null>(null);
  const [nameText, setNameText] = useState('');
  const [mengeText, setMengeText] = useState('');
  const [mengeEinheit, setMengeEinheit] = useState('piece');
  const [laden_, setLaden] = useState('');
  // Laden einmal je Einkauf: eine Kette per Logo oder Sonstiger mit Freitext.
  const [kette, setKette] = useState<Kette | 'sonstiger' | null>(null);
  const [gesamtText, setGesamtText] = useState('');
  const [am, setAm] = useState(heute());
  const [laeden, setLaeden] = useState<string[]>([]);
  const scanner = useRef<ScannerGriff>(null);

  useEffect(() => {
    sessionStorage.setItem(`lager-lauf-${schluessel}`, JSON.stringify(stand));
  }, [schluessel, stand]);

  useEffect(() => {
    api.get<EinkaufOut[]>('/einkaeufe?limit=100')
      .then((e) => setLaeden([...new Set(e.filter((x) => !x.kette).map((x) => x.laden).filter((x): x is string => !!x))]))
      .catch(() => setLaeden([]));
  }, []);

  const postenIds = stand.eintraege.flatMap((e) => (e.art === 'posten' ? [e.posten.id] : []));
  const sachenIds = stand.eintraege.flatMap((e) => (e.art === 'sache' ? [e.sache.id] : []));
  const ohnePreis = stand.eintraege.filter((e) =>
    e.art === 'posten' ? e.posten.preis == null : e.sache.purchase_price == null).length;

  const eintragen = useCallback((neu: Eintrag) => {
    setStand((s) => ({
      ...s,
      eintraege: [neu, ...s.eintraege.filter((e) =>
        !(e.art === neu.art && (e.art === 'posten'
          ? e.posten.id === (neu as { posten: StockEntryOut }).posten.id
          : e.sache.id === (neu as { sache: ElectronicAssetOut }).sache.id)))],
    }));
  }, []);

  async function senden(extra: Partial<EinbuchenIn>) {
    setBeschaeftigt(true);
    setMeldung(null);
    try {
      const body: EinbuchenIn = {
        bereich: schluessel,
        platz_id: stand.platzId,
        zustand: istSache ? stand.zustand || null : null,
        ...(istExemplar ? { medium: stand.medium ?? null, medientyp: stand.medientyp ?? null } : {}),
        lauf_posten: postenIds,
        ...extra,
      };
      const r = await api.post<EinbuchenOut>('/laeufe/einbuchen', body);
      const anders = r.anderer_bereich ? ` (gehört zum Bereich ${r.anderer_bereich})` : '';
      switch (r.art) {
        case 'neu':
        case 'mehr':
          setFrage(null);
          if (r.posten) {
            eintragen({ art: 'posten', posten: r.posten });
            setMeldung({ text: r.art === 'mehr'
              ? `${r.posten.product_name}: jetzt ${menge(r.posten.quantity, r.posten.unit)}${anders}`
              : `${r.posten.product_name} eingebucht${r.produkt_neu ? ', neues Produkt' : ''}${anders}` });
          }
          if (r.sache) {
            eintragen({ art: 'sache', sache: r.sache });
            setMeldung({ text: `${r.sache.kennung} ${r.sache.name} eingebucht${r.titel_offen
              ? '. medien antwortet gerade nicht, der Titel wird nachgetragen' : ''}` });
          }
          break;
        case 'wiedergesehen':
          setFrage(null);
          setMeldung({ text: `${r.sache?.kennung} ${r.sache?.name} ist schon im Bestand. Kein Zugang.` });
          break;
        case 'name_fehlt':
          setNameText(r.vorschlag?.name ?? '');
          setFrage({ art: 'name', code: r.code ?? null, vorschlag: r.vorschlag, hinweis: r.hinweis });
          break;
        case 'menge_fehlt':
          setMengeText('');
          setMengeEinheit(r.produkt_einheit ?? 'g');
          setFrage({ art: 'menge', code: r.code ?? null, name: extra.name ?? null,
            produkt: r.produkt_name ?? '', einheit: r.produkt_einheit ?? 'g' });
          break;
        case 'bekannt':
          setFrage({ art: 'bekannt', code: r.code ?? null, vorhanden: r.vorhanden ?? [] });
          break;
      }
    } catch (err) {
      setMeldung({ text: fehlertext(err), fehler: true });
    } finally {
      setBeschaeftigt(false);
    }
  }

  function zeileNeu(neu: Eintrag, fehler?: string) {
    if (fehler) setMeldung({ text: fehler, fehler: true });
    else eintragen(neu);
  }

  /* Ein Fehlscan geht ganz: der Dienst loescht den Posten bzw. das Stueck,
     solange nichts verbraucht und kein Einkauf daran haengt. Eine zu hohe
     Menge nach einem doppelten Scan aendert man dagegen im Mengenfeld. */
  async function zuruecknehmen(e: Eintrag) {
    setBeschaeftigt(true);
    try {
      const r = await api.post<ZuruecknehmenOut>('/laeufe/einbuchen/zuruecknehmen',
        e.art === 'posten' ? { posten_id: e.posten.id } : { sache_id: e.sache.id });
      setStand((s) => ({
        ...s,
        eintraege: s.eintraege.filter((x) => !(x.art === e.art && (x.art === 'posten'
          ? x.posten.id === (e as { posten: StockEntryOut }).posten.id
          : x.sache.id === (e as { sache: ElectronicAssetOut }).sache.id))),
      }));
      setMeldung({ text: r.text });
      neuLaden();
    } catch (err) {
      setMeldung({ text: fehlertext(err), fehler: true });
    } finally {
      setBeschaeftigt(false);
    }
  }

  const ladenText = kette === 'sonstiger' ? laden_.trim() : '';
  const istKette = kette != null && kette !== 'sonstiger';

  async function abschliessen() {
    const gesamt = zahl(gesamtText);
    setBeschaeftigt(true);
    try {
      const e = await api.post<EinkaufOut | null>('/laeufe/abschluss', {
        bereich: schluessel, posten: postenIds, sachen: sachenIds,
        gesamt, kette: istKette ? kette : null, laden: ladenText || null, am,
      });
      const n = stand.eintraege.length;
      let text = `Lauf beendet: ${n} ${n === 1 ? 'Eintrag' : 'Einträge'}.`;
      if (e) {
        text = `Einkauf ${e.laden ?? ''} vom ${new Date(e.am).toLocaleDateString('de-DE')}`
          + (e.gesamt != null ? ` über ${eur(e.gesamt)}` : '') + ` gespeichert.`;
        const verteilt = Object.keys(e.verteilt ?? {}).length;
        if (verteilt) text += ` ${verteilt} ${verteilt === 1 ? 'Stück bekam' : 'Stücke bekamen'} den Rest als Preis.`;
        else if (e.ohne_preis) text += ` ${e.ohne_preis} ohne Einzelpreis.`;
      }
      setStand((s) => ({ ...s, eintraege: [] }));
      setGesamtText('');
      setLaden('');
      setKette(null);
      setFrage(null);
      setMeldung({ text });
      neuLaden();
    } catch (err) {
      setMeldung({ text: fehlertext(err), fehler: true });
    } finally {
      setBeschaeftigt(false);
    }
  }

  const arbeitsfeld = (
    <>
      {meldung && <div className={meldung.fehler ? 'lauf-meldung fehler' : 'lauf-meldung'}>{meldung.text}</div>}

      {frage?.art === 'name' && (
        <form
          className="lauf-frage"
          onSubmit={(e) => {
            e.preventDefault();
            if (nameText.trim()) senden({ code: frage.code, name: nameText.trim(), kategorie: frage.vorschlag?.category ?? null });
          }}
        >
          <p>
            {frage.hinweis ? <>{frage.hinweis} </> : frage.code ? <>Diesen Strichcode kennt das Lager noch nicht. </> : null}
            {frage.vorschlag ? <>Der Name ist ein Vorschlag aus OpenFoodFacts, bitte prüfen.</> : <>Wie heißt es?</>}
          </p>
          {istExemplar ? (
            <TitelSuche text={nameText} onText={setNameText}
              onWahl={(t) => senden({ code: frage.code, titel_id: t.id, katalogtitel: t.titel, name: nameText.trim() || t.titel })} />
          ) : (
            <input className="form-input" value={nameText} onChange={(e) => setNameText(e.target.value)}
              placeholder={istSache ? 'Name, z. B. Akkuschrauber' : 'Name, z. B. Haferdrink'} autoFocus />
          )}
          {istExemplar && (
            <p className="form-hinweis">
              Einen Titel antippen, oder übernehmen: dann findet medien ihn oder legt ihn an. Eine
              Staffel im Namen wird zum Teil.
            </p>
          )}
          {!istSache && (
            <div className="lauf-oder">
              oder vorhandenes Produkt wählen:
              <ProductSelect bereich={schluessel} placeholder="Produkt suchen…"
                onSelect={(p: ProductOut) => senden({ code: frage.code, name: p.name })} />
            </div>
          )}
          <div className="inline-form-actions">
            <button type="submit" className="btn btn-sm btn-secondary" disabled={!nameText.trim() || beschaeftigt}>Einbuchen</button>
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => setFrage(null)}>Überspringen</button>
          </div>
        </form>
      )}

      {frage?.art === 'menge' && (
        <form
          className="lauf-frage"
          onSubmit={(e) => {
            e.preventDefault();
            const n = zahl(mengeText);
            if (n && n > 0) senden({ code: frage.code, name: frage.name, menge: n, einheit: mengeEinheit });
          }}
        >
          <p>Wie viel {frage.produkt}? Das Lager kennt dafür noch keine Packungsgröße.</p>
          <span className="lauf-menge">
            <input className="form-input" inputMode="decimal" value={mengeText}
              onChange={(e) => setMengeText(e.target.value)} placeholder="Menge" autoFocus />
            <select className="form-select" value={mengeEinheit} onChange={(e) => setMengeEinheit(e.target.value)} aria-label="Einheit">
              {['g', 'kg', 'ml', 'l', 'piece'].map((u) => <option key={u} value={u}>{einheit(u)}</option>)}
            </select>
          </span>
          <div className="inline-form-actions">
            <button type="submit" className="btn btn-sm btn-secondary" disabled={!zahl(mengeText) || beschaeftigt}>Einbuchen</button>
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => setFrage(null)}>Überspringen</button>
          </div>
        </form>
      )}

      {frage?.art === 'bekannt' && (
        <div className="lauf-frage">
          <p>Davon gibt es schon {frage.vorhanden.length === 1 ? 'ein Stück' : `${frage.vorhanden.length} Stücke`}:</p>
          <ul className="lauf-bekannt">
            {frage.vorhanden.map((v) => (
              <li key={v.id}>
                <span className="platz-kennung">{v.kennung}</span> {v.name} · {v.condition} · {v.platz_pfad || 'nicht eingelagert'}
              </li>
            ))}
          </ul>
          <div className="inline-form-actions">
            <button type="button" className="btn btn-sm btn-secondary" disabled={beschaeftigt}
              onClick={() => senden({ code: frage.code, bestaetigt: true })}>Neues Stück einbuchen</button>
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => setFrage(null)}>Überspringen</button>
          </div>
        </div>
      )}
    </>
  );

  const zeilen = (liste: Eintrag[]) => liste.map((e) => e.art === 'posten'
    ? <PostenZeile key={`p-${e.posten.id}-${e.posten.quantity}-${e.posten.preis}`} p={e.posten} frist={frist}
        onNeu={(p, f) => zeileNeu({ art: 'posten', posten: p }, f)} onZurueck={() => zuruecknehmen(e)} />
    : <SacheZeile key={`s-${e.sache.id}-${e.sache.purchase_price}`} s={e.sache} scanner={scanner} scannerOffen={offen}
        onNeu={(s, f) => zeileNeu({ art: 'sache', sache: s }, f)} onZurueck={() => zuruecknehmen(e)} />);

  const zaehler = `${stand.eintraege.length} ${stand.eintraege.length === 1 ? 'Eintrag' : 'Einträge'} in diesem Lauf`
    + (stand.eintraege.length ? ` · ${ohnePreis} ohne Preis` : '');

  return (
    <div className="page">
      <Kopf titel="Einbuchen" />
      <p className="seiten-satz">
        Scannen, und was durch die Hände geht, ist gebucht. {istExemplar
          ? 'Der Titel kommt aus dem medien-Katalog; jede Scheibe bekommt eine Kennung (S-0001), Zustand, Preis und Foto stehen in der Quittung.'
          : istSache
          ? 'Jedes Stück bekommt eine Kennung (S-0001); Zustand, Preis und Foto stehen in der Quittung.'
          : `Menge, ${frist} und Preis stehen als Vorschlag in der Quittung und lassen sich dort ändern.`}
      </p>

      <div className="lauf-vorgabe">
        <PlatzWahl wert={stand.platzId} onWahl={(platzId) => setStand((s) => ({ ...s, platzId }))}
          label="Platz für diesen Durchgang" />
        {istExemplar && (
          <div className="lauf-felder lauf-vorgabe-felder">
            <label>
              <span>Medium</span>
              <select className="form-select" value={stand.medium ?? 'DVD'}
                onChange={(e) => setStand((s) => ({ ...s, medium: e.target.value }))}>
                {MEDIEN.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
            <label>
              <span>Medientyp</span>
              <select className="form-select" value={stand.medientyp ?? 'Film'}
                onChange={(e) => setStand((s) => ({ ...s, medientyp: e.target.value }))}>
                {MEDIENTYPEN.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
          </div>
        )}
        {istSache && (
          <div className="form-group">
            <label className="form-label">Zustand für diesen Durchgang</label>
            <select className="form-select" value={stand.zustand}
              onChange={(e) => setStand((s) => ({ ...s, zustand: e.target.value }))}>
              <option value="">{istExemplar ? 'Ungeprüft (nicht angesehen)' : 'Gut (Vorgabe)'}</option>
              {ZUSTAENDE.filter((z) => z !== 'Ungeprüft').map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="lauf-knoepfe">
        <button type="button" className="btn btn-primary btn-lg" onClick={() => { setMeldung(null); setOffen(true); }}>
          Scannen
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => { setNameText(''); setFrage({ art: 'name', code: null }); }}>
          Ohne Strichcode
        </button>
        <span className="lauf-zaehler">{zaehler}</span>
      </div>

      {!offen && arbeitsfeld}

      <div className="lauf-liste">{zeilen(stand.eintraege)}</div>

      {stand.eintraege.length > 0 && (
        <section className="lauf-abschluss">
          <h2 className="regal-titel">Lauf abschließen</h2>
          <p className="form-hinweis">
            {istSache
              ? 'Ein Gesamtbetrag geht auf die Stücke ohne eigenen Preis, gewichtet nach Marktwert, wenn ihn jedes hat.'
              : 'Der Gesamtbetrag gilt für den Einkauf und wird nicht auf die Posten verteilt. Einzelpreise kommen aus der Quittung.'}
            {' '}Beides ist freiwillig. Mit Laden lernt die Einkaufsliste, wo es am günstigsten war.
          </p>
          <div className="laden-wahl" role="group" aria-label="Laden">
            {KETTEN.map((k) => (
              <button key={k.schluessel} type="button" className="laden-knopf"
                aria-pressed={kette === k.schluessel}
                onClick={() => setKette(kette === k.schluessel ? null : k.schluessel)}>
                <LadenZeichen kette={k.schluessel} gross /> {k.name}
              </button>
            ))}
            <button type="button" className="laden-knopf sonstiger" aria-pressed={kette === 'sonstiger'}
              onClick={() => setKette(kette === 'sonstiger' ? null : 'sonstiger')}>
              Sonstiger
            </button>
          </div>
          <div className="lauf-felder">
            {kette === 'sonstiger' && (
              <label>
                <span>Laden</span>
                <input className="form-input" list="lauf-laeden" value={laden_} onChange={(e) => setLaden(e.target.value)} placeholder="z. B. Wochenmarkt" autoFocus />
                <datalist id="lauf-laeden">{laeden.map((l) => <option key={l} value={l} />)}</datalist>
              </label>
            )}
            <label>
              <span>Gesamtbetrag</span>
              <input className="form-input" inputMode="decimal" value={gesamtText} onChange={(e) => setGesamtText(e.target.value)} placeholder="z. B. 47,80" />
            </label>
            <label>
              <span>Datum</span>
              <input className="form-input" type="date" value={am} onChange={(e) => setAm(e.target.value)} />
            </label>
          </div>
          <button type="button" className="btn btn-secondary btn-block" onClick={abschliessen} disabled={beschaeftigt}>
            {zahl(gesamtText) != null || istKette || ladenText ? 'Einkauf speichern und Lauf beenden' : 'Lauf beenden'}
          </button>
        </section>
      )}

      {!istSache && (
        <p className="form-hinweis lauf-fuss">
          Lieber ein Formular? <Link to={weg(schluessel, 'einbuchen')}>Einzeln von Hand einbuchen</Link>.
        </p>
      )}

      <Scanner
        ref={scanner}
        offen={offen}
        titel={`Einbuchen · ${bereich?.name ?? ''}`}
        stand={zaehler}
        gesperrt={beschaeftigt || frage != null}
        onCode={(code) => senden({ code })}
        onSchliessen={() => setOffen(false)}
      >
        {arbeitsfeld}
        {zeilen(stand.eintraege.slice(0, 1))}
      </Scanner>
    </div>
  );
}
