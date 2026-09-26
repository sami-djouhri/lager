import { Routes, Route, Navigate } from 'react-router-dom';
import BottomNav from './components/BottomNav';
import DashboardPage from './pages/DashboardPage';
import BestandPage from './pages/BestandPage';
import EinbuchenPage from './pages/EinbuchenPage';
import AusbuchenPage from './pages/AusbuchenPage';
import ProduktePage from './pages/ProduktePage';
import StatistikPage from './pages/StatistikPage';
import EinkaufslistePage from './pages/EinkaufslistePage';
import WertsachenPage from './pages/WertsachenPage';

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/bestand" element={<BestandPage />} />
        <Route path="/einbuchen" element={<EinbuchenPage />} />
        <Route path="/ausbuchen" element={<AusbuchenPage />} />
        <Route path="/scanner" element={<Navigate to="/einbuchen" replace />} />
        <Route path="/produkte" element={<ProduktePage />} />
        <Route path="/statistik" element={<StatistikPage />} />
        <Route path="/einkaufsliste" element={<EinkaufslistePage />} />
        <Route path="/wertsachen" element={<WertsachenPage />} />
        {/* Ohne Catch-all rendert eine unbekannte URL nur die Navigation,
            also eine leere Seite ohne Hinweis, was los ist. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomNav />
    </>
  );
}
