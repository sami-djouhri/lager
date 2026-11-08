import { api } from './api';
import type { ElectronicAssetOut, PlatzOut } from './types';

/* Plaetze im Browser: Namen der Arten, Shopfloor-Gruende, Etiketten.
   Die Regeln (wer in wem stehen darf, Kennung) stehen im Server,
   `app/services/plaetze.py`; hier steht nur, was die Oberflaeche anzeigt. */

export const ART_NAMEN: Record<string, string> = {
  raum: 'Raum',
  regal: 'Regal',
  fach: 'Fach',
  kiste: 'Kiste',
};

/** Was unter einer Art angelegt werden kann (gleiche Regel wie der Server). */
export const KINDER_ARTEN: Record<string, string[]> = {
  raum: ['regal', 'kiste'],
  regal: ['fach'],
  fach: ['kiste'],
  kiste: [],
};

export const GRUND_NAMEN: Record<string, string> = {
  im_einsatz: 'Im Einsatz',
  reparatur: 'In Reparatur',
  verkauf_vorbereiten: 'Verkauf vorbereiten',
  rippen: 'Rippen',
  schauen: 'Schauen',
};

/** Eine Zustandsskala fuer alle Sachen (Owner 2026-11-01), wie `models.ZUSTAENDE`. */
export const ZUSTAENDE = ['Neu', 'Sehr gut', 'Gut', 'Gebraucht', 'Beschädigt', 'Ungeprüft'];

/** Wie in medien (`felder.MEDIEN`, `felder.MEDIENTYPEN`), die Werte, die dort zaehlen. */
export const MEDIEN = ['DVD', 'Blu-ray', '4K UHD', 'Box', 'CD', 'Vinyl', 'Buch', 'Spiel-Disc', 'Spiel-Modul'];
export const MEDIENTYPEN = ['Film', 'Serie', 'Dokumentation', 'Musik', 'Buch', 'Spiel', 'Sonstige'];

export async function ladePlaetze(): Promise<PlatzOut[]> {
  return api.get<PlatzOut[]>('/plaetze');
}

/* Die QR-Bibliothek ist dieselbe Datei wie in medien (public/vendor), im
   Haus und erst beim Drucken geladen: die Startseite braucht sie nie. */
type QrFabrik = (typ: number, stufe: string) => {
  addData: (d: string) => void;
  make: () => void;
  createSvgTag: (o: { cellSize: number; margin: number; scalable: boolean }) => string;
};

function ladeQr(): Promise<QrFabrik> {
  const vorhanden = (window as unknown as { qrcode?: QrFabrik }).qrcode;
  if (vorhanden) return Promise.resolve(vorhanden);
  return new Promise((fertig, fehler) => {
    const s = document.createElement('script');
    s.src = '/vendor/qrcode.js';
    s.onload = () => {
      const q = (window as unknown as { qrcode?: QrFabrik }).qrcode;
      if (q) fertig(q);
      else fehler(new Error('QR-Bibliothek nicht geladen'));
    };
    s.onerror = () => fehler(new Error('QR-Bibliothek nicht geladen'));
    document.head.appendChild(s);
  });
}

function esc(t: string): string {
  return t.replace(/[&<>"]/g, (z) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[z]!);
}

interface Etikett {
  kennung: string;
  name: string;
  zeile: string;
}

/**
 * Etikettenbogen in einem neuen Fenster, Bogenmass wie in medien (3 × 34 mm).
 *
 * Der QR-Code traegt nur die Kennung (`L-001`, `S-0001`), keine Adresse: der
 * Scanner erkennt am Praefix, was vor der Kamera war, und eine Adresse im Code
 * waere nach einem Umzug des Dienstes ein totes Etikett.
 */
async function bogenDrucken(etiketten: Etikett[]): Promise<void> {
  if (!etiketten.length) throw new Error('Nichts ausgewählt');
  // Fenster zuerst, sonst blockiert der Browser es nach dem await als Pop-up.
  const fenster = window.open('', '_blank');
  if (!fenster) throw new Error('Pop-up blockiert, bitte erlauben');
  const qrcode = await ladeQr();
  const html = etiketten
    .map((e) => {
      const qr = qrcode(0, 'M');
      qr.addData(e.kennung);
      qr.make();
      return `<div class="e">${qr.createSvgTag({ cellSize: 2, margin: 0, scalable: true })}
        <div><b>${esc(e.kennung)}</b><span>${esc(e.name)}</span><i>${esc(e.zeile)}</i></div></div>`;
    })
    .join('');
  fenster.document.write(`<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Etiketten</title><style>
    @page { size: A4; margin: 10mm 7mm; }
    body { margin: 0; font: 9pt system-ui, sans-serif; color: #000; background: #fff; }
    .bogen { display: grid; grid-template-columns: repeat(3, 1fr); grid-auto-rows: 34mm; }
    .e { display: grid; grid-template-columns: 26mm 1fr; gap: 3mm; align-items: center; padding: 2mm 3mm; border: .2mm dashed #bbb; overflow: hidden; break-inside: avoid; }
    .e svg { width: 26mm; height: 26mm; }
    .e b { display: block; font-size: 14pt; letter-spacing: .02em; }
    .e span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: 10pt; }
    .e i { display: block; color: #444; font-size: 8pt; font-style: normal; margin-top: 1mm; }
    @media print { .hinweis { display: none; } .e { border-color: #eee; } }
    .hinweis { padding: 8px; font: 13px system-ui; background: #ffd; }
  </style></head><body><div class="hinweis">${etiketten.length} Etiketten · Drucken mit Strg+P (100 %, ohne Ränder anpassen)</div><div class="bogen">${html}</div></body></html>`);
  fenster.document.close();
}

export function etikettenDrucken(plaetze: PlatzOut[]): Promise<void> {
  if (!plaetze.length) return Promise.reject(new Error('Keine Plätze ausgewählt'));
  return bogenDrucken(plaetze.map((p) => ({
    kennung: p.kennung,
    name: p.name,
    zeile: [ART_NAMEN[p.art], p.pfad.split(' › ').slice(0, -1).join(' › ')].filter(Boolean).join(' · '),
  })));
}

/** Stueck-Etiketten. Gedruckt nur fuer Sachen ohne Strichcode (Owner, wie medien):
    wo die Packung einen traegt, unterscheidet bei Doppelten der Zustand. */
export function sachEtikettenDrucken(sachen: ElectronicAssetOut[]): Promise<void> {
  if (!sachen.length) return Promise.reject(new Error('Keine Sachen ohne Strichcode'));
  return bogenDrucken(sachen.map((s) => ({
    kennung: s.kennung ?? '',
    name: s.name,
    zeile: [s.brand, s.model].filter(Boolean).join(' · ') || (s.platz_pfad ?? ''),
  })));
}
