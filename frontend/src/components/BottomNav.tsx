import { NavLink, useLocation } from 'react-router-dom';
import Icon, { type IconName } from './Icon';
import { useBereiche, weg } from '../bereich/kontext';

/* Die Leiste haengt am Bereich: wer in der Hausapotheke steht, sieht deren
   Seiten und sonst nichts (Owner 2026-11-01: getrennt). Der erste Eintrag
   fuehrt immer zur Bereichswahl zurueck. Die Beschriftung laeuft schmal
   (font-stretch 88 in der CSS), nicht kleiner.

   Feste Plaetze ueber alle Bereiche: 1 Bereiche, 2 die Startseite des
   Bereichs, 3 der Hauptgriff (Einbuchen bzw. im Eingang Plaetze: Lagern).
   Einbuchen traegt ueberall das Plus, die Kamera gehoert dem Lagern. Vorher
   stand Einbuchen mal an vierter, mal an dritter Stelle, mal mit Plus, mal
   mit Kamera (Projectdeck 175). */

type Reiter = { to: string; icon: IconName; label: string; end?: boolean };

function reiterFuer(pfad: string, bauart: string | undefined): Reiter[] {
  const start: Reiter = { to: '/', icon: 'haus', label: 'Bereiche', end: true };
  const treffer = pfad.match(/^\/b\/([^/]+)/);
  if (!treffer) {
    return [
      start,
      { to: '/plaetze', icon: 'kiste', label: 'Plätze' },
      { to: '/lagern', icon: 'kamera', label: 'Lagern' },
      { to: '/shopfloor', icon: 'lupe', label: 'Shopfloor' },
      { to: '/einkaufsliste', icon: 'wagen', label: 'Einkauf' },
    ];
  }
  const b = treffer[1];
  if (bauart === 'stueck' || bauart === 'exemplar') {
    return [
      start,
      { to: weg(b), icon: 'geraet', label: bauart === 'exemplar' ? 'Filme' : 'Sachen', end: true },
      { to: weg(b, 'lauf'), icon: 'plus', label: 'Einbuchen' },
    ];
  }
  if (bauart === 'kiste') {
    return [start, { to: weg(b), icon: 'kiste', label: 'Kisten', end: true }];
  }
  return [
    start,
    { to: weg(b), icon: 'kiste', label: 'Übersicht', end: true },
    // „Einbuchen" fuehrt seit Stufe 4 in den Lauf; das Formular fuer einen
    // einzelnen Posten bleibt unter /einbuchen erreichbar (Link im Lauf), weil
    // mealprep und alte Lesezeichen dorthin zeigen.
    { to: weg(b, 'lauf'), icon: 'plus', label: 'Einbuchen' },
    { to: weg(b, 'bestand'), icon: 'lupe', label: 'Bestand' },
    { to: weg(b, 'produkte'), icon: 'teller', label: 'Produkte' },
  ];
}

export default function BottomNav() {
  const { pathname } = useLocation();
  const { bereiche } = useBereiche();
  const schluessel = pathname.match(/^\/b\/([^/]+)/)?.[1];
  const bauart = bereiche.find((b) => b.schluessel === schluessel)?.bauart;

  return (
    <nav className="bottom-nav">
      {reiterFuer(pathname, bauart).map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) => (isActive ? 'active' : '')}
        >
          <span className="nav-icon">
            <Icon name={t.icon} />
          </span>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
