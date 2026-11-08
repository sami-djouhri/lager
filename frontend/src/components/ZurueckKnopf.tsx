import { useEffect, useState } from 'react';

/* Eine Quittungszeile zuruecknehmen (Fehlscan). Zwei Griffe: der erste fragt,
   der zweite nimmt zurueck. Ein einzelner Griff mit dem Daumen beim Scannen
   haette sonst ein richtig gebuchtes Ding wieder geloescht. Nach vier Sekunden
   ohne zweiten Griff steht der Knopf wieder auf Anfang. */
export default function ZurueckKnopf({ onZurueck, gesperrt }: { onZurueck: () => void; gesperrt?: boolean }) {
  const [fragt, setFragt] = useState(false);

  useEffect(() => {
    if (!fragt) return;
    const t = window.setTimeout(() => setFragt(false), 4000);
    return () => window.clearTimeout(t);
  }, [fragt]);

  return (
    <button
      type="button"
      className={fragt ? 'lauf-zurueck fragt' : 'lauf-zurueck'}
      disabled={gesperrt}
      onClick={() => {
        if (fragt) {
          setFragt(false);
          onZurueck();
        } else {
          setFragt(true);
        }
      }}
    >
      {fragt ? 'Wirklich zurücknehmen?' : 'Zurücknehmen'}
    </button>
  );
}
