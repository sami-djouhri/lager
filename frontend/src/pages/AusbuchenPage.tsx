import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { ProductOut, AvailabilityOut, ConsumeRequest, BarcodeResult, Page } from '../types';
import ProductSelect from '../components/ProductSelect';
import BarcodeInput from '../components/BarcodeInput';

const REASONS = [
  { value: 'verbraucht', label: 'Verbraucht' },
  { value: 'weggeworfen', label: 'Weggeworfen' },
  { value: 'abgelaufen', label: 'Abgelaufen' },
];

const UNIT_LABELS: Record<string, string> = { g: 'g', ml: 'ml', piece: 'Stk' };

export default function AusbuchenPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preProductId = searchParams.get('product_id');

  const [product, setProduct] = useState<ProductOut | null>(null);
  const [availability, setAvailability] = useState<AvailabilityOut | null>(null);
  const [amount, setAmount] = useState<number>(0);
  const [reason, setReason] = useState('verbraucht');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);

  // Load preselected product
  useEffect(() => {
    if (preProductId) {
      api
        .get<ProductOut>(`/products/${preProductId}`)
        .then((p) => setProduct(p))
        .catch(() => {});
    }
  }, [preProductId]);

  // Load availability when product changes
  useEffect(() => {
    if (!product) {
      setAvailability(null);
      return;
    }
    api
      .get<AvailabilityOut>(
        `/stock/available?product_id=${product.id}&unit=${product.default_unit}`,
      )
      .then(setAvailability)
      .catch(() => setAvailability(null));
  }, [product]);

  function handleSelectProduct(p: ProductOut) {
    setProduct(p);
    setAmount(0);
  }

  function handleBarcodeResult(result: BarcodeResult) {
    if (result.source === 'db' && result.product) {
      // Product exists in DB - load it
      api.get<Page<ProductOut>>(`/products?q=${encodeURIComponent(result.product.name)}`)
        .then(({ items: products }) => {
          const match = products.find(p => p.barcode === result.product!.barcode);
          if (match) {
            handleSelectProduct(match);
          } else {
            setToast({ msg: 'Produkt nicht im Lager gefunden', type: 'error' });
            setTimeout(() => setToast(null), 3000);
          }
        })
        .catch(() => {
          setToast({ msg: 'Fehler beim Laden des Produkts', type: 'error' });
          setTimeout(() => setToast(null), 3000);
        });
    } else if (result.source === 'openfoodfacts') {
      setToast({ msg: 'Produkt nicht im Lager. Zuerst einbuchen.', type: 'error' });
      setTimeout(() => setToast(null), 3000);
    } else {
      setToast({ msg: 'Barcode nicht gefunden', type: 'error' });
      setTimeout(() => setToast(null), 3000);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!product || amount <= 0) return;

    setSubmitting(true);
    try {
      const body: ConsumeRequest = {
        product_id: product.id,
        amount,
        unit: product.default_unit,
        reason,
        source: 'manual',
      };
      await api.post('/stock/consume', body);
      setToast({ msg: `${amount} ${UNIT_LABELS[product.default_unit] ?? product.default_unit} ${product.name} ausgebucht`, type: 'success' });
      setTimeout(() => {
        setToast(null);
        navigate('/bestand');
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fehler beim Ausbuchen';
      setToast({ msg, type: 'error' });
      setTimeout(() => setToast(null), 3000);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Ausbuchen</h1>

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Produkt</label>
          <ProductSelect onSelect={handleSelectProduct} />
          <div style={{ marginTop: 8 }}>
            <BarcodeInput
              onResult={handleBarcodeResult}
              onError={(msg) => {
                setToast({ msg, type: 'error' });
                setTimeout(() => setToast(null), 3000);
              }}
            />
          </div>
        </div>

        {product && (
          <>
            {availability && (
              <div className="availability">
                Verfügbar:{' '}
                <span className="availability-value">
                  {availability.total} {UNIT_LABELS[availability.unit] ?? availability.unit}
                </span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">
                Menge ({UNIT_LABELS[product.default_unit] ?? product.default_unit})
              </label>
              <input
                type="number"
                className="form-input"
                value={amount || ''}
                onChange={(e) => setAmount(Number(e.target.value))}
                min={0}
                step="any"
                inputMode="decimal"
                max={availability?.total}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Grund</label>
              <div className="reason-selector">
                {REASONS.map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    className={`reason-btn${reason === r.value ? ' active' : ''}`}
                    onClick={() => setReason(r.value)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block btn-lg"
              disabled={submitting || amount <= 0}
            >
              {submitting ? 'Wird ausgebucht...' : 'Ausbuchen'}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
