import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { ProductOut, StockEntryCreate, BarcodeResult, ProductCreate, Page } from '../types';
import ProductSelect from '../components/ProductSelect';
import QuantityInput from '../components/QuantityInput';
import BarcodeInput from '../components/BarcodeInput';
import { fristName, useBereich, weg } from '../bereich/kontext';
import Kopf from '../bereich/Kopf';
import PlatzWahl from '../components/PlatzWahl';

export default function EinbuchenPage() {
  const navigate = useNavigate();
  const { schluessel, bereich } = useBereich();
  const [searchParams] = useSearchParams();
  const preselectedName = searchParams.get('product') ?? '';

  const [product, setProduct] = useState<ProductOut | null>(null);
  const [quantity, setQuantity] = useState<number>(0);
  const [unit, setUnit] = useState('g');
  const [mhd, setMhd] = useState('');
  const [platzId, setPlatzId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);
  const [barcodeResult, setBarcodeResult] = useState<BarcodeResult | null>(null);
  const [creatingProduct, setCreatingProduct] = useState(false);

  function handleSelectProduct(p: ProductOut) {
    setProduct(p);
    setUnit(p.default_unit);
    if (p.typical_pack_sizes.length > 0) {
      setQuantity(p.typical_pack_sizes[0]);
    }
    setBarcodeResult(null);
  }

  function handleBarcodeResult(result: BarcodeResult) {
    if (result.source === 'db' && result.product) {
      // Product exists in DB - load it as ProductOut
      api.get<Page<ProductOut>>(`/products?q=${encodeURIComponent(result.product.name)}&bereich=${encodeURIComponent(schluessel)}`)
        .then(({ items: products }) => {
          const match = products.find(p => p.barcode === result.product!.barcode);
          if (match) {
            handleSelectProduct(match);
          } else {
            setBarcodeResult(result);
          }
        })
        .catch(() => setBarcodeResult(result));
    } else {
      setBarcodeResult(result);
    }
  }

  async function handleCreateFromBarcode() {
    if (!barcodeResult?.product) return;
    setCreatingProduct(true);
    try {
      const body: ProductCreate = {
        name: barcodeResult.product.name,
        bereich: schluessel,
        barcode: barcodeResult.product.barcode,
        category: barcodeResult.product.category ?? undefined,
        default_unit: barcodeResult.product.default_unit ?? 'g',
        nutrition_per_100: barcodeResult.product.nutrition_per_100 ?? undefined,
        image_url: barcodeResult.product.image_url ?? undefined,
        typical_pack_sizes: barcodeResult.product.typical_pack_sizes ?? [],
        shelf_life_days_default: barcodeResult.product.shelf_life_days_default ?? undefined,
      };
      const created = await api.post<ProductOut>('/products', body);
      handleSelectProduct(created);
      setToast({ msg: `${created.name} angelegt`, type: 'success' });
      setTimeout(() => setToast(null), 2000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fehler beim Anlegen';
      setToast({ msg, type: 'error' });
      setTimeout(() => setToast(null), 3000);
    } finally {
      setCreatingProduct(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!product || quantity <= 0) return;

    setSubmitting(true);
    try {
      const body: StockEntryCreate = {
        product_id: product.id,
        quantity,
        unit,
        platz_id: platzId,
      };
      if (mhd) body.mhd = mhd;
      await api.post('/stock', body);
      setToast({ msg: `${product.name} eingebucht`, type: 'success' });
      setTimeout(() => {
        setToast(null);
        navigate(weg(schluessel, 'bestand'));
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fehler beim Einbuchen';
      setToast({ msg, type: 'error' });
      setTimeout(() => setToast(null), 3000);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <Kopf titel="Einbuchen" />

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Produkt</label>
          <ProductSelect
            bereich={schluessel}
            onSelect={handleSelectProduct}
            placeholder={preselectedName || 'Produkt suchen...'}
          />
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

        {/* Barcode result: OpenFoodFacts product not yet in DB */}
        {barcodeResult && barcodeResult.source === 'openfoodfacts' && barcodeResult.product && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="scanner-result-name">{barcodeResult.product.name}</div>
            <div className="scanner-result-detail">
              {barcodeResult.product.category && <span>{barcodeResult.product.category} &middot; </span>}
              Gefunden bei OpenFoodFacts
            </div>
            {barcodeResult.product.image_url && (
              <img
                src={barcodeResult.product.image_url}
                alt={barcodeResult.product.name}
                style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 8, marginBottom: 12 }}
              />
            )}
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleCreateFromBarcode}
              disabled={creatingProduct}
            >
              {creatingProduct ? 'Wird angelegt...' : 'Anlegen + Einbuchen'}
            </button>
          </div>
        )}

        {/* Barcode not found */}
        {barcodeResult && barcodeResult.source === null && (
          <div className="card" style={{ marginBottom: 16, background: 'var(--color-warning-light)' }}>
            Barcode nicht gefunden. Bitte Produkt manuell suchen oder anlegen.
          </div>
        )}

        {product && (
          <>
            <QuantityInput
              quantity={quantity}
              unit={unit}
              onQuantityChange={setQuantity}
              onUnitChange={setUnit}
              packSizes={product.typical_pack_sizes}
            />

            <div className="form-group" style={{ marginTop: 16 }}>
              <label className="form-label">{fristName(bereich)}</label>
              <input
                type="date"
                className="form-input"
                value={mhd}
                onChange={(e) => setMhd(e.target.value)}
              />
            </div>

            <PlatzWahl wert={platzId} onWahl={setPlatzId} />

            <button
              type="submit"
              className="btn btn-primary btn-block btn-lg"
              disabled={submitting || quantity <= 0}
            >
              {submitting ? 'Wird eingebucht...' : 'Einbuchen'}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
