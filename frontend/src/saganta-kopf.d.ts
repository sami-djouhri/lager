/* ERZEUGT, NICHT VON HAND AENDERN (saganta/scripts/kopf-erzeugen.py).
 * Macht <saganta-kopf> in TSX bekannt. */
import type { DetailedHTMLProps, HTMLAttributes } from 'react';

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'saganta-kopf': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        /** Kennung aus apps.ts, z. B. "lager". */
        app: string;
        /** Abweichender Titel, sonst der Name aus dem Katalog. */
        titel?: string;
      };
    }
  }
}

export {};
