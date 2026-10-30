interface Props {
  quantity: number | string;
  unit: string;
  onQuantityChange: (v: number) => void;
  onUnitChange: (v: string) => void;
  packSizes?: number[];
}

const UNITS = ['g', 'ml', 'piece'];
const UNIT_LABELS: Record<string, string> = { g: 'g', ml: 'ml', piece: 'Stk' };

export default function QuantityInput({
  quantity,
  unit,
  onQuantityChange,
  onUnitChange,
  packSizes = [],
}: Props) {
  return (
    <div>
      <div className="quantity-row">
        <div className="form-group">
          <label className="form-label">Menge</label>
          <input
            type="number"
            className="form-input"
            value={quantity}
            onChange={(e) => onQuantityChange(Number(e.target.value))}
            min={0}
            step="any"
            inputMode="decimal"
          />
        </div>
        <div className="form-group">
          <label className="form-label">Einheit</label>
          <select
            className="form-select"
            value={unit}
            onChange={(e) => onUnitChange(e.target.value)}
          >
            {UNITS.map((u) => (
              <option key={u} value={u}>
                {UNIT_LABELS[u]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {packSizes.length > 0 && (
        <div className="pack-sizes">
          {packSizes.map((size) => (
            <button
              key={size}
              type="button"
              className={`pack-size-btn${Number(quantity) === size ? ' active' : ''}`}
              onClick={() => onQuantityChange(size)}
            >
              {size} {UNIT_LABELS[unit] ?? unit}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
