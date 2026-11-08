import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import { useBereiche, weg } from '../bereich/kontext';
import type { BereichOut } from '../types';
import LoadError from '../components/LoadError';
import Icon from '../components/Icon';

/* Die Startseite ist die Bereichswahl (Owner 2026-11-01: „Startseite klickt
   man Bereich an"). Gebaut wie ein Inhaltsverzeichnis vorn im Bestandsbuch;
   die Saetze und ihre Rangfolge rechnet der Server (`app/bereiche.py`).

   Geordnet nach Lage, nicht nach der festen Reihenfolge der Bereiche. In
   der ersten Fassung standen neun gleich schwere Zeilen untereinander, und
   der eine Bereich, in dem etwas verdirbt, unterschied sich von den anderen
   nur durch eine drei Pixel breite Kante. Jetzt steht oben, was ansteht, mit
   der Zahl vorn; leere Bereiche teilen sich einen Satz, statt ihn viermal zu
   wiederholen; nicht gebaute stehen in einer Zeile ganz unten.

   Die Farbe bleibt der Verfallsskala vorbehalten: die Zahl traegt die
   Farbe der Frist (vorbei, bald), ein knapper Vorrat bleibt Tinte. Ein noch
   nicht gebauter Bereich ist kein Link, sonst fuehrte er in eine leere Seite
   und saehe kaputt aus. */

// Umgekehrt formuliert: alles, was weder ruhig noch leer ist, steht an.
// Die erste Fassung zaehlte die anstehenden Saetze auf, und jeder neue Satz
// des Servers (`verkauf`, `ohne_inhalt`) fiel still von der Startseite.
const IM_LOT = ['ruhig', 'leer'];

// Die Stufe steht nur im Satz des Servers („Kommt mit Stufe 4: …"), ein
// eigenes Feld gibt es nicht. Fehlt sie, bleibt der Name allein stehen.
function stufeAus(b: BereichOut): string | null {
  return b.satz.text.match(/Stufe (\d+)/)?.[1] ?? null;
}

function Zeile({ b }: { b: BereichOut }) {
  const ansteht = !IM_LOT.includes(b.satz.schluessel);
  return (
    <Link
      to={weg(b.schluessel)}
      className={`bereich-zeile satz-${b.satz.schluessel}${b.satz.blockiert ? ' blockiert' : ''}`}
    >
      {ansteht && <span className="bereich-zahl">{b.satz.anzahl}</span>}
      <span className="bereich-text">
        <span className="bereich-name">{b.name}</span>
        <span className="bereich-satz">{b.satz.text}</span>
      </span>
      <Icon name="pfeil" className="bereich-pfeil" />
    </Link>
  );
}

export default function StartPage() {
  const { bereiche, fehler, laedt, neuLaden } = useBereiche();

  // Zurueck auf der Startseite: Saetze neu rechnen lassen, sonst steht nach
  // dem Ausbuchen noch der alte Satz da.
  useEffect(() => {
    neuLaden();
  }, [neuLaden]);

  if (laedt && bereiche.length === 0) return <div className="page loading">Bereiche werden geladen</div>;

  const bereit = bereiche.filter((b) => b.bereit);
  const stehtAn = bereit.filter((b) => !IM_LOT.includes(b.satz.schluessel));
  const imLot = bereit.filter((b) => b.satz.schluessel === 'ruhig');
  const leer = bereit.filter((b) => b.satz.schluessel === 'leer');
  const kommtNoch = bereiche.filter((b) => !b.bereit);
  // Ein gemeinsamer Satz nur, wenn er fuer alle leeren Bereiche wirklich
  // derselbe ist; sonst steht er je Bereich.
  const leerSaetze = new Set(leer.map((b) => b.satz.text));
  const leerGemeinsam = leerSaetze.size === 1 ? [...leerSaetze][0] : null;

  return (
    <div className="page">
      <h1 className="page-title">Lager</h1>

      {fehler && <LoadError was="Die Bereichsliste" fehler={fehler} onRetry={neuLaden} />}

      {stehtAn.length > 0 && (
        <section className="regal" aria-labelledby="regal-an">
          <h2 id="regal-an" className="regal-titel">Steht an</h2>
          <div className="bereichsliste">
            {stehtAn.map((b) => <Zeile key={b.schluessel} b={b} />)}
          </div>
        </section>
      )}

      {imLot.length > 0 && (
        <section className="regal" aria-labelledby="regal-lot">
          <h2 id="regal-lot" className="regal-titel">Im Lot</h2>
          <div className="bereichsliste">
            {imLot.map((b) => <Zeile key={b.schluessel} b={b} />)}
          </div>
        </section>
      )}

      {leer.length > 0 && (
        <section className="regal" aria-labelledby="regal-leer">
          <h2 id="regal-leer" className="regal-titel">Noch leer</h2>
          <div className="leer-liste">
            {leer.map((b) => (
              <Link key={b.schluessel} to={weg(b.schluessel)} className="leer-eintrag">
                <span className="bereich-name">{b.name}</span>
                {!leerGemeinsam && <span className="bereich-satz">{b.satz.text}</span>}
              </Link>
            ))}
          </div>
          {leerGemeinsam && <p className="regal-hinweis">{leerGemeinsam}</p>}
        </section>
      )}

      {kommtNoch.length > 0 && (
        <section className="regal regal-spaeter" aria-labelledby="regal-spaeter">
          <h2 id="regal-spaeter" className="regal-titel">Kommt noch</h2>
          <ul className="spaeter-liste">
            {kommtNoch.map((b) => (
              <li key={b.schluessel} title={b.satz.text}>
                {b.name}
                {stufeAus(b) && <span className="spaeter-stufe">Stufe {stufeAus(b)}</span>}
                {/* Wartet ein Bereich nicht auf eine Stufe, sondern auf etwas
                    anderes (Filme & Medien auf den Schluessel zu medien), steht
                    der Grund da und nicht nur im Tooltip. */}
                {!stufeAus(b) && <span className="spaeter-satz">{b.satz.text}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <Link to="/plaetze" className="bereich-nebenweg">
        <Icon name="kiste" className="knopf-icon" />
        Plätze: Räume, Regale, Kisten und Etiketten
      </Link>
      <Link to="/shopfloor" className="bereich-nebenweg">
        <Icon name="lupe" className="knopf-icon" />
        Shopfloor: eingebucht, noch nicht eingelagert
      </Link>
      <Link to="/einkaufsliste" className="bereich-nebenweg">
        <Icon name="wagen" className="knopf-icon" />
        Einkaufsliste (eigene App)
      </Link>
    </div>
  );
}
