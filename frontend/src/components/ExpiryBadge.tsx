/* Die knappe Form der Haltbarkeit, fuer enge Listen.
 *
 * Wo Platz ist, steht statt dessen der Verfallsstrahl (siehe Verfall.tsx),
 * der die Frist auch als Abstand zeigt. Hier reicht die Zahl, aber sie
 * spricht dieselbe Sprache: "seit 3 Mon" ist vorbei, "in 12 T" steht aus.
 * Vorher stand in beiden Faellen nur ein Wort ("Abgelaufen" / "12 Tage"),
 * und die Richtung musste man aus der Farbe raten.
 *
 * Beschriftung und Vorlesetext kommen aus Verfall.tsx, damit die beiden
 * Darstellungen nicht auseinanderlaufen koennen.
 */

import { beschriftung, vorgelesen } from './Verfall';

interface Props {
  daysLeft: number | null;
  urgency?: string;
}

function stufe(daysLeft: number | null): string {
  if (daysLeft === null) return 'ok';
  if (daysLeft <= 0) return 'abgelaufen';
  if (daysLeft <= 2) return 'kritisch';
  if (daysLeft <= 7) return 'bald';
  return 'ok';
}

export default function ExpiryBadge({ daysLeft, urgency }: Props) {
  const u = urgency ?? stufe(daysLeft);
  return (
    <span className={`expiry-badge ${u}`} title={vorgelesen(daysLeft)}>
      {beschriftung(daysLeft)}
    </span>
  );
}
