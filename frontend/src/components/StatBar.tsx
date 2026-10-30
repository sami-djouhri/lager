interface Props {
  label: string;
  value: number;
  max: number;
  unit?: string;
}

export default function StatBar({ label, value, max, unit = '' }: Props) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const display = unit ? `${Math.round(value)} ${unit}` : String(Math.round(value));

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
