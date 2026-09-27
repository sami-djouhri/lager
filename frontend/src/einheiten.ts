/* Einheiten und Orte in der Sprache, in der die App spricht.
 *
 * Die Zuordnung lag bisher nur in StockCard. Ueberall sonst wurde der rohe
 * Wert aus der Datenbank gezeigt, und auf dem Dashboard stand deshalb
 * "10 piece" statt "10 Stk". Ein Ort fuer die Uebersetzung, damit das nicht
 * je Seite neu entschieden wird.
 */

const EINHEITEN: Record<string, string> = {
  g: 'g',
  ml: 'ml',
  piece: 'Stk',
  pieces: 'Stk',
  stk: 'Stk',
};

export function einheit(wert: string | null | undefined): string {
  if (!wert) return '';
  return EINHEITEN[wert.toLowerCase()] ?? wert;
}

/* Menge und Einheit als ein Stueck, damit der Zwischenraum ueberall gleich
   ist und nicht mal mit, mal ohne Leerzeichen gesetzt wird. */
export function menge(wert: number, roheEinheit: string | null | undefined): string {
  return `${wert} ${einheit(roheEinheit)}`.trim();
}
