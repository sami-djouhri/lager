/* Der Verfallsstrahl: das Kennzeichen dieses Dienstes.
 *
 * Vorher trug jede Zeile ein Schild mit dem Wort "Abgelaufen". Bei zwanzig
 * abgelaufenen Posten standen zwanzig gleiche rote Schilder untereinander,
 * und die Zahl, die entscheidet, welcher zuerst drankommt, wurde nicht
 * gezeigt: `days_left` kam vom Server und landete im Wort.
 *
 * Hier sitzt der Posten statt dessen auf einer kurzen Achse. Der senkrechte
 * Strich ist HEUTE. Links davon ist die Haltbarkeit vorbei, rechts steht sie
 * aus, und der Abstand sagt, wie weit. Zwei Tage sehen anders aus als vierzig.
 *
 * Zwei Dinge, die hier bewusst so sind:
 *
 * HEUTE sitzt bei 38 Prozent, nicht in der Mitte. Nach hinten reicht die
 * Skala weiter als nach vorn: Haltbarkeiten laufen ueber Monate, abgelaufen
 * ist etwas selten laenger als ein paar Wochen, bevor es weggeworfen wird.
 *
 * Die Skala ist logarithmisch. Linear waeren 3 Tage und 5 Tage nicht
 * unterscheidbar, sobald ein Posten mit 180 Tagen Haltbarkeit in derselben
 * Liste steht. Der Unterschied zwischen 3 und 5 Tagen ist aber genau der,
 * auf den es ankommt.
 */

interface Props {
  daysLeft: number | null;
  urgency?: string;
}

/* Wo HEUTE auf dem Strahl liegt, in Prozent. */
const HEUTE = 38;
/* Wie weit die Skala in jede Richtung reicht, in Tagen.
   Ein Jahr in beide Richtungen. Die erste Fassung reichte 60 Tage zurueck;
   im echten Bestand standen Posten, die seit ueber 200 Tagen abgelaufen
   waren, und die klemmten alle am linken Anschlag. Der Strahl unterschied
   dann nichts mehr, also genau das, wofuer er gebaut ist. */
const RUECKWAERTS = 365;
const VORWAERTS = 365;

function stufe(urgency: string | undefined, daysLeft: number | null): string {
  if (urgency) return urgency;
  if (daysLeft === null) return 'unbekannt';
  if (daysLeft <= 0) return 'abgelaufen';
  if (daysLeft <= 2) return 'kritisch';
  if (daysLeft <= 7) return 'bald';
  return 'ok';
}

/* Gestauchte Skala: nah an HEUTE fein, weit weg grob. */
function gestaucht(tage: number, spanne: number): number {
  const x = Math.min(Math.abs(tage), spanne);
  return Math.log1p(x) / Math.log1p(spanne);
}

function position(daysLeft: number | null): number {
  if (daysLeft === null) return HEUTE;
  if (daysLeft <= 0) return HEUTE - HEUTE * gestaucht(daysLeft, RUECKWAERTS);
  return HEUTE + (100 - HEUTE) * gestaucht(daysLeft, VORWAERTS);
}

/* Die Einheit waechst mit dem Abstand. "seit 215 T" muss man umrechnen,
   bevor es etwas bedeutet; "seit 7 Mon" versteht man sofort. Tage bleiben
   dort, wo sie zaehlen, also in den ersten Wochen. */
function spanne(tage: number): string {
  if (tage < 90) return `${tage} T`;
  if (tage < 365) return `${Math.round(tage / 30)} Mon`;
  const jahre = tage / 365;
  return jahre < 2 ? '1 J' : `${Math.floor(jahre)} J`;
}

export function beschriftung(daysLeft: number | null): string {
  if (daysLeft === null) return 'ohne MHD';
  if (daysLeft === 0) return 'heute';
  if (daysLeft < 0) return `seit ${spanne(Math.abs(daysLeft))}`;
  return `in ${spanne(daysLeft)}`;
}

/* Fuer Vorleseprogramme ausgeschrieben: "seit 7 Mon" ist gesprochen nutzlos. */
export function vorgelesen(daysLeft: number | null): string {
  if (daysLeft === null) return 'Kein Mindesthaltbarkeitsdatum hinterlegt';
  if (daysLeft === 0) return 'Läuft heute ab';
  if (daysLeft < 0) {
    const d = Math.abs(daysLeft);
    return `Abgelaufen seit ${d} ${d === 1 ? 'Tag' : 'Tagen'}`;
  }
  return `Haltbar noch ${daysLeft} ${daysLeft === 1 ? 'Tag' : 'Tage'}`;
}

export default function Verfall({ daysLeft, urgency }: Props) {
  const s = stufe(urgency, daysLeft);
  const links = position(daysLeft);

  return (
    <div className="verfall" title={vorgelesen(daysLeft)}>
      <div className="verfall-strahl" role="img" aria-label={vorgelesen(daysLeft)}>
        <span className="verfall-heute" />
        <span
          className={`verfall-punkt ${s}`}
          style={s === 'unbekannt' ? undefined : { left: `${links}%` }}
        />
      </div>
      <span className={`verfall-text ${s}`} aria-hidden="true">
        {beschriftung(daysLeft)}
      </span>
    </div>
  );
}
