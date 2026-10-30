/* Strichsymbole fuer die Bedienung.
 *
 * Vorher standen hier Emoji im Text (Kiste, Einkaufswagen, Lupe, Laptop).
 * Drei Gruende, warum sie weg sind: sie sehen auf jedem Geraet anders aus
 * (Apple zeichnet anders als Android als Windows), sie bringen eine fremde
 * Farbigkeit in ein Blatt, das sonst nur Zustandsfarben traegt, und sie
 * lassen sich nicht auf die Strichstaerke der Schrift abstimmen.
 *
 * Alle Symbole teilen dieselbe Bauart: 24er Raster, nur Striche, 1.6 breit,
 * runde Enden. Sie erben die Textfarbe.
 */

interface Props {
  name: IconName;
  className?: string;
}

export type IconName =
  | 'haus'
  | 'kiste'
  | 'wagen'
  | 'plus'
  | 'minus'
  | 'lupe'
  | 'geraet'
  | 'balken'
  | 'kamera'
  | 'teller'
  | 'erneuern';

const pfade: Record<IconName, JSX.Element> = {
  haus: (
    <>
      <path d="M3.5 10.2 12 3.6l8.5 6.6" />
      <path d="M5.5 9v10.4h13V9" />
      <path d="M9.8 19.4v-5.6h4.4v5.6" />
    </>
  ),
  kiste: (
    <>
      <path d="M3.4 7.6 12 3.4l8.6 4.2v8.8L12 20.6l-8.6-4.2z" />
      <path d="M3.4 7.6 12 11.9l8.6-4.3" />
      <path d="M12 11.9v8.7" />
    </>
  ),
  wagen: (
    <>
      <path d="M2.8 3.9h2.5l2.4 10.3h9.6" />
      <path d="M5.9 6.7h15L18.8 12H7.2" />
      <circle cx="9.2" cy="18.6" r="1.5" />
      <circle cx="16.6" cy="18.6" r="1.5" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5.2v13.6" />
      <path d="M5.2 12h13.6" />
    </>
  ),
  minus: <path d="M5.2 12h13.6" />,
  lupe: (
    <>
      <circle cx="10.8" cy="10.8" r="6.4" />
      <path d="M15.5 15.5 20.4 20.4" />
    </>
  ),
  geraet: (
    <>
      <rect x="3.4" y="4.6" width="17.2" height="11.3" rx="1.4" />
      <path d="M2 19.4h20" />
    </>
  ),
  balken: (
    <>
      <path d="M4.4 20V12.6" />
      <path d="M9.5 20V6.2" />
      <path d="M14.5 20v-9.4" />
      <path d="M19.6 20V8.6" />
    </>
  ),
  kamera: (
    <>
      <path d="M3.4 7.9h3.4l1.5-2.3h7.4l1.5 2.3h3.4v10.5H3.4z" />
      <circle cx="12" cy="13" r="3.4" />
    </>
  ),
  teller: (
    <>
      <circle cx="12" cy="12" r="8.2" />
      <circle cx="12" cy="12" r="4.4" />
    </>
  ),
  erneuern: (
    <>
      <path d="M20.2 12a8.2 8.2 0 1 1-2.5-5.9" />
      <path d="M20.4 4.2v4.6h-4.6" />
    </>
  ),
};

export default function Icon({ name, className }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {pfade[name]}
    </svg>
  );
}
