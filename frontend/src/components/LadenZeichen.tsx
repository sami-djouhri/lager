/* Laden-Logo fuer den Preisvergleich (Owner 2026-11-07).

   Die Liste spiegelt app/ketten.py. `logo` ist das SVG aus laeden/
   (Wikimedia Commons, Owner 2026-11-07: echte Logos). Netto und Akzenta sind
   das Original-SVG unveraendert in einem Quadrat mit Kettenfarbe, sonst waeren
   sie klein unlesbar bzw. im dunklen Thema unsichtbar. Ohne Datei: Kuerzel.
   Gleiche Datei in einkaufsliste/frontend/src/LadenZeichen.tsx. */

import kaufland from './laeden/kaufland.svg';
import lidl from './laeden/lidl.svg';
import netto from './laeden/netto.svg';
import akzenta from './laeden/akzenta.svg';
import picnic from './laeden/picnic.svg';

export const KETTEN = [
  { schluessel: 'kaufland', name: 'Kaufland', kurz: 'K', logo: kaufland as string | null },
  { schluessel: 'lidl', name: 'Lidl', kurz: 'L', logo: lidl as string | null },
  { schluessel: 'netto', name: 'Netto', kurz: 'N', logo: netto as string | null },
  { schluessel: 'akzenta', name: 'Akzenta', kurz: 'A', logo: akzenta as string | null },
  { schluessel: 'picnic', name: 'Picnic', kurz: 'P', logo: picnic as string | null },
] as const;

export type Kette = (typeof KETTEN)[number]['schluessel'];

export default function LadenZeichen({ kette, gross = false }: { kette: string; gross?: boolean }) {
  const k = KETTEN.find((x) => x.schluessel === kette);
  if (!k) return null;
  const klasse = `laden-zeichen laden-${k.schluessel}${gross ? ' gross' : ''}`;
  if (k.logo) return <img className={klasse} src={k.logo} alt={k.name} title={k.name} />;
  return <span className={klasse} role="img" aria-label={k.name} title={k.name}>{k.kurz}</span>;
}
