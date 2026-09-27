import { NavLink } from 'react-router-dom';
import Icon, { type IconName } from './Icon';

/* Sechs Reiter auf einer Handybreite sind eng. Die Beschriftung laeuft
   deshalb schmal (font-stretch 88 in der CSS), nicht kleiner: kleiner Text
   wird unlesbar, schmaler Text bleibt lesbar und braucht weniger Platz. */
const tabs: { to: string; icon: IconName; label: string }[] = [
  { to: '/', icon: 'haus', label: 'Start' },
  { to: '/bestand', icon: 'kiste', label: 'Bestand' },
  { to: '/einkaufsliste', icon: 'wagen', label: 'Einkauf' },
  { to: '/einbuchen', icon: 'plus', label: 'Einbuchen' },
  { to: '/produkte', icon: 'lupe', label: 'Produkte' },
  { to: '/wertsachen', icon: 'geraet', label: 'Wertsachen' },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.to === '/'}
          className={({ isActive }) => (isActive ? 'active' : '')}
        >
          <span className="nav-icon">
            <Icon name={t.icon} />
          </span>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
