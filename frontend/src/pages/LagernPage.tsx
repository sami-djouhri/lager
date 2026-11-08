import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { LagernIn, LagernOut, PlatzDingOut, PlatzOut, ZuruecknehmenOut } from '../types';
import Scanner from '../components/Scanner';
import ZurueckKnopf from '../components/ZurueckKnopf';
import { GRUND_NAMEN } from '../plaetze';

/* Der Lagern-Lauf (Stufe 4, Vorbild medien). Zwei Griffe: Fach-Etikett
   scannen, Ding scannen. Am Praefix erkennt der Dienst ohne Rueckfrage, was
   vor der Kamera war (`L-` Platz, `S-` Stueck, sonst Strichcode).

   Der Pin ist der Kern: das Fach wird mindestens einmal gescannt, der Pin
   entscheidet nur, ob es stehen bleibt. Gepinnt sind zwanzig Dinge ins selbe
   Fach 21 Scans statt 40; ohne Pin verlangt jedes Ding seinen eigenen
   Platzscan. ⚠️ Ein frisch gescanntes Fach ist NICHT von selbst gepinnt: sonst
   klebte ein versehentlicher Scan am naechsten Ding, und das laege im falschen
   Fach, ohne dass es auffaellt.

   Drei Richtungen (Owner 2026-11-01): Einlagern nimmt nur, was noch keinen
   Platz hat; Umlagern nur, was schon in einem Fach liegt; Auf den Shopfloor
   holt aus dem Fach, auch Vorraete. Der Grund gilt fuer den ganzen Lauf und
   nur fuer Sachen: Vorraete kennen keinen Grund. */

type Richtung = 'ein' | 'um' | 'aus';

const RICHTUNGEN: { wert: Richtung; name: string }[] = [
  { wert: 'ein', name: 'Einlagern' },
  { wert: 'um', name: 'Umlagern' },
  { wert: 'aus', name: 'Auf den Shopfloor' },
];

interface Gebucht {
  ding: PlatzDingOut;
  vorher: string;
  richtung: Richtung;
  // Stand vor der Buchung, fuer „Zuruecknehmen" (aus LagernOut)
  vorherPlatzId: number | null;
  vorherVerbleib: string | null;
  vorherGrund: string | null;
}

type Frage = { code: string; mhds: (string | null)[]; zustaende: string[]; gruende: string[] };

const datum = (d: string) => new Date(d).toLocaleDateString('de-DE');

export default function LagernPage() {
  const [richtung, setRichtung] = useState<Richtung>('ein');
  const [grund, setGrund] = useState<string | null>(null);
  const [platz, setPlatz] = useState<PlatzOut | null>(null);
  const [gepinnt, setGepinnt] = useState(false);
  const [liste, setListe] = useState<Gebucht[]>([]);
  const [frage, setFrage] = useState<Frage | null>(null);
  const [offen, setOffen] = useState(false);
  const [beschaeftigt, setBeschaeftigt] = useState(false);
  const [meldung, setMeldung] = useState<{ text: string; fehler?: boolean } | null>(null);
  const [eingabe, setEingabe] = useState('');

  const brauchtFach = richtung !== 'aus';

  async function senden(code: string, antwort: Partial<LagernIn> = {}) {
    setBeschaeftigt(true);
    setMeldung(null);
    try {
      const body: LagernIn = {
        richtung, code, platz_id: brauchtFach ? platz?.id ?? null : null,
        grund: richtung === 'aus' ? grund : null, ...antwort,
      };
      // Ohne Fach gar nicht erst fragen, ausser es ist selbst ein Fach-Etikett.
      if (brauchtFach && !platz && !/^\s*L[:-]?\d/i.test(code)) {
        setMeldung({ text: 'Zuerst das Fach-Etikett scannen.', fehler: true });
        return;
      }
      const r = await api.post<LagernOut>('/laeufe/lagern', body);
      if (r.art === 'platz' && r.platz) {
        setPlatz(r.platz);
        setGepinnt(false);
        setFrage(null);
        setMeldung({ text: `Ziel: ${r.platz.kennung} ${r.platz.pfad}` });
        return;
      }
      if (r.art === 'welches' || r.art === 'grund_fehlt') {
        setFrage({ code, mhds: r.mhds ?? [], zustaende: r.zustaende ?? [], gruende: r.gruende ?? [] });
        return;
      }
      setFrage(null);
      if (r.art === 'gebucht' && r.ding) {
        const g: Gebucht = {
          ding: r.ding, vorher: r.vorher_pfad ?? '', richtung,
          vorherPlatzId: r.vorher_platz_id ?? null,
          vorherVerbleib: r.vorher_verbleib ?? null,
          vorherGrund: r.vorher_grund ?? null,
        };
        // Ein zweiter Scan desselben Dings ersetzt die Zeile, behaelt aber den
        // Stand vor der ERSTEN Buchung: Zuruecknehmen fuehrt dorthin zurueck,
        // wo es vor diesem Durchgang lag.
        setListe((l) => {
          const alt = l.find((x) => x.ding.art === g.ding.art && x.ding.id === g.ding.id);
          const neu = alt ? { ...g, vorher: alt.vorher, vorherPlatzId: alt.vorherPlatzId,
            vorherVerbleib: alt.vorherVerbleib, vorherGrund: alt.vorherGrund } : g;
          return [neu, ...l.filter((x) => x !== alt)];
        });
        setMeldung({ text: `${g.ding.name}: ${wegText(g)}` });
        // Ohne Pin ist das Ziel nach der Buchung verbraucht.
        if (brauchtFach && !gepinnt) setPlatz(null);
        return;
      }
      setMeldung({ text: r.hinweis ?? 'Nichts gebucht.', fehler: true });
    } catch (err) {
      setMeldung({ text: fehlertext(err), fehler: true });
    } finally {
      setBeschaeftigt(false);
    }
  }

  async function zuruecknehmen(g: Gebucht) {
    setBeschaeftigt(true);
    try {
      const r = await api.post<ZuruecknehmenOut>('/laeufe/lagern/zuruecknehmen', {
        ...(g.ding.art === 'sache' ? { sache_id: g.ding.id } : { posten_id: g.ding.id }),
        vorher_platz_id: g.vorherPlatzId,
        vorher_verbleib: g.vorherVerbleib,
        vorher_grund: g.vorherGrund,
      });
      setListe((l) => l.filter((x) => x !== g));
      setMeldung({ text: r.text });
    } catch (err) {
      setMeldung({ text: fehlertext(err), fehler: true });
    } finally {
      setBeschaeftigt(false);
    }
  }

  function wechseln(r: Richtung) {
    setRichtung(r);
    setFrage(null);
    setMeldung(null);
    if (r === 'aus') {
      setPlatz(null);
      setGepinnt(false);
    }
  }

  const standText = brauchtFach
    ? (platz ? `Ziel: ${platz.kennung} ${platz.pfad}${gepinnt ? ' (angeheftet)' : ''}` : 'Erst ein Fach-Etikett scannen.')
    : `Grund für Sachen: ${grund ? GRUND_NAMEN[grund] : 'wird beim ersten Stück gefragt'}`;

  const arbeitsfeld = (
    <>
      {meldung && <div className={meldung.fehler ? 'lauf-meldung fehler' : 'lauf-meldung'}>{meldung.text}</div>}
      {frage && (
        <div className="lauf-frage">
          {frage.gruende.length > 0 ? (
            <>
              <p>Warum kommt es aus dem Fach? Die Gründe gelten je Bereich.</p>
              <div className="filter-chips">
                {frage.gruende.map((g) => (
                  <button key={g} type="button" className="chip"
                    onClick={() => { setGrund(g); senden(frage.code, { grund: g }); }}>
                    {GRUND_NAMEN[g] ?? g}
                  </button>
                ))}
              </div>
            </>
          ) : frage.mhds.length > 0 ? (
            <>
              <p>Davon liegen Posten mit verschiedenem MHD. Welches Datum steht auf der Packung?</p>
              <div className="filter-chips">
                {frage.mhds.map((m) => (
                  <button key={m ?? 'ohne'} type="button" className="chip"
                    onClick={() => senden(frage.code, m ? { mhd: m } : { ohne_mhd: true })}>
                    {m ? datum(m) : 'ohne MHD'}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <p>Mehrere Stücke tragen diesen Code. Welchen Zustand hat das in deiner Hand?</p>
              <div className="filter-chips">
                {frage.zustaende.map((z) => (
                  <button key={z} type="button" className="chip" onClick={() => senden(frage.code, { zustand: z })}>{z}</button>
                ))}
              </div>
            </>
          )}
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => setFrage(null)}>Überspringen</button>
        </div>
      )}
    </>
  );

  const pin = brauchtFach && platz && (
    <button type="button" className={gepinnt ? 'btn btn-sm btn-secondary aktiv' : 'btn btn-sm btn-secondary'}
      aria-pressed={gepinnt} onClick={() => setGepinnt((g) => !g)}>
      {gepinnt ? 'Fach lösen' : 'Fach anheften'}
    </button>
  );

  return (
    <div className="page">
      <Link to="/plaetze" className="page-bereich">Plätze</Link>
      <h1 className="page-title">Lagern</h1>
      <p className="seiten-satz">Fach-Etikett scannen, dann das Ding.</p>

      <div className="tabs" role="tablist" aria-label="Richtung">
        {RICHTUNGEN.map((r) => (
          <button key={r.wert} type="button" role="tab" aria-selected={richtung === r.wert}
            className={richtung === r.wert ? 'tab active' : 'tab'} onClick={() => wechseln(r.wert)}>
            {r.name}
          </button>
        ))}
      </div>

      {richtung === 'aus' && (
        <>
          <div className="filter-chips">
            {Object.entries(GRUND_NAMEN).map(([k, v]) => (
              <button key={k} type="button" className={grund === k ? 'chip active' : 'chip'}
                aria-pressed={grund === k} onClick={() => setGrund(k)}>{v}</button>
            ))}
          </div>
          <p className="form-hinweis">
            Der Grund gilt für alle Sachen in diesem Durchgang, Vorräte brauchen keinen; passt er
            nicht zum Bereich des Stücks, fragt der Lauf nach. Eine Sache behält ihren Platz und
            findet beim Zurücklegen ihr Fach wieder.
          </p>
        </>
      )}

      {/* Ein gewaehlter Grund steht schon als Marke da; der Satz wiederholte ihn nur. */}
      {(brauchtFach || !grund) && <p className="lauf-stand">{standText}</p>}

      <div className="lauf-knoepfe">
        <button type="button" className="btn btn-primary btn-lg" onClick={() => { setMeldung(null); setOffen(true); }}>
          Scannen
        </button>
        {pin}
        {brauchtFach && platz && !gepinnt && (
          <span className="form-hinweis">Anheften hält das Fach für die nächsten Scans.</span>
        )}
        <span className="lauf-zaehler">{liste.length ? `${liste.length} gebucht` : ''}</span>
      </div>

      <form className="barcode-manual-row lauf-hand" onSubmit={(e) => {
        e.preventDefault();
        const code = eingabe.trim();
        setEingabe('');
        if (code) senden(code);
      }}>
        <input className="form-input" value={eingabe} onChange={(e) => setEingabe(e.target.value)}
          placeholder="L-001, S-0001 oder Strichcode" autoComplete="off" aria-label="Code eintippen" />
        <button type="submit" className="btn btn-sm btn-secondary" disabled={!eingabe.trim() || beschaeftigt}>Los</button>
      </form>

      {!offen && arbeitsfeld}

      <div className="lauf-liste">
        {liste.map((g) => <LagerZeile key={`${g.ding.art}-${g.ding.id}`} g={g} onZurueck={() => zuruecknehmen(g)} />)}
        {!liste.length && <p className="form-hinweis">Noch nichts in diesem Durchgang.</p>}
      </div>

      <Scanner
        offen={offen}
        titel={RICHTUNGEN.find((r) => r.wert === richtung)!.name}
        stand={<>{standText} {pin}</>}
        gesperrt={beschaeftigt || frage != null}
        onCode={(code) => senden(code)}
        onSchliessen={() => setOffen(false)}
      >
        {arbeitsfeld}
        {liste[0] && <LagerZeile g={liste[0]} onZurueck={() => zuruecknehmen(liste[0])} />}
      </Scanner>
    </div>
  );
}

function wegText(g: Gebucht): string {
  const d = g.ding;
  if (g.richtung === 'aus') {
    const grund = d.shopfloor_grund ? GRUND_NAMEN[d.shopfloor_grund] : 'nicht eingelagert';
    return d.art === 'sache' && d.platz_pfad ? `${grund} · gehört nach ${d.platz_pfad}` : grund;
  }
  return g.vorher ? `${g.vorher} → ${d.platz_pfad}` : `→ ${d.platz_pfad}`;
}

function LagerZeile({ g, onZurueck }: { g: Gebucht; onZurueck: () => void }) {
  const d = g.ding;
  return (
    <div className="lauf-zeile">
      <div className="lauf-zeile-kopf">
        {d.kennung && <span className="platz-kennung">{d.kennung}</span>}
        <span className="lauf-name">{d.name}</span>
        <span className="lauf-ort">{wegText(g)}</span>
        <ZurueckKnopf onZurueck={onZurueck} />
      </div>
      {d.detail && <div className="form-hinweis">{d.detail}</div>}
    </div>
  );
}
