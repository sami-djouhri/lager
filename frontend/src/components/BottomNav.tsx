import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/', icon: '\u2302', label: 'Start' },
  { to: '/bestand', icon: '\u{1F4E6}', label: 'Bestand' },
  { to: '/einkaufsliste', icon: '\u{1F6D2}', label: 'Einkauf' },
  { to: '/einbuchen', icon: '\u2795', label: 'Einbuchen' },
  { to: '/produkte', icon: '\u{1F50D}', label: 'Produkte' },
  { to: '/wertsachen', icon: '\u{1F4BB}', label: 'Wertsachen' },
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
          <span className="nav-icon">{t.icon}</span>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
