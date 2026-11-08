import { Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import BottomNav from './components/BottomNav';
import { BereicheProvider, useBereich } from './bereich/kontext';
import StartPage from './pages/StartPage';
import DashboardPage from './pages/DashboardPage';
import BestandPage from './pages/BestandPage';
import EinbuchenPage from './pages/EinbuchenPage';
import AusbuchenPage from './pages/AusbuchenPage';
import ProduktePage from './pages/ProduktePage';
import StatistikPage from './pages/StatistikPage';
import EinkaufslistePage from './pages/EinkaufslistePage';
import WertsachenPage from './pages/WertsachenPage';
import KistenPage from './pages/KistenPage';
import PlaetzePage from './pages/PlaetzePage';
import PlatzPage from './pages/PlatzPage';
import ShopfloorPage from './pages/ShopfloorPage';
import LaufPage from './pages/LaufPage';
import LagernPage from './pages/LagernPage';

/* Adressen sind zweistufig: `/b/<bereich>/<seite>` (Vorbild medien). Die
   Vorrats-Bereiche teilen sich dieselben Seiten, jede filtert auf den Bereich
   aus der Adresse; Technik & Sachen hat seine eigene. */

/** Die alten, einstufigen Adressen tragen Lesezeichen und die Saganta-Shell. */
function AlterWeg({ nach }: { nach: string }) {
  const { search } = useLocation();
  return <Navigate to={nach + search} replace />;
}

/** Die Einkaufsliste ist seit 2026-11-01 eine eigene App (Entscheid,
    docker/einkaufsliste). Unter einem saganta-Namen geht es dorthin; am
    Direktport im LAN gibt es keinen Geschwisternamen, dann bleibt die alte
    Vorschlagsseite stehen, statt ins Leere zu fuehren. */
// Zurueckgehalten bis die App laeuft (Stand 2026-11-01: kein Container,
// kein Vhost): sonst fuehrte /einkaufsliste unter dem saganta-Namen ins Leere.
const EINKAUFSLISTE_LIVE = false;

function ZurEinkaufsliste() {
  const host = window.location.hostname;
  if (EINKAUFSLISTE_LIVE && host.includes('saganta')) {
    window.location.replace(`${window.location.protocol}//${host.replace(/^[^.]+\./, 'einkaufsliste.')}/`);
    return null;
  }
  return <EinkaufslistePage />;
}

/** Einstieg in einen Bereich: Vorrat = Uebersicht, Stueck = Sachen-Liste, Kiste = Kisten. */
function BereichStart() {
  const { bereich } = useBereich();
  if (bereich && !bereich.bereit) return <Navigate to="/" replace />;
  if (bereich?.bauart === 'stueck' || bereich?.bauart === 'exemplar') return <WertsachenPage />;
  if (bereich?.bauart === 'kiste') return <KistenPage />;
  return <DashboardPage />;
}

/** Der Einbuch-Lauf gibt es fuer Vorraete und Sachen (Stufe 4), nicht fuer Kisten. */
function NurLauf({ children }: { children: JSX.Element }) {
  const { bereich } = useBereich();
  const { bereich: schluessel } = useParams();
  if (bereich && (!bereich.bereit || !['vorrat', 'stueck', 'exemplar'].includes(bereich.bauart))) {
    return <Navigate to={`/b/${schluessel}`} replace />;
  }
  return children;
}

/** Vorrats-Seiten nur in Vorrats-Bereichen; sonst zurueck in den Bereich. */
function NurVorrat({ children }: { children: JSX.Element }) {
  const { bereich } = useBereich();
  const { bereich: schluessel } = useParams();
  if (bereich && bereich.bauart !== 'vorrat') return <Navigate to={`/b/${schluessel}`} replace />;
  return children;
}

export default function App() {
  return (
    <BereicheProvider>
      <saganta-kopf app="lager"></saganta-kopf>
      <Routes>
        <Route path="/" element={<StartPage />} />
        <Route path="/einkaufsliste" element={<ZurEinkaufsliste />} />
        <Route path="/plaetze" element={<PlaetzePage />} />
        <Route path="/plaetze/:id" element={<PlatzPage />} />
        <Route path="/shopfloor" element={<ShopfloorPage />} />
        <Route path="/lagern" element={<LagernPage />} />
        <Route path="/b/:bereich" element={<BereichStart />} />
        <Route path="/b/:bereich/lauf" element={<NurLauf><LaufPage /></NurLauf>} />
        <Route path="/b/:bereich/bestand" element={<NurVorrat><BestandPage /></NurVorrat>} />
        <Route path="/b/:bereich/einbuchen" element={<NurVorrat><EinbuchenPage /></NurVorrat>} />
        <Route path="/b/:bereich/ausbuchen" element={<NurVorrat><AusbuchenPage /></NurVorrat>} />
        <Route path="/b/:bereich/produkte" element={<NurVorrat><ProduktePage /></NurVorrat>} />
        <Route path="/b/:bereich/statistik" element={<NurVorrat><StatistikPage /></NurVorrat>} />

        <Route path="/bestand" element={<AlterWeg nach="/b/lebensmittel/bestand" />} />
        <Route path="/einbuchen" element={<AlterWeg nach="/b/lebensmittel/einbuchen" />} />
        <Route path="/scanner" element={<AlterWeg nach="/b/lebensmittel/einbuchen" />} />
        <Route path="/ausbuchen" element={<AlterWeg nach="/b/lebensmittel/ausbuchen" />} />
        <Route path="/produkte" element={<AlterWeg nach="/b/lebensmittel/produkte" />} />
        <Route path="/statistik" element={<AlterWeg nach="/b/lebensmittel/statistik" />} />
        <Route path="/wertsachen" element={<AlterWeg nach="/b/technik" />} />
        {/* Ohne Catch-all rendert eine unbekannte URL nur die Navigation,
            also eine leere Seite ohne Hinweis, was los ist. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomNav />
    </BereicheProvider>
  );
}
