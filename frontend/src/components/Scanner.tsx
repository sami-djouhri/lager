import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from 'react';
import { fotoAusVideo } from '../fotos';

/* Der Scanner der beiden Laeufe (Vorbild medien `scannerOeffnen`).

   Er bleibt offen, solange der Lauf geht: Scan um Scan, die letzte Quittung
   steht darunter (`children`). Zwei Leser: `BarcodeDetector`, wo der Browser
   ihn hat (Chrome auf Android), sonst zxing aus dem eigenen Haus
   (`/vendor/zxing.min.js`, erst beim Oeffnen geladen).

   Die Kamera gibt der Browser nur in einem sicheren Kontext frei, also ueber
   `https://lager.home.arpa`. Ueber eine IP-Adresse passiert sonst wortlos
   nichts; deshalb steht das dann als Satz da, und das Eintippen geht immer.

   Derselbe Code zweimal hintereinander innerhalb von drei Sekunden zaehlt
   einmal: die Kamera sieht dasselbe Etikett zehnmal je Sekunde. */

export interface ScannerGriff {
  /** Ein Foto aus dem laufenden Kamerastrom. */
  foto: () => Promise<Blob>;
}

interface Props {
  offen: boolean;
  titel: string;
  /** Kurzer Stand ueber dem Bild, etwa „Ziel: Keller › Regal A". */
  stand?: ReactNode;
  onCode: (code: string) => void;
  onSchliessen: () => void;
  /** Waehrend einer Rueckfrage oder Anfrage werden Scans ignoriert. */
  gesperrt?: boolean;
  children?: ReactNode;
}

type ZXingLeser = { decodeFromConstraints: (c: unknown, v: HTMLVideoElement, f: (r: { getText: () => string } | null) => void) => Promise<unknown>; reset: () => void };

// `ideal`, nicht `exact`: eine Kamera ohne 1080p liefert dann ihr Bestes
// statt eines Fehlers. Die Aufloesung ist fuer das Foto da.
const KAMERA = { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } };
const FORMATE = ['ean_13', 'ean_8', 'upc_a', 'qr_code', 'code_128'];

function zxingLaden(): Promise<void> {
  const w = window as unknown as { ZXing?: unknown };
  if (w.ZXing) return Promise.resolve();
  return new Promise((ok, fehler) => {
    const s = document.createElement('script');
    s.src = '/vendor/zxing.min.js';
    s.onload = () => ok();
    s.onerror = () => fehler(new Error('Scanner-Bibliothek nicht ladbar'));
    document.head.appendChild(s);
  });
}

const Scanner = forwardRef<ScannerGriff, Props>(function Scanner(
  { offen, titel, stand, onCode, onSchliessen, gesperrt = false, children },
  griff,
) {
  const video = useRef<HTMLVideoElement>(null);
  const [hinweis, setHinweis] = useState('');
  const [eingabe, setEingabe] = useState('');
  const melden = useRef(onCode);
  const sperre = useRef(gesperrt);
  const zuletzt = useRef({ code: '', zeit: 0 });
  melden.current = onCode;
  sperre.current = gesperrt;

  useImperativeHandle(griff, () => ({ foto: () => fotoAusVideo(video.current) }), []);

  useEffect(() => {
    if (!offen) return;
    let strom: MediaStream | null = null;
    let uhr: number | undefined;
    let leser: ZXingLeser | null = null;
    let vorbei = false;

    const erkannt = (roh: string) => {
      const code = roh.trim();
      const jetzt = Date.now();
      if (!code || sperre.current) return;
      if (code === zuletzt.current.code && jetzt - zuletzt.current.zeit < 3000) return;
      zuletzt.current = { code, zeit: jetzt };
      melden.current(code);
    };

    (async () => {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setHinweis('Die Kamera gibt der Browser nur über https://lager.home.arpa frei. Hier den Code eintippen.');
        return;
      }
      setHinweis('Etikett oder Strichcode vor die Kamera halten.');
      try {
        const v = video.current!;
        const Detektor = (window as unknown as { BarcodeDetector?: new (o: unknown) => { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> } }).BarcodeDetector;
        if (Detektor) {
          strom = await navigator.mediaDevices.getUserMedia({ video: KAMERA, audio: false });
          if (vorbei) return;
          v.srcObject = strom;
          await v.play();
          const det = new Detektor({ formats: FORMATE });
          uhr = window.setInterval(async () => {
            try {
              const f = await det.detect(v);
              if (f[0]) erkannt(f[0].rawValue);
            } catch {
              /* Bild noch nicht bereit */
            }
          }, 250);
        } else {
          await zxingLaden();
          if (vorbei) return;
          const ZX = (window as unknown as { ZXing: { BrowserMultiFormatReader: new () => ZXingLeser } }).ZXing;
          leser = new ZX.BrowserMultiFormatReader();
          await leser.decodeFromConstraints({ video: KAMERA }, v, (r) => {
            if (r) erkannt(r.getText());
          });
        }
      } catch (e) {
        setHinweis(`Kamera nicht verfügbar (${e instanceof Error ? e.message : String(e)}). Eintippen geht immer.`);
      }
    })();

    return () => {
      vorbei = true;
      window.clearInterval(uhr);
      try { leser?.reset(); } catch { /* egal */ }
      strom?.getTracks().forEach((t) => t.stop());
      const v = video.current;
      if (v?.srcObject instanceof MediaStream) v.srcObject.getTracks().forEach((t) => t.stop());
      if (v) v.srcObject = null;
    };
  }, [offen]);

  if (!offen) return null;

  return (
    <div className="scanner-buehne" role="dialog" aria-modal="true" aria-label={titel}>
      <div className="scanner-kopf">
        <span className="scanner-titel">{titel}</span>
        <button type="button" className="btn btn-sm btn-secondary" onClick={onSchliessen}>
          Fertig
        </button>
      </div>
      {stand && <div className="scanner-stand">{stand}</div>}
      <div className="scanner-bild">
        <video ref={video} playsInline muted />
      </div>
      <p className="scanner-hinweis">{hinweis}</p>
      <form
        className="barcode-manual-row"
        onSubmit={(e) => {
          e.preventDefault();
          const code = eingabe.trim();
          setEingabe('');
          if (code && !sperre.current) melden.current(code);
        }}
      >
        <input
          className="form-input"
          value={eingabe}
          onChange={(e) => setEingabe(e.target.value)}
          placeholder="L-001, S-0001 oder Strichcode"
          autoComplete="off"
          aria-label="Code eintippen"
        />
        <button type="submit" className="btn btn-sm btn-secondary" disabled={!eingabe.trim() || gesperrt}>
          Los
        </button>
      </form>
      <div className="scanner-quittung">{children}</div>
    </div>
  );
});

export default Scanner;
