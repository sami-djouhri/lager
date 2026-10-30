import { useEffect, useState } from 'react';
import { api } from '../api';
import type { MealPlanRequest, MealPlanResponse, RecipeOut } from '../types';

interface Props {
  onClose: () => void;
  onPlanned?: () => void;
}

const UNIT_LABELS: Record<string, string> = { g: 'g', ml: 'ml', piece: 'Stk' };

export default function MealPlanModal({ onClose, onPlanned }: Props) {
  const [recipes, setRecipes] = useState<RecipeOut[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [servings, setServings] = useState(2);
  const [plan, setPlan] = useState<MealPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<RecipeOut[]>('/recipes')
      .then((rows) => setRecipes(rows))
      .catch((err) => setError(err.message || 'Rezepte konnten nicht geladen werden'))
      .finally(() => setLoading(false));
  }, []);

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  async function calculate() {
    if (selected.size === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const body: MealPlanRequest = { recipe_ids: [...selected], servings };
      const resp = await api.post<MealPlanResponse>('/meal-plan', body);
      setPlan(resp);
      onPlanned?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Fehler bei Berechnung');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Mahlzeit planen</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {error && <div className="toast error" style={{ position: 'static', marginBottom: 12 }}>{error}</div>}

          {loading ? (
            <div className="loading">Rezepte laden...</div>
          ) : recipes.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-text">Keine Rezepte verfügbar</div>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Rezepte</label>
                {recipes.map((r) => (
                  <label
                    key={r.id}
                    className="autocomplete-item"
                    style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(r.id)}
                      onChange={() => toggle(r.id)}
                    />
                    <span>{r.name}</span>
                    <span className="autocomplete-item-sub">
                      {r.ingredients.length} Zutaten
                    </span>
                  </label>
                ))}
              </div>

              <div className="form-group">
                <label className="form-label">Portionen</label>
                <input
                  type="number"
                  className="form-input"
                  min={1}
                  max={20}
                  value={servings}
                  onChange={(e) => setServings(Math.max(1, Number(e.target.value)))}
                />
              </div>

              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={calculate}
                disabled={submitting || selected.size === 0}
              >
                {submitting ? 'Berechne...' : 'Einkaufsliste berechnen'}
              </button>
            </>
          )}

          {plan && (
            <div style={{ marginTop: 16 }}>
              <h3>Einkaufsliste</h3>
              {plan.shopping_list.length === 0 ? (
                <div className="empty-state-text">
                  Alles im Bestand: nichts einzukaufen.
                </div>
              ) : (
                plan.shopping_list.map((item) => (
                  <div key={item.product_id} className="low-stock-item">
                    <div className="low-stock-item-info">
                      <span className="low-stock-item-name">{item.product_name}</span>
                      <span className="low-stock-item-detail">
                        Benötigt: {item.needed} {UNIT_LABELS[item.unit] ?? item.unit} ·
                        Vorhanden: {item.available} {UNIT_LABELS[item.unit] ?? item.unit} ·
                        <strong> Fehlt: {item.missing} {UNIT_LABELS[item.unit] ?? item.unit}</strong>
                      </span>
                    </div>
                  </div>
                ))
              )}

              {plan.missing_stock.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>Unbekannte Produkte</h3>
                  {plan.missing_stock.map((m, i) => (
                    <div key={i} className="low-stock-item">
                      <div className="low-stock-item-info">
                        <span className="low-stock-item-name">{m.product_name}</span>
                        <span className="low-stock-item-detail">
                          {m.needed} {UNIT_LABELS[m.unit] ?? m.unit}, noch nicht im Katalog
                        </span>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
