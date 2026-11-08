interface Props {
  label: string;
  value: number;
  max: number;
  unit?: string;
}

export default function StatBar({ label, value, max, unit = '' }: Props) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  // Eine Nachkommastelle, deutsch: `Math.round` machte aus 0,4 l eine 0.
  const zahl = value.toLocaleString('de-DE', { maximumFractionDigits: 1 });
  const display = unit ? `${zahl} ${unit}` : zahl;

  return (
    <div className="stat-bar-container">
      <div className="stat-bar-label">
        <span className="stat-bar-label-name">{label}</span>
        <span className="stat-bar-label-value">{display}</span>
      </div>
      <div className="stat-bar-track">
        <div className="stat-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
