/* ERZEUGT, NICHT VON HAND AENDERN.
 *
 * Quellen: saganta/packages/ui/src/apps.ts, packages/ui/src/components/Icon.svelte,
 * packages/design-tokens/src/theme.css (Pruefsumme 5ad910388c5e)
 * Werkzeug: saganta/scripts/kopf-erzeugen.py --schreiben
 *
 * Der Saganta-Kopf fuer Dienste ausserhalb der SvelteKit-Suite, Gegenstueck
 * zu TopBar.svelte: App-Wechsler, Wortmarke "Saganta /" (fuehrt zur
 * Uebersicht), Sinnbild in Messing, App-Name, Platz fuer Aktionen
 * (slot="aktionen"), darunter das 2-px-Band mit der Signatur der App.
 *
 *   <saganta-kopf app="lager"></saganta-kopf>
 *
 * Unter einem Namen ohne Domain (Direktport, LAN-IP, localhost) gibt es keine
 * Geschwister-Adressen: dann entfallen Wechsler und Link, statt ins Leere zu
 * zeigen. Eine Aenderung hier meldet der Waechter als Abweichung.
 */
(() => {
  if (customElements.get('saganta-kopf')) return;

  const APPS = [
  {
    "id": "shell",
    "name": "Übersicht",
    "beschreibung": "Launchpad: alle Apps auf einen Blick.",
    "icon": "layout-grid",
    "sub": "",
    "subHeim": "shell",
    "nurHeim": false,
    "signatur": "linear-gradient(currentColor, currentColor)"
  },
  {
    "id": "calendar",
    "name": "Kalender",
    "beschreibung": "Termine, Tagestypen, Gewohnheiten.",
    "icon": "calendar",
    "sub": "kalender",
    "subHeim": "calendar",
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 13px)"
  },
  {
    "id": "aufgaben",
    "name": "Aufgaben",
    "beschreibung": "Aufgaben, Tagesziele und der geplante Tag. Verknüpft mit Projekten und Notizen.",
    "icon": "list-todo",
    "sub": "aufgaben",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 7px, transparent 7px 12px)"
  },
  {
    "id": "kontakte",
    "name": "Kontakte",
    "beschreibung": "Menschen mit Telefon, Mail, Adresse, Geburtstag und Jahrestagen. Verknüpft mit Terminen und Notizen.",
    "icon": "users",
    "sub": "kontakte",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 5px, currentColor 5px 8px, transparent 8px 16px)"
  },
  {
    "id": "notizen",
    "name": "Notizen",
    "beschreibung": "Notizbücher, Anhänge, geteilte Notizen.",
    "icon": "file-text",
    "sub": "notizen",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 15px, transparent 15px 18px)"
  },
  {
    "id": "post",
    "name": "Post",
    "beschreibung": "E-Mails und Briefe in einer Inbox. Konten, Briefkasten, Verträge und Fristen.",
    "icon": "inbox",
    "sub": "post",
    "subHeim": null,
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 5px)"
  },
  {
    "id": "news",
    "name": "News",
    "beschreibung": "Nachrichtenquellen und das persönliche Briefing.",
    "icon": "newspaper",
    "sub": "news",
    "subHeim": null,
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 30px, transparent 30px 40px)"
  },
  {
    "id": "projectdeck",
    "name": "ProjectDeck",
    "beschreibung": "Projekte, Entscheidungen, Portfolio.",
    "icon": "layout-dashboard",
    "sub": "projectdeck",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 20px, transparent 20px 26px, currentColor 26px 29px, transparent 29px 35px)"
  },
  {
    "id": "tagebuch",
    "name": "Tagebuch",
    "beschreibung": "Tageseinträge, im Browser verschlüsselt. Nur im Heimnetz.",
    "icon": "book",
    "sub": "tagebuch",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 1px, transparent 1px 15px)"
  },
  {
    "id": "fitness",
    "name": "Fitness",
    "beschreibung": "Trainingspläne und erfasste Sätze.",
    "icon": "dumbbell",
    "sub": "fitness",
    "subHeim": null,
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 16px, transparent 16px 20px, currentColor 20px 24px, transparent 24px 34px)"
  },
  {
    "id": "mealprep",
    "name": "MealPrep",
    "beschreibung": "Rezepte und Wochenplanung.",
    "icon": "utensils",
    "sub": "mealprep",
    "subHeim": null,
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 5px, transparent 5px 8px, currentColor 8px 13px, transparent 13px 24px)"
  },
  {
    "id": "lager",
    "name": "Lager",
    "beschreibung": "Vorräte, Haushalt, Technik und Sachen.",
    "icon": "archive",
    "sub": "lager",
    "subHeim": null,
    "nurHeim": false,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 11px, transparent 11px 22px)"
  },
  {
    "id": "einkaufsliste",
    "name": "Einkaufsliste",
    "beschreibung": "Was fehlt, von selbst aus Vorrat und Essensplan.",
    "icon": "shopping-cart",
    "sub": "einkaufsliste",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 14px, transparent 14px 18px, currentColor 18px 26px, transparent 26px 30px, currentColor 30px 34px, transparent 34px 44px)"
  },
  {
    "id": "finanzen",
    "name": "Finanzen",
    "beschreibung": "Konten, Prognose, Budgets und Depot.",
    "icon": "trending-up",
    "sub": "finanzen",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 6px, currentColor 6px 9px, transparent 9px 22px)"
  },
  {
    "id": "medien",
    "name": "Medien",
    "beschreibung": "Filme, Serien, Bücher, Spiele und Musik: Bestand, Verkauf, Bewertung.",
    "icon": "library",
    "sub": "medien",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 5px, currentColor 5px 6px, transparent 6px 8px, currentColor 8px 12px, transparent 12px 22px)"
  },
  {
    "id": "wissen",
    "name": "Wissen",
    "beschreibung": "Eine Suche über das Offline-Wissen: Wiki, Bücher, Dokumente, Anleitungen.",
    "icon": "lightbulb",
    "sub": "wissen",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 8px, transparent 8px 10px, currentColor 10px 12px, transparent 12px 20px)"
  },
  {
    "id": "bibliothek",
    "name": "Bibliothek",
    "beschreibung": "Die Hausbibliothek zum Lesen, mit Lesestand und Notizen.",
    "icon": "book-open",
    "sub": "bibliothek",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 24px, transparent 24px 30px, currentColor 30px 40px, transparent 40px 46px)"
  },
  {
    "id": "karten",
    "name": "Karten",
    "beschreibung": "Offline-Karten mit Suche, Routen und Bus und Bahn.",
    "icon": "map",
    "sub": "karten",
    "subHeim": null,
    "nurHeim": true,
    "signatur": "repeating-linear-gradient(90deg, currentColor 0 12px, transparent 12px 16px, currentColor 16px 17px, transparent 17px 21px)"
  }
];

  const SYMBOLE = {
  "archive": "<rect width=\"20\" height=\"5\" x=\"2\" y=\"3\" rx=\"1\"/><path d=\"M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8\"/><path d=\"M10 12h4\"/>",
  "book": "<path d=\"M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20\"/>",
  "book-open": "<path d=\"M12 7v14\"/><path d=\"M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z\"/>",
  "calendar": "<path d=\"M8 2v4\"/><path d=\"M16 2v4\"/><rect width=\"18\" height=\"18\" x=\"3\" y=\"4\" rx=\"2\"/><path d=\"M3 10h18\"/>",
  "dumbbell": "<path d=\"M14.4 14.4 9.6 9.6\"/><path d=\"M18.657 21.485a2 2 0 1 1-2.829-2.828l-1.767 1.768a2 2 0 1 1-2.829-2.829l6.364-6.364a2 2 0 1 1 2.829 2.829l-1.768 1.767a2 2 0 1 1 2.828 2.829z\"/><path d=\"m21.5 21.5-1.4-1.4\"/><path d=\"M3.9 3.9 2.5 2.5\"/><path d=\"M6.404 12.768a2 2 0 1 1-2.829-2.829l1.768-1.767a2 2 0 1 1-2.828-2.829l2.828-2.828a2 2 0 1 1 2.829 2.828l1.767-1.768a2 2 0 1 1 2.829 2.829z\"/>",
  "file-text": "<path d=\"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z\"/><path d=\"M14 2v4a2 2 0 0 0 2 2h4\"/><path d=\"M10 9H8\"/><path d=\"M16 13H8\"/><path d=\"M16 17H8\"/>",
  "inbox": "<polyline points=\"22 12 16 12 14 15 10 15 8 12 2 12\"/><path d=\"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z\"/>",
  "layout-dashboard": "<rect width=\"7\" height=\"9\" x=\"3\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"5\" x=\"14\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"9\" x=\"14\" y=\"12\" rx=\"1\"/><rect width=\"7\" height=\"5\" x=\"3\" y=\"16\" rx=\"1\"/>",
  "layout-grid": "<rect width=\"7\" height=\"7\" x=\"3\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"7\" x=\"14\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"7\" x=\"14\" y=\"14\" rx=\"1\"/><rect width=\"7\" height=\"7\" x=\"3\" y=\"14\" rx=\"1\"/>",
  "library": "<path d=\"m16 6 4 14\"/><path d=\"M12 6v14\"/><path d=\"M8 8v12\"/><path d=\"M4 4v16\"/>",
  "lightbulb": "<path d=\"M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5\"/><path d=\"M9 18h6\"/><path d=\"M10 22h4\"/>",
  "list-todo": "<rect x=\"3\" y=\"5\" width=\"6\" height=\"6\" rx=\"1\"/><path d=\"m3 17 2 2 4-4\"/><path d=\"M13 6h8\"/><path d=\"M13 12h8\"/><path d=\"M13 18h8\"/>",
  "map": "<path d=\"M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z\"/><path d=\"M15 5.764v15\"/><path d=\"M9 3.236v15\"/>",
  "newspaper": "<path d=\"M15 18h-5\"/><path d=\"M18 14h-8\"/><path d=\"M21 3v18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2\"/><path d=\"M7 3h14a2 2 0 0 1 2 2v0\"/><rect width=\"8\" height=\"4\" x=\"10\" y=\"6\" rx=\"1\"/>",
  "shopping-cart": "<circle cx=\"8\" cy=\"21\" r=\"1\"/><circle cx=\"19\" cy=\"21\" r=\"1\"/><path d=\"M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12\"/>",
  "trending-up": "<polyline points=\"22 7 13.5 15.5 8.5 10.5 2 17\"/><polyline points=\"16 7 22 7 22 13\"/>",
  "users": "<path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\"/><circle cx=\"9\" cy=\"7\" r=\"4\"/><path d=\"M22 21v-2a4 4 0 0 0-3-3.87\"/><path d=\"M16 3.13a4 4 0 0 1 0 7.75\"/>",
  "utensils": "<path d=\"M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2\"/><path d=\"M7 2v20\"/><path d=\"M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7\"/>"
};

  const STIL = `
    :host {
      display: block;
      position: sticky;
      top: 0;
      z-index: 30;
      font-family: var(--saganta-schrift, 'Inter Variable', Inter, ui-sans-serif, system-ui, sans-serif);
      color: #f3ede2;
      background: rgb(22 19 15 / 0.8);
      -webkit-backdrop-filter: blur(12px);
      backdrop-filter: blur(12px);
    }
    * { box-sizing: border-box; }
    .zeile {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      height: 56px; padding: 0 12px;
      padding-left: max(12px, env(safe-area-inset-left));
      padding-right: max(12px, env(safe-area-inset-right));
    }
    .links { display: flex; align-items: center; gap: 6px; min-width: 0; }
    .rechts { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
    .marke {
      display: flex; align-items: center; gap: 8px; min-width: 0;
      color: inherit; text-decoration: none; border-radius: 6px;
    }
    .wort { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
    .trenner { color: #a69b8a; }
    .sinnbild { color: #dd9c3f; display: inline-flex; }
    .app { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .wechsler { position: relative; }
    .knopf {
      display: grid; place-items: center; width: 44px; height: 44px;
      background: none; border: 0; padding: 0; color: #a69b8a; cursor: pointer;
    }
    .knopf:hover { color: #f3ede2; }
    .knopf > span {
      display: grid; place-items: center; width: 32px; height: 32px;
      border: 1px solid #7c7264; border-radius: 6px;
    }
    .knopf:hover > span { background: #1f1b15; }
    a:focus-visible, button:focus-visible { outline: 2px solid #dd9c3f; outline-offset: 2px; }
    .tafel {
      position: absolute; left: 0; top: 100%; margin-top: 6px; z-index: 40;
      width: 18rem; max-width: calc(100vw - 24px);
      border: 1px solid #302920; border-radius: 12px; overflow: hidden;
      background: #1f1b15; box-shadow: 0 12px 32px rgb(0 0 0 / 0.45);
    }
    .tafel[hidden] { display: none; }
    .tafel-kopf {
      padding: 8px 12px; border-bottom: 1px solid #302920;
      font-size: 12px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: #a69b8a;
    }
    .raster {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; padding: 8px;
      max-height: 70vh; overflow-y: auto;
    }
    .raster a {
      display: flex; flex-direction: column; align-items: center; gap: 6px;
      padding: 12px 8px; border-radius: 8px; text-align: center; text-decoration: none;
      color: #a69b8a; font-size: 12px; line-height: 1.2;
    }
    .raster a:hover { background: #292319; color: #f3ede2; }
    .raster a[aria-current="page"] { background: rgb(221 156 63 / 0.1); color: #dd9c3f; }
    .band { height: 2px; color: #7c7264; }
    @media (max-width: 639px) {
      .wort, .trenner { display: none; }
    }
  `;

  /** Der Raum eines Hosts, wie `raumVon` in apps.ts: die letzten beiden Labels. */
  function raumVon(host) {
    const name = (host || '').replace(/^\[|\]$/g, '').replace(/:\d+$/, '').toLowerCase();
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(name) || name.includes(':')) return null;
    const teile = name.split('.').filter(Boolean);
    return teile.length < 2 ? null : teile.slice(-2).join('.');
  }
  const istHeim = (raum) => !!raum && raum.endsWith('.home');
  function appUrl(app, raum) {
    const sub = istHeim(raum) ? (app.subHeim || app.sub) : app.sub;
    return sub ? `https://${sub}.${raum}` : `https://${raum}`;
  }

  function svg(name, groesse) {
    const pfad = SYMBOLE[name];
    if (!pfad) return '';
    return `<svg width="${groesse}" height="${groesse}" viewBox="0 0 24 24" fill="none" ` +
      `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ` +
      `aria-hidden="true">${pfad}</svg>`;
  }

  function knoten(tag, klasse, text) {
    const k = document.createElement(tag);
    if (klasse) k.className = klasse;
    if (text != null) k.textContent = text;
    return k;
  }

  class SagantaKopf extends HTMLElement {
    static get observedAttributes() { return ['app', 'titel']; }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._draussen = (e) => {
        if (this._tafel && !this._tafel.hidden && !e.composedPath().includes(this)) this._zu();
      };
      this._taste = (e) => { if (e.key === 'Escape') this._zu(); };
    }

    connectedCallback() {
      this._zeichne();
      document.addEventListener('click', this._draussen);
      document.addEventListener('keydown', this._taste);
    }

    disconnectedCallback() {
      document.removeEventListener('click', this._draussen);
      document.removeEventListener('keydown', this._taste);
    }

    attributeChangedCallback() { if (this.isConnected) this._zeichne(); }

    _zu() {
      if (!this._tafel) return;
      this._tafel.hidden = true;
      this._knopf.setAttribute('aria-expanded', 'false');
    }

    _zeichne() {
      const id = this.getAttribute('app') || '';
      const app = APPS.find((a) => a.id === id);
      const raum = raumVon(window.location.host);
      const shell = APPS.find((a) => a.id === 'shell');
      const wurzel = this.shadowRoot;
      wurzel.textContent = '';
      const stil = document.createElement('style');
      stil.textContent = STIL;
      wurzel.append(stil);

      const zeile = knoten('div', 'zeile');
      const links = knoten('div', 'links');
      const rechts = knoten('div', 'rechts');
      rechts.append(document.createElement('slot'));
      rechts.firstChild.name = 'aktionen';

      this._tafel = null;
      if (raum) {
        const wechsler = knoten('div', 'wechsler');
        const knopf = knoten('button', 'knopf');
        knopf.type = 'button';
        knopf.setAttribute('aria-haspopup', 'menu');
        knopf.setAttribute('aria-expanded', 'false');
        knopf.setAttribute('aria-label', 'App-Wechsler');
        knopf.title = 'Apps';
        knopf.innerHTML = `<span>${svg('layout-grid', 18)}</span>`;
        const tafel = knoten('div', 'tafel');
        tafel.hidden = true;
        tafel.setAttribute('role', 'menu');
        tafel.append(knoten('div', 'tafel-kopf', 'Saganta-Apps'));
        const raster = knoten('div', 'raster');
        for (const a of APPS.filter((x) => istHeim(raum) || !x.nurHeim)) {
          const ziel = knoten('a');
          ziel.href = appUrl(a, raum);
          ziel.title = a.beschreibung;
          ziel.setAttribute('role', 'menuitem');
          if (a.id === id) ziel.setAttribute('aria-current', 'page');
          ziel.innerHTML = svg(a.icon, 20);
          ziel.append(knoten('span', null, a.name));
          raster.append(ziel);
        }
        tafel.append(raster);
        knopf.addEventListener('click', () => {
          tafel.hidden = !tafel.hidden;
          knopf.setAttribute('aria-expanded', String(!tafel.hidden));
        });
        wechsler.append(knopf, tafel);
        links.append(wechsler);
        this._tafel = tafel;
        this._knopf = knopf;
      }

      const marke = knoten(raum ? 'a' : 'span', 'marke');
      if (raum) {
        marke.href = appUrl(shell, raum);
        marke.setAttribute('aria-label', 'Zurück zur Saganta-Übersicht');
      }
      marke.append(knoten('span', 'wort', 'Saganta'), knoten('span', 'trenner', '/'));
      if (app) {
        const sinnbild = knoten('span', 'sinnbild');
        sinnbild.innerHTML = svg(app.icon, 17);
        marke.append(sinnbild);
      }
      marke.append(knoten('span', 'app', this.getAttribute('titel') || (app ? app.name : id)));
      links.append(marke);

      zeile.append(links, rechts);
      const band = knoten('div', 'band');
      band.setAttribute('aria-hidden', 'true');
      // Ohne bekannte App die durchgehende Linie, wie `signaturFuer` in apps.ts.
      band.style.backgroundImage = app ? app.signatur : 'linear-gradient(currentColor, currentColor)';
      wurzel.append(zeile, band);
    }
  }

  customElements.define('saganta-kopf', SagantaKopf);
})();
