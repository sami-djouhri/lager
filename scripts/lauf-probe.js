// Klickt beide Laeufe durch, wie ein Mensch am Regal (Stufe 4).
//
// Laeuft in zenika/alpine-chrome:with-puppeteer gegen eine Wegwerf-Instanz
// (scripts/lauf-probe.sh), NIE gegen den echten Bestand: die Probe legt an,
// bucht und laedt hoch.
//
// Die Kamera ist eine Attrappe (--use-fake-device-for-media-stream), und
// `http://localhost` gilt als sicherer Kontext. So laeuft derselbe Weg wie am
// Telefon bis auf das Erkennen selbst: der Code kommt ueber das Eingabefeld
// der Scanner-Buehne, das Foto aus dem echten (Attrappen-)Kamerastrom.
//
// Gemessen wird, was ein Bild nicht zeigt: Skriptfehler, ob jede Antwort die
// erwartete Art hat, ob der Pin haelt und ob ein Foto ankommt. Die Bilder
// landen in /work/bilder und werden trotzdem angesehen.

const puppeteer = require('puppeteer');

const BASIS = process.env.BASIS || 'http://localhost:8000';
const BILDER = '/work/bilder';
const EAN = '4006381333627';
const EAN2 = '4000521003753';

const befunde = [];
const schritt = (name) => console.log(`-- ${name}`);
function pruefe(bedingung, text) {
  if (!bedingung) befunde.push(text);
  console.log(`   ${bedingung ? 'ok ' : 'FEHL'} ${text}`);
}

async function api(seite, methode, pfad, body) {
  return seite.evaluate(async (m, p, b) => {
    const r = await fetch(`/api${p}`, { method: m, headers: { 'Content-Type': 'application/json' },
      body: b ? JSON.stringify(b) : undefined });
    return { status: r.status, json: await r.json().catch(() => null) };
  }, methode, pfad, body);
}

async function warteText(seite, text, ms = 5000) {
  try {
    await seite.waitForFunction((t) => document.body.innerText.includes(t), { timeout: ms }, text);
    return true;
  } catch {
    return false;
  }
}

async function tippeCode(seite, code) {
  const feld = await seite.$('.scanner-buehne input[aria-label="Code eintippen"]')
    || await seite.$('input[aria-label="Code eintippen"]');
  await feld.click({ clickCount: 3 });
  await feld.type(code);
  await feld.press('Enter');
  await new Promise((r) => setTimeout(r, 600));
}

// Knoepfe werden bis zu 5 s gesucht, nicht sofort: auf dem Pi kam die
// Antwort auf einen Scan einmal spaeter als die feste Pause, und die Probe
// brach ab, obwohl die Seite den Knopf gleich danach zeigte.
async function suche(seite, fn, ...args) {
  try {
    const h = await seite.waitForFunction(fn, { timeout: 5000 }, ...args);
    return h.asElement();
  } catch {
    return null;
  }
}

async function knopf(seite, text, bereich = 'body') {
  const el = await suche(seite, (t, b) => {
    const wurzel = document.querySelector(b) || document.body;
    return [...wurzel.querySelectorAll('button, a')].find((k) => k.textContent.trim() === t) || null;
  }, text, bereich);
  if (!el) throw new Error(`Knopf „${text}“ nicht gefunden`);
  await el.click();
  await new Promise((r) => setTimeout(r, 500));
}

// Einen Knopf in der Quittungszeile klicken, die `zeile` enthaelt.
async function zeilenKnopf(seite, zeile, text, bereich = 'body') {
  const el = await suche(seite, (z, t, b) => {
    const wurzel = document.querySelector(b) || document.body;
    const reihe = [...wurzel.querySelectorAll('.lauf-zeile')].find((r) => r.textContent.includes(z));
    return reihe ? [...reihe.querySelectorAll('button')].find((k) => k.textContent.trim() === t) || null : null;
  }, zeile, text, bereich);
  if (!el) throw new Error(`Knopf „${text}“ in der Zeile „${zeile}“ nicht gefunden`);
  await el.click();
  await new Promise((r) => setTimeout(r, 500));
}

// Fuer das Abbruchbild: ohne Bild sagt ein ABBRUCH nur, welcher Knopf fehlte, nicht was stattdessen dastand.
let abbruchSeite = null;

async function bild(seite, name) {
  await seite.screenshot({ path: `${BILDER}/${name}.png`, fullPage: true });
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium-browser',
    args: ['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
      '--disable-dev-shm-usage'],
  });
  const seite = await browser.newPage();
  abbruchSeite = seite;
  const fehler = [];
  seite.on('pageerror', (e) => fehler.push(`pageerror: ${e.message}`));
  seite.on('console', (m) => { if (m.type() === 'error') fehler.push(`console: ${m.text()}`); });
  await seite.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });

  await seite.goto(`${BASIS}/`, { waitUntil: 'networkidle0' });
  schritt('Plätze anlegen');
  const keller = await api(seite, 'POST', '/plaetze', { name: 'Keller', art: 'raum' });
  const kuehl = await api(seite, 'POST', '/plaetze', { name: 'Kühlschrank', art: 'raum' });
  pruefe(keller.status === 201 && kuehl.status === 201, 'zwei Räume angelegt');
  const kk = keller.json.kennung;
  const kh = kuehl.json.kennung;

  // ---------------- Einbuchen: Lebensmittel ----------------
  schritt('Einbuch-Lauf Lebensmittel');
  await seite.goto(`${BASIS}/b/lebensmittel/lauf`, { waitUntil: 'networkidle0' });
  await bild(seite, '01-lauf-leer-390');
  await knopf(seite, 'Scannen');
  pruefe(!!(await seite.$('.scanner-buehne')), 'Scanner-Bühne offen');
  await new Promise((r) => setTimeout(r, 1500));
  const kamera = await seite.evaluate(() => {
    const v = document.querySelector('.scanner-buehne video');
    return v ? v.videoWidth : -1;
  });
  pruefe(kamera > 0, `Kamerastrom läuft (Breite ${kamera})`);
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'kennt das Lager noch nicht'), 'unbekannter Strichcode fragt nach dem Namen');
  await bild(seite, '02-name-fehlt-390');
  const name = await seite.$('.scanner-buehne .lauf-frage input.form-input');
  await name.type('Haferdrink');
  await knopf(seite, 'Einbuchen', '.scanner-buehne');
  pruefe(await warteText(seite, 'Haferdrink eingebucht'), 'Haferdrink eingebucht, neues Produkt');
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'jetzt 2 Stk'), 'zweiter Scan erhöht den Posten (ein Posten je MHD)');
  await bild(seite, '03-quittung-390');

  // Preis in der Quittung (im Scanner) eintragen
  const preis = await seite.$('.scanner-buehne .lauf-zeile input[placeholder="leer lassen"]');
  await preis.type('2,58');
  await seite.click('.scanner-titel');
  await new Promise((r) => setTimeout(r, 700));
  await knopf(seite, 'Fertig', '.scanner-buehne');
  pruefe(!(await seite.$('.scanner-buehne')), 'Scanner geschlossen');

  // Ohne Strichcode
  await knopf(seite, 'Ohne Strichcode');
  const n2 = await seite.$('.lauf-frage input.form-input');
  await n2.type('Brot');
  await knopf(seite, 'Einbuchen', '.lauf-frage');
  pruefe(await warteText(seite, 'Brot eingebucht'), 'Brot ohne Strichcode eingebucht');
  const zaehler = await seite.$eval('.lauf-zaehler', (e) => e.textContent);
  pruefe(zaehler.includes('2 Einträge') && zaehler.includes('1 ohne Preis'), `Zähler: ${zaehler}`);

  // Abschluss
  await seite.type('input[placeholder="z. B. Kaufland"]', 'Kaufland');
  await seite.type('input[placeholder="z. B. 47,80"]', '12,50');
  await bild(seite, '04-abschluss-390');
  await knopf(seite, 'Einkauf speichern und Lauf beenden');
  pruefe(await warteText(seite, 'gespeichert'), 'Einkauf gespeichert');
  const eink = await api(seite, 'GET', '/einkaeufe');
  pruefe(eink.json.length === 1 && eink.json[0].gesamt === 12.5 && eink.json[0].laden === 'Kaufland',
    'Einkauf 12,50 € bei Kaufland in der API');
  const stock = await api(seite, 'GET', '/stock?limit=50');
  const hafer = stock.json.items.find((p) => p.product_name === 'Haferdrink');
  pruefe(hafer && hafer.quantity === 2 && hafer.preis === 2.58, `Haferdrink 2 Stk, Preis ${hafer && hafer.preis}`);
  const brot = stock.json.items.find((p) => p.product_name === 'Brot');
  pruefe(brot && brot.preis === null, 'Brot bleibt ohne Preis (nichts verteilt)');

  // ---------------- Einbuchen: Technik ----------------
  schritt('Einbuch-Lauf Technik');
  await seite.goto(`${BASIS}/b/technik/lauf`, { waitUntil: 'networkidle0' });
  await knopf(seite, 'Scannen');
  await new Promise((r) => setTimeout(r, 1200));
  await tippeCode(seite, EAN2);
  const n3 = await seite.$('.scanner-buehne .lauf-frage input.form-input');
  await n3.type('USB-Stick');
  await knopf(seite, 'Einbuchen', '.scanner-buehne');
  pruefe(await warteText(seite, 'S-0001 USB-Stick eingebucht'), 'S-0001 USB-Stick');
  await knopf(seite, 'Foto', '.scanner-buehne');
  pruefe(await seite.waitForSelector('.scanner-buehne .lauf-foto img', { timeout: 6000 }).then(() => true, () => false),
    'Foto aus dem Kamerastrom angekommen');
  await tippeCode(seite, EAN2);
  pruefe(await warteText(seite, 'Davon gibt es schon ein Stück'), 'gleicher Strichcode zeigt das vorhandene Stück');
  await bild(seite, '05-bekannt-390');
  await knopf(seite, 'Neues Stück einbuchen', '.scanner-buehne');
  pruefe(await warteText(seite, 'S-0002 USB-Stick eingebucht'), 'zweites Stück S-0002 (Strichcode nicht eindeutig)');
  // Ein Fehlscan: drittes Stueck, sofort zurueckgenommen (zwei Griffe).
  await tippeCode(seite, EAN2);
  await knopf(seite, 'Neues Stück einbuchen', '.scanner-buehne');
  pruefe(await warteText(seite, 'S-0003 USB-Stick eingebucht'), 'Fehlscan S-0003 eingebucht');
  await zeilenKnopf(seite, 'S-0003', 'Zurücknehmen', '.scanner-buehne');
  pruefe(await warteText(seite, 'Wirklich zurücknehmen?'), 'erster Griff fragt nur');
  await bild(seite, '05b-zuruecknehmen-fragt-390');
  // Der Knopf faellt nach 4 s ohne zweiten Griff zurueck (Absicht). Ein
  // Ganzseitenbild auf dem Pi dauert laenger: dann wurde der zweite Klick zum
  // ersten, und S-0003 blieb stehen (Befund 01.11.). Also neu scharf machen.
  if (!(await warteText(seite, 'Wirklich zurücknehmen?', 200))) {
    console.log('   (Knopf stand nach dem Bild wieder auf Anfang, neu gegriffen)');
    await zeilenKnopf(seite, 'S-0003', 'Zurücknehmen', '.scanner-buehne');
  }
  await zeilenKnopf(seite, 'S-0003', 'Wirklich zurücknehmen?', '.scanner-buehne');
  pruefe(await warteText(seite, 'S-0003 USB-Stick zurückgenommen'), 'S-0003 zurückgenommen');
  await tippeCode(seite, 'S-0001');
  pruefe(await warteText(seite, 'ist schon im Bestand'), 'eigenes Etikett: kein Zugang');
  await tippeCode(seite, kk);
  pruefe(await warteText(seite, 'Platz-Etikett'), 'Platz-Etikett im Einbuch-Lauf abgewiesen');
  await knopf(seite, 'Fertig', '.scanner-buehne');
  await seite.type('input[placeholder="z. B. 47,80"]', '19,98');
  await knopf(seite, 'Einkauf speichern und Lauf beenden');
  pruefe(await warteText(seite, 'den Rest als Preis'), 'Gesamtbetrag auf die Stücke verteilt');
  const sachen = await api(seite, 'GET', '/electronics?limit=50');
  const preise = sachen.json.items.map((s) => s.purchase_price).sort();
  pruefe(JSON.stringify(preise) === JSON.stringify([9.99, 9.99]), `Preise ${JSON.stringify(preise)}`);

  // ---------------- Lagern ----------------
  schritt('Lagern-Lauf');
  await seite.goto(`${BASIS}/lagern`, { waitUntil: 'networkidle0' });
  await bild(seite, '06-lagern-390');
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'Zuerst das Fach-Etikett'), 'ohne Fach keine Buchung');
  await tippeCode(seite, kk);
  pruefe(await warteText(seite, `Ziel: ${kk}`), 'Fach gescannt');
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'Haferdrink: → Keller'), 'Haferdrink eingelagert');
  const ohnePin = await seite.$eval('.lauf-stand', (e) => e.textContent);
  pruefe(ohnePin.includes('Erst ein Fach-Etikett'), 'ohne Pin ist das Fach nach der Buchung weg');
  await tippeCode(seite, kk);
  await knopf(seite, 'Fach anheften');
  await tippeCode(seite, 'S-0001');
  await tippeCode(seite, 'S-0002');
  const mitPin = await seite.$eval('.lauf-stand', (e) => e.textContent);
  pruefe(mitPin.includes('angeheftet'), 'angeheftetes Fach bleibt stehen');
  const z = await seite.$eval('.lauf-zaehler', (e) => e.textContent);
  pruefe(z.includes('3 gebucht'), `Zähler ${z}`);
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'schon ganz eingelagert'), 'schon Eingelagertes verweist auf Umlagern');

  await knopf(seite, 'Umlagern');
  await tippeCode(seite, kh);
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'Keller → Kühlschrank'), 'Haferdrink umgelagert');

  await knopf(seite, 'Auf den Shopfloor');
  await tippeCode(seite, 'S-0001');
  pruefe(await warteText(seite, 'Warum kommt es aus dem Fach?'), 'ohne Grund fragt der Lauf nach dem Grund des Bereichs');
  const frageGruende = await seite.$$eval('.lauf-frage .chip', (k) => k.map((x) => x.textContent.trim()));
  pruefe(JSON.stringify(frageGruende) === JSON.stringify(['Im Einsatz', 'In Reparatur', 'Verkauf vorbereiten']),
    `nur die Gründe von Technik (${frageGruende.join(', ')})`);
  await knopf(seite, 'In Reparatur', '.lauf-frage');
  pruefe(await warteText(seite, 'In Reparatur · gehört nach Keller'), 'S-0001 in Reparatur, Platz bleibt');
  await tippeCode(seite, EAN);
  pruefe(await warteText(seite, 'Haferdrink: nicht eingelagert'), 'Vorrat aus dem Fach geholt');
  pruefe(await warteText(seite, '2 Stk'), 'Menge mit deutscher Einheit (nicht „piece“)');
  await bild(seite, '07-lagern-fertig-390');
  // S-0002 lag vor diesem Durchgang ohne Platz auf dem Shopfloor.
  await zeilenKnopf(seite, 'S-0002', 'Zurücknehmen');
  await zeilenKnopf(seite, 'S-0002', 'Wirklich zurücknehmen?');
  pruefe(await warteText(seite, 'USB-Stick zurückgenommen'), 'Lagern von S-0002 zurückgenommen');
  const s2 = (await api(seite, 'GET', '/electronics?limit=50')).json.items.find((x) => x.kennung === 'S-0002');
  pruefe(s2 && s2.platz_id === null && s2.verbleib === 'shopfloor',
    `S-0002 wieder ohne Platz auf dem Shopfloor (${s2 && s2.verbleib}, Platz ${s2 && s2.platz_id})`);

  // ---------------- Startseite: Filme & Medien ohne Schluessel ----------------
  schritt('Startseite');
  await seite.goto(`${BASIS}/`, { waitUntil: 'networkidle0' });
  pruefe(await warteText(seite, 'Wartet auf die Anbindung an medien'),
    'Filme & Medien ohne Schlüssel ausgegraut, mit Satz');

  // ---------------- Sachen-Seite ----------------
  schritt('Sachen-Seite');
  await seite.goto(`${BASIS}/b/technik`, { waitUntil: 'networkidle0' });
  pruefe(await warteText(seite, 'S-0001'), 'Kennung steht an der Sache');
  pruefe(!!(await seite.$('img.sache-bild')), 'Foto an der Sache sichtbar');
  pruefe(await warteText(seite, 'Platz & Verbleib'), 'Griffe an der Sache beschriftet');
  await bild(seite, '08-sachen-390');

  // ---------------- Stufe 7a: Vermisst, Abgang, Zuruecknehmen ----------------
  schritt('Vermisst und Abgang');
  const griff = async (kennung, text) => {
    const el = await suche(seite, (k, t) => {
      const reihe = document.getElementById(k);
      return reihe ? [...reihe.querySelectorAll('button')].find((b) => b.textContent.trim() === t) || null : null;
    }, kennung, text);
    if (!el) throw new Error(`Griff „${text}“ an ${kennung} nicht gefunden`);
    await el.click();
    await new Promise((r) => setTimeout(r, 500));
  };
  await griff('S-0001', 'Platz & Verbleib');
  await seite.evaluate(() => {
    const wahl = [...document.querySelectorAll('.inline-form select')].pop();
    const setze = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    setze.call(wahl, 'vermisst');
    wahl.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await knopf(seite, 'Speichern', '.inline-form');
  pruefe(await warteText(seite, 'vermisst'), 'S-0001 als vermisst markiert');
  await griff('S-0002', 'Abgang');
  await seite.type('.inline-form input[inputmode="decimal"]', '7,50');
  await bild(seite, '08b-abgang-390');
  await knopf(seite, 'Als verkauft buchen', '.inline-form');
  pruefe(await warteText(seite, 'Abgegangen (1)'), 'S-0002 steht unter Abgegangen');
  pruefe(!(await seite.$('#S-0002')), 'S-0002 nicht mehr in der Liste');
  const weg2 = (await api(seite, 'GET', '/electronics?limit=50&abgegangen=true')).json.items;
  pruefe(weg2.length === 1 && weg2[0].erloes === 7.5 && weg2[0].abgang === 'verkauft',
    `Abgang mit Erlös 7,50 (${weg2[0] && weg2[0].erloes})`);
  await seite.click('details.abgaenge > summary');
  await knopf(seite, 'Zurücknehmen', 'details.abgaenge');
  pruefe(await suche(seite, () => document.getElementById('S-0002')), 'S-0002 nach dem Zurücknehmen wieder da');
  await seite.goto(`${BASIS}/`, { waitUntil: 'networkidle0' });
  pruefe(await warteText(seite, '1 Stück ist vermisst'), 'Startseite nennt das vermisste Stück');
  await bild(seite, '08c-start-vermisst-390');

  // Breite Ansicht
  await seite.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  await seite.goto(`${BASIS}/b/lebensmittel/lauf`, { waitUntil: 'networkidle0' });
  await bild(seite, '09-lauf-1280');
  await knopf(seite, 'Scannen');
  await new Promise((r) => setTimeout(r, 1200));
  await bild(seite, '10-scanner-1280');
  await knopf(seite, 'Fertig', '.scanner-buehne');
  await seite.goto(`${BASIS}/lagern`, { waitUntil: 'networkidle0' });
  await bild(seite, '11-lagern-1280');

  // Ueberlauf auf dem Handy
  await seite.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });
  for (const pfad of ['/b/lebensmittel/lauf', '/b/technik/lauf', '/lagern', '/b/technik']) {
    await seite.goto(`${BASIS}${pfad}`, { waitUntil: 'networkidle0' });
    const breit = await seite.evaluate(() => document.documentElement.scrollWidth);
    pruefe(breit <= 390, `${pfad}: kein waagerechter Überlauf (${breit} px)`);
  }

  // Eine Abweisung loest die Probe absichtlich aus (Platz-Etikett im
  // Einbuch-Lauf) und prueft sie oben. Der Browser meldet sie als
  // Konsolenfehler; genau diese ist deshalb erwartet, eine zweite waere ein
  // Befund. (Bis Stufe 5 war es auch „Sache ohne Grund", das ist jetzt eine
  // Rueckfrage.)
  const abgewiesen = fehler.filter((f) => f.includes('status of 422'));
  pruefe(abgewiesen.length === 1, `genau die eine erwartete Abweisung (${abgewiesen.length})`);
  for (const f of fehler.filter((x) => !x.includes('status of 422'))) befunde.push(f);
  const unerwartet = fehler.filter((x) => !x.includes('status of 422'));
  console.log(unerwartet.length ? `Skriptfehler:\n  ${unerwartet.join('\n  ')}` : 'Keine Skriptfehler.');
  await browser.close();
  console.log(befunde.length ? `\n${befunde.length} BEFUNDE` : '\nKEINE BEFUNDE');
  process.exit(befunde.length ? 1 : 0);
})().catch(async (e) => {
  console.error('ABBRUCH:', e.message);
  if (abbruchSeite) {
    try {
      await bild(abbruchSeite, '99-abbruch');
      const text = await abbruchSeite.evaluate(() => {
        const b = document.querySelector('.scanner-buehne');
        return (b || document.body).innerText;
      });
      console.error(`Seitentext beim Abbruch:\n${text.slice(0, 1500)}`);
    } catch (f) {
      console.error('Abbruchbild gescheitert:', f.message);
    }
  }
  process.exit(2);
});
