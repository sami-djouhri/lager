import { useState, useEffect } from 'react';
import { api, fehlertext } from '../api';
import type { ProductOut, ProductCreate, ProductUpdate, Page } from '../types';
import LoadError from '../components/LoadError';

const CATEGORIES = [
  'Alle', 'Getreide', 'Milchprodukte', 'Fleisch', 'Gemüse', 'Obst',
  'Gewürze', 'Öle', 'Getränke', 'Konserven', 'Sonstiges',
];

const UNITS = [
  { value: 'g', label: 'Gramm (g)' },
  { value: 'ml', label: 'Milliliter (ml)' },
  { value: 'piece', label: 'Stück' },
];

export default function ProduktePage() {
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('Alle');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<ProductOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<ProductCreate>({ name: '' });
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function loadProducts() {
    setLoadError(null);
    try {
      const params = new URLSearchParams({ limit: '500' });
      if (category !== 'Alle') params.set('category', category);
      if (search) params.set('q', search);
      const data = await api.get<Page<ProductOut>>(`/products?${params}`);
      setProducts(data.items);
    } catch (err) {
      setLoadError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, search]);

  function startCreate() {
    setEditing(null);
    setCreating(true);
    setForm({ name: '', default_unit: 'g', category: undefined });
  }

  function startEdit(p: ProductOut) {
    setCreating(false);
    setEditing(p);
    setForm({
      name: p.name,
      barcode: p.barcode,
      category: p.category,
      default_unit: p.default_unit,
      typical_pack_sizes: p.typical_pack_sizes,
      shelf_life_days_default: p.shelf_life_days_default,
      image_url: p.image_url,
      min_stock: p.min_stock,
      min_stock_unit: p.min_stock_unit,
    });
  }

  function cancelEdit() {
    setEditing(null);
    setCreating(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name) return;

    try {
      if (creating) {
        await api.post('/products', form);
        showToast('Produkt angelegt', 'success');
      } else if (editing) {
        const update: ProductUpdate = { ...form };
        await api.put(`/products/${editing.id}`, update);
        showToast('Produkt aktualisiert', 'success');
      }
      cancelEdit();
      setLoading(true);
      loadProducts();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fehler';
      showToast(msg, 'error');
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Produkt wirklich löschen?')) return;
    try {
      await api.del(`/products/${id}`);
      showToast('Produkt gelöscht', 'success');
      cancelEdit();
      setLoading(true);
      loadProducts();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fehler beim Löschen';
      showToast(msg, 'error');
    }
  }

  function showToast(msg: string, type: string) {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2500);
  }

  const showForm = creating || editing;

  return (
    <div className="page">
      <h1 className="page-title">Produkte</h1>

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

      <div className="form-group">
        <input
          type="text"
          className="form-input"
          placeholder="Produkt suchen..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setLoading(true); }}
        />
      </div>

      <div className="filter-chips">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            className={`chip${category === cat ? ' active' : ''}`}
            onClick={() => { setCategory(cat); setLoading(true); }}
          >
            {cat}
          </button>
        ))}
      </div>

      {showForm && (
        <form className="inline-form" onSubmit={handleSave}>
          <div className="inline-form-title">
            {creating ? 'Neues Produkt' : `${editing!.name} bearbeiten`}
          </div>

          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              type="text"
              className="form-input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Barcode</label>
            <input
              type="text"
              className="form-input"
              value={form.barcode ?? ''}
              onChange={(e) => setForm({ ...form, barcode: e.target.value || null })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Kategorie</label>
            <select
              className="form-select"
              value={form.category ?? ''}
              onChange={(e) => setForm({ ...form, category: e.target.value || undefined })}
            >
              <option value="">-- Keine --</option>
              {CATEGORIES.filter((c) => c !== 'Alle').map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Standard-Einheit</label>
            <select
              className="form-select"
              value={form.default_unit ?? 'g'}
              onChange={(e) => setForm({ ...form, default_unit: e.target.value })}
            >
              {UNITS.map((u) => (
                <option key={u.value} value={u.value}>{u.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Haltbarkeit (Tage)</label>
            <input
              type="number"
              className="form-input"
              value={form.shelf_life_days_default ?? ''}
              onChange={(e) =>
                setForm({ ...form, shelf_life_days_default: e.target.value ? Number(e.target.value) : null })
              }
            />
          </div>

          <div className="form-group">
            <label className="form-label">Mindestbestand</label>
            <div className="quantity-row">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="number"
                  className="form-input"
                  placeholder="z.B. 500"
                  step="any"
                  min="0"
                  value={form.min_stock ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, min_stock: e.target.value ? Number(e.target.value) : null })
                  }
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <select
                  className="form-select"
                  value={form.min_stock_unit ?? form.default_unit ?? 'g'}
                  onChange={(e) => setForm({ ...form, min_stock_unit: e.target.value })}
                >
                  {UNITS.map((u) => (
                    <option key={u.value} value={u.value}>{u.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="inline-form-actions">
            <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
              Speichern
            </button>
            {editing && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => handleDelete(editing.id)}
              >
                Löschen
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
              Abbrechen
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="loading">Laden...</div>
      ) : loadError ? (
        <LoadError was="Die Produktliste" fehler={loadError} onRetry={loadProducts} />
      ) : products.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">{'\u{1F50D}'}</div>
          <div className="empty-state-text">Keine Produkte gefunden</div>
        </div>
      ) : (
        products.map((p) => (
          <div key={p.id} className="product-item" onClick={() => startEdit(p)}>
            <div className="product-item-info">
              <div className="product-item-name">{p.name}</div>
              <div className="product-item-meta">
                {p.category && <span>{p.category} &middot; </span>}
                {p.default_unit}
                {p.barcode && <span> &middot; {p.barcode}</span>}
              </div>
            </div>
          </div>
        ))
      )}

      {!showForm && (
        <button className="fab" onClick={startCreate} title="Neues Produkt">
          +
        </button>
      )}
    </div>
  );
}
