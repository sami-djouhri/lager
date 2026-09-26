interface Props {
  daysLeft: number | null;
  urgency?: string;
}

function getUrgency(daysLeft: number | null): string {
  if (daysLeft === null) return 'ok';
  if (daysLeft <= 0) return 'abgelaufen';
  if (daysLeft <= 2) return 'kritisch';
  if (daysLeft <= 7) return 'bald';
  return 'ok';
}

function getLabel(urgency: string, daysLeft: number | null): string {
  if (urgency === 'abgelaufen') return 'Abgelaufen';
  if (urgency === 'kritisch') return daysLeft === 1 ? '1 Tag' : `${daysLeft} Tage`;
  if (urgency === 'bald') return `${daysLeft} Tage`;
  if (daysLeft === null) return 'Kein MHD';
  return `${daysLeft} Tage`;
}

export default function ExpiryBadge({ daysLeft, urgency }: Props) {
  const u = urgency ?? getUrgency(daysLeft);
  const label = getLabel(u, daysLeft);
  return <span className={`expiry-badge ${u}`}>{label}</span>;
}
