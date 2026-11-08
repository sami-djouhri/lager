import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { BereichOut } from '../types';

/* Die Bereiche kommen vom Server (`app/bereiche.py`), samt Satz je Kachel.
   Hier steht bewusst keine zweite Liste: eine Kopie im Browser veraltet still,
   sobald der Server einen Bereich oeffnet. */

interface Stand {
  bereiche: BereichOut[];
  fehler: string | null;
  laedt: boolean;
  neuLaden: () => void;
}

const Kontext = createContext<Stand>({
  bereiche: [],
  fehler: null,
  laedt: true,
  neuLaden: () => {},
});

export function BereicheProvider({ children }: { children: ReactNode }) {
  const [bereiche, setBereiche] = useState<BereichOut[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);

  const neuLaden = useCallback(async () => {
    setFehler(null);
    try {
      setBereiche(await api.get<BereichOut[]>('/bereiche'));
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => {
    neuLaden();
  }, [neuLaden]);

  return (
    <Kontext.Provider value={{ bereiche, fehler, laedt, neuLaden }}>{children}</Kontext.Provider>
  );
}

export function useBereiche(): Stand {
  return useContext(Kontext);
}

/** Der Bereich aus der Adresse (`/b/:bereich/...`), solange die Liste laedt `null`. */
export function useBereich(): { schluessel: string; bereich: BereichOut | null } {
  const { bereich: schluessel = 'lebensmittel' } = useParams();
  const { bereiche } = useBereiche();
  return { schluessel, bereich: bereiche.find((b) => b.schluessel === schluessel) ?? null };
}

/** Adresse einer Seite im Bereich, z. B. `weg('apotheke', 'bestand')`. */
export function weg(bereich: string, seite = ''): string {
  return seite ? `/b/${bereich}/${seite}` : `/b/${bereich}`;
}

/** Wie die Frist im Bereich heisst; ohne eigene Frist das neutrale „Haltbar bis". */
export function fristName(bereich: BereichOut | null): string {
  return bereich?.frist ?? 'Haltbar bis';
}
