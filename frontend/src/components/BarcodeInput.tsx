import { useState, useEffect, useRef, useCallback } from 'react';
import { api, fehlertext } from '../api';
import type { BarcodeResult } from '../types';
import Icon from './Icon';

interface Props {
  onResult: (result: BarcodeResult) => void;
  onError?: (msg: string) => void;
}

/** Check if camera API is available (requires secure context). */
function canUseCamera(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

export default function BarcodeInput({ onResult, onError }: Props) {
  const [mode, setMode] = useState<'idle' | 'camera' | 'manual'>('idle');
  const [manualCode, setManualCode] = useState('');
  const [looking, setLooking] = useState(false);
  const scannerRef = useRef<{ stop: () => Promise<void> } | null>(null);
  const regionId = useRef(`scan-${Math.random().toString(36).slice(2, 8)}`);

  const stopCamera = useCallback(async () => {
    if (scannerRef.current) {
      try { await scannerRef.current.stop(); } catch { /* ignore */ }
      scannerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => { stopCamera(); };
  }, [stopCamera]);

  async function lookupBarcode(code: string) {
    setLooking(true);
    try {
      const data = await api.get<BarcodeResult>(`/barcode/${encodeURIComponent(code)}`);
      onResult(data);
    } catch (err) {
      // Frueher wurde hier ein leeres Ergebnis gemeldet: ein fehlgeschlagener
      // Lookup sah dann aus wie "Barcode unbekannt". Der Nutzer haette den
      // Artikel von Hand angelegt, obwohl er laengst im Bestand ist.
      onError?.(`Barcode-Suche fehlgeschlagen: ${fehlertext(err)}`);
    } finally {
      setLooking(false);
    }
  }

  async function startCamera() {
    setMode('camera');
    // Wait for DOM to have the region element
    await new Promise((r) => setTimeout(r, 100));

    try {
      const { Html5Qrcode } = await import('html5-qrcode');
      const s = new Html5Qrcode(regionId.current);
      scannerRef.current = s as unknown as typeof scannerRef.current;

      await s.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 150 } },
        async (decodedText: string) => {
          await s.stop();
          scannerRef.current = null;
          setMode('idle');
          lookupBarcode(decodedText);
        },
        () => {},
      );
    } catch (err) {
      console.error('Scanner error:', err);
      onError?.('Kamera konnte nicht gestartet werden. Bitte Berechtigung prüfen.');
      setMode('idle');
    }
  }

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    const code = manualCode.trim();
    if (!code) return;
    setMode('idle');
    lookupBarcode(code);
  }

  function handleScanClick() {
    if (canUseCamera()) {
      startCamera();
    } else {
      setMode('manual');
    }
  }

  return (
    <div className="barcode-input">
      {mode === 'idle' && !looking && (
        <div className="barcode-buttons">
          <button type="button" className="btn btn-sm btn-secondary" onClick={handleScanClick}>
            <Icon name={canUseCamera() ? 'kamera' : 'lupe'} className="knopf-icon" />
            {canUseCamera() ? 'Barcode scannen' : 'Barcode eingeben'}
          </button>
          {canUseCamera() && (
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => setMode('manual')}>
              Manuell eingeben
            </button>
          )}
        </div>
      )}

      {looking && (
        <div className="barcode-looking">Barcode wird gesucht...</div>
      )}

      {mode === 'camera' && (
        <div className="barcode-camera">
          <div className="scanner-wrapper">
            <div id={regionId.current} />
          </div>
          <button type="button" className="btn btn-sm btn-secondary btn-block" onClick={async () => { await stopCamera(); setMode('idle'); }}>
            Abbrechen
          </button>
        </div>
      )}

      {mode === 'manual' && (
        <form className="barcode-manual" onSubmit={handleManualSubmit}>
          <div className="barcode-manual-row">
            <input
              type="text"
              className="form-input"
              placeholder="Barcode eingeben (z.B. 4000521003753)"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              autoFocus
              inputMode="numeric"
              pattern="[0-9]*"
            />
            <button type="submit" className="btn btn-sm btn-primary" disabled={!manualCode.trim()}>
              Suchen
            </button>
          </div>
          <button type="button" className="btn btn-sm btn-secondary" style={{ marginTop: 8 }} onClick={() => { setMode('idle'); setManualCode(''); }}>
            Abbrechen
          </button>
        </form>
      )}
    </div>
  );
}
