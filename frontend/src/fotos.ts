import type { ElectronicAssetOut } from './types';

/* Fotos an Sachen (Vorbild medien). Der Browser verkleinert auf 1600 px
   Kante und schickt JPEG: ein Handybild hat 12 MB, und die wandern sonst
   alle durchs WLAN, nur damit der Dienst sie wegwirft. Der Dienst nimmt
   ohnehin nur JPEG an (geprueft an den Magic-Bytes). */

const KANTE = 1600;
const GUETE = 0.82;

/* Der Dateiname haengt als `v` an der Adresse, obwohl der Server ihn nicht
   liest: die Route ist konstant und darf lange im Cache liegen, und ohne den
   wechselnden Teil zeigte der Browser nach einem neuen Foto das alte. */
export function fotoUrl(s: Pick<ElectronicAssetOut, 'id' | 'foto'> | null | undefined): string | null {
  return s && s.foto ? `/api/sachen/${s.id}/foto?v=${encodeURIComponent(s.foto)}` : null;
}

function verkleinern(quelle: CanvasImageSource, breite: number, hoehe: number): HTMLCanvasElement {
  const faktor = Math.min(1, KANTE / Math.max(breite, hoehe));
  const leinwand = document.createElement('canvas');
  leinwand.width = Math.max(1, Math.round(breite * faktor));
  leinwand.height = Math.max(1, Math.round(hoehe * faktor));
  leinwand.getContext('2d')!.drawImage(quelle, 0, 0, leinwand.width, leinwand.height);
  return leinwand;
}

function alsJpeg(leinwand: HTMLCanvasElement): Promise<Blob> {
  return new Promise((fertig, fehler) =>
    leinwand.toBlob(
      (b) => (b ? fertig(b) : fehler(new Error('Bild ließ sich nicht umwandeln'))),
      'image/jpeg',
      GUETE,
    ),
  );
}

/** Ein Bild aus dem laufenden Kamerastrom, ohne den Scanner zu verlassen. */
export function fotoAusVideo(video: HTMLVideoElement | null): Promise<Blob> {
  if (!video || !video.videoWidth) {
    return Promise.reject(new Error('Die Kamera läuft nicht. Foto später an der Sache nachtragen.'));
  }
  return alsJpeg(verkleinern(video, video.videoWidth, video.videoHeight));
}

export async function fotoAusDatei(datei: File): Promise<Blob> {
  const bild = await createImageBitmap(datei);
  try {
    return await alsJpeg(verkleinern(bild, bild.width, bild.height));
  } finally {
    bild.close();
  }
}

/** Dateiauswahl, auf dem Telefon direkt die Kamera. */
export function fotoAuswaehlen(): Promise<Blob> {
  return new Promise((fertig, fehler) => {
    const feld = document.createElement('input');
    feld.type = 'file';
    feld.accept = 'image/*';
    feld.setAttribute('capture', 'environment');
    // Ohne `cancel` bliebe das Versprechen nach einem Abbruch fuer immer offen.
    feld.addEventListener('cancel', () => fehler(new Error('Kein Bild gewählt')));
    feld.addEventListener('change', async () => {
      const datei = feld.files?.[0];
      if (!datei) {
        fehler(new Error('Kein Bild gewählt'));
        return;
      }
      try {
        fertig(await fotoAusDatei(datei));
      } catch (e) {
        fehler(e);
      }
    });
    feld.click();
  });
}

export async function fotoSenden(sacheId: number, bild: Blob): Promise<ElectronicAssetOut> {
  let res: Response;
  try {
    res = await fetch(`/api/sachen/${sacheId}/foto`, {
      method: 'POST',
      headers: { 'Content-Type': 'image/jpeg' },
      body: bild,
    });
  } catch {
    throw new Error('Keine Verbindung zum Server');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error ?? `Foto nicht gespeichert (HTTP ${res.status})`);
  }
  return res.json();
}
