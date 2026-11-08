# lager: Richtung und Stufen

> Auftrag **2026-11-01**: „Das Lager soll für mehr als nur Lebensmittel
> sein, aber getrennt. Assets auflösen. Schaue bei medien, was man abschauen
> kann." Auf die erste Auswahlfrage: **„planen wir das größer"**, danach drei
> Auswahlrunden (zwei zu den Bereichen, eine zu Verbleib und Inventur).
>
> Hier steht, **was** gilt und **warum**. Die Stufen stehen als Aufgaben im
> Saganta Projectdeck unter **Saganta Lager**. Zuschnitt wie bei medien: eine
> Stufe je Sitzung, danach ein Stand an den Owner.

## Ausgangslage (gemessen 2026-11-01)

- Bestand: 20 Produkte, 24 Posten, 10 Elektronik-Stücke, ein Mandant. Die
  Lebensmittel sind der Demo-Seed vom Februar, im Alltag lief das Lager nicht.
- `saganta-assets` + `saganta-assets-api`: 10 Zeilen, **alle** Spiegel der
  Lager-Elektronik, **0** selbst angelegt. Auflösen verliert keine Daten. Den
  Marktwert hat das Lager schon selbst (`app/services/marktwatch.py`).
- Der Entscheid „assets wird in lager eingebaut" stand seit dem 24.10. nur in
  einer Notiz in `wake-gateway/host/services.json`.

## Entscheidungen (Owner, 2026-11-01)

**Die Startseite ist die Bereichswahl.** Man klickt einen Bereich an, und darin
mischt sich nichts mit den anderen. Jede Kachel trägt **einen Satz, was
ansteht** (wie die medien-Startseite), roter Rand nur, wenn etwas blockiert.

**Feste Bereiche, keine selbst angelegten.** Neun, jeder mit einer Bauart:

| Bereich | Bauart | Frist heißt |
|---|---|---|
| Lebensmittel | Vorrat (Menge, Frist, Mindestbestand) | MHD |
| Getränke & Keller | Vorrat | MHD |
| Haushalt & Drogerie | Vorrat | (keine Pflicht) |
| Hausapotheke | Vorrat | Verfall |
| Garten & Saatgut | Vorrat | Keimfähig bis |
| Werkstatt-Material | Fundort: **wo es liegt, damit ich es wiederfinde**, keine Menge | |
| Technik & Sachen | Einzelstück mit Nummer (ersetzt Assets und „Wertsachen") | Garantie |
| Kleidung & Schuhe | **nur Kisten** (Kiste + Inhaltsangabe) | |
| Saison & Deko | Kisten | |

Verworfen: Tierbedarf, Sport & Outdoor, Spiele & Freizeit, Zubehör am Gerät,
Belege & Garantie als Verknüpfung, Fotos je Stück, selbst angelegte Bereiche,
Kleidung als Einzelstücke.

**Lagerplätze mit Etiketten wie in medien.** Jeder Platz hat eine fortlaufende
Kennung `L-001` (nicht aus dem Namen abgeleitet: ein Etikett klebt, ein Name
wird umbenannt), dazu Raum › Regal › Fach als Name. Der Scanner erkennt am
Präfix ohne Rückfrage, ob ein Platz oder ein Stück vor der Kamera war.

**Behälter sind Plätze.** Eine Kiste hat selbst ein Etikett, steht an einem
Platz und hat Inhalt; zieht die Kiste um, zieht der Inhalt mit. Eine Kiste hat
**keinen** Verbleib („nur Platz").

**Lagerplatz und Verbleib sind zwei Dinge** (aus medien übernommen). Der
Lagerplatz sagt, wohin ein Stück gehört, und bleibt beim Herausholen stehen;
der Verbleib sagt, wo es ist: **Eingelagert · Shopfloor · Verliehen ·
Vermisst**. Alterung („seit 40 Tagen verliehen") kommt aus dem Verlauf, nicht
aus einem Datumsfeld.

**Einbuchen vor Einlagern** (Owner, Architektur-Runde 2026-11-01: „Wie bei
Medien soll es Shopfloor geben. Einlagern hilft nur beim Wiederfinden,
eingebucht ist erstmal wichtiger für ‚ist da‘"). Was eingebucht ist, zählt als
vorhanden, auch ohne Platz. Ohne Platz liegt es auf dem **Shopfloor, noch
nicht eingelagert**. Der Shopfloor hat eine feste Grundliste wie in medien:
**Im Einsatz · In Reparatur · Verkauf vorbereiten**; ein leerer Grund heißt
„noch nicht eingelagert", ein Zugang bekommt nie einen Grund. „Im Einsatz" ist
der Verkaufsschutz (bisher `usage_status`).

**Abgang: Verkauft oder Weg, die Zeile bleibt.** Sie fällt aus jeder Liste,
„was hatte ich mal" und die Erlösrechnung bleiben beantwortbar.

**Inventur je Fach:** Fach scannen, Stücke scannen. Was fehlt, steht am Ende
als **Liste zum Bestätigen** (je Stück Vermisst / Shopfloor / woanders).
Nichts wird von selbst gebucht.

**Wert und Verkauf für alle Einzelstücke**, nicht nur Elektronik: Kaufpreis,
Marktwert über marktwatch, Verkaufsvorschläge. Was im Einsatz ist, wird nie
vorgeschlagen (der bisherige `usage_status`-Schutz).

**Die Einkaufsliste wird eine eigene App**, auch nativ für Android. Sie steht
deshalb nicht in diesem Plan, sondern als eigenes Produkt im Projectdeck. Bis
dahin bleibt `/einkaufsliste` im Lager und von der Startseite erreichbar.

## Architektur (Owner-Runde 2026-11-01, zweite Sitzung)

Gemessen vor der Runde: vier Bauarten, aber nur zwei Datenmodelle
(`product`/`stock_entry` und `electronic_asset`), der Ort an Posten und
Stücken ein freier Text (live `Kuehlschrank`, `Vorratskammer`, `Homelab`,
`Elektronik`), 8 von 10 Stücken mit Homelab-Feldern aus einem Seed für
host/node1. Die Stufen 3 bis 7 brauchen drei Grundbausteine, die es nicht gab.

**Drei Tabellen kommen dazu, eine wird umgebaut:**

| Tabelle | Inhalt |
|---|---|
| `platz` | Kennung `L-001` (fortlaufend je Mandant), Name, Art **Raum › Regal › Fach › Kiste**, Eltern-Platz. Eine Kiste trägt Inhaltstext und optional einen Bereich (Kleidung, Saison) |
| `sache` | alles, was kein Vorrat ist: Technik-Stücke (aus `electronic_asset`) und Werkstatt-Dinge. `bereich`, `platz_id`, `verbleib`, `shopfloor_grund`, `abgang` |
| `verlauf` | jede Änderung Feld für Feld (Vorbild medien); daraus Alterung und Mahnliste |
| `stock_entry` | bekommt `platz_id`; der freie Text `location` fällt nach der Migration |

**Feste Verschachtelung** (Owner): Raum › Regal › Fach, eine Kiste steht in
einem Fach oder direkt im Raum, **nie in einer Kiste**. Dinge dürfen an jeder
Ebene liegen (das Fahrrad steht im Keller, ohne Fach). Zieht eine Kiste um,
ändert sich nur ihr Eltern-Platz.

**Werkstatt-Material ist eine Zeile je Ding** (Owner): „Schrauben M6" ist eine
`sache` ohne Nummer, Wert und Verbleib-Pflicht, damit „wo ist …" das Ding
findet und nicht nur das Fach.

**Vorrat bekommt nur Platz oder Shopfloor** (Owner): Verliehen und Vermisst
gibt es nur für Sachen. Bei Vorräten entscheidet die Menge.

**Plätze sind ein eigener Eingang neben den Bereichen** (Owner), wie die
Einkaufsliste: Raumbaum, Etiketten, Inventur je Fach und die Suche über
alles. Ein Fach ist in echt gemischt; in den Bereichen steht der Platz nur als
Angabe am Ding.

**Homelab-Felder fallen ersatzlos** („ganz streichen"):
`host_name`, `homelab_role`, `service_refs` und der Seed
`app/services/homelab_inventory.py`. life-ops liest sie über `.get` und
bricht daran nicht.

**Migration der Altorte:** jeder freie Ortstext wird ein Raum, die Posten
und Stücke liegen danach dort. `Homelab` und `Elektronik` sind keine Orte,
die 9 Stücke mit `usage_status` critical stehen danach auf dem Shopfloor mit
Grund „Im Einsatz", das übrige ist noch nicht eingelagert.

**Nach außen bleibt die Form:** `/api/electronics` liefert weiter
`usage_status` (aus dem Verbleib abgeleitet), `/api/critical` bleibt
unverändert. Beide liest life-ops, die mobile-api hängt am selben Dienst.

## Filme & Medien: das physische Lager aus medien (Owner-Runde 2026-11-01, dritte Sitzung)

„Medien führt ein eigenes Lager für physische DVDs, das soll nach Saganta
Lager." Zwei Auswahlrunden.

**Gemessen davor:** in medien stehen 271 Titel, aber **0 Exemplare und 0
Lagerplätze** (224 Exemplare am 2026-10-31 auf Ansage geleert, Rückweg
`/app/data/medien.vor-leeren-2026-10-31.db` im Volume). Erwartet werden beim
neuen Einbuchen 700 bis 800 Stück. Der Umzug kommt **vor** diesem Einbuchen,
deshalb muss kein Stück migriert werden.

**Der Schnitt** (Owner):

| zieht ins Lager | bleibt in medien |
|---|---|
| Exemplare (Medium, Zustand, Staffel/`teil`, Edition, EAN, Kaufpreis) | Katalog: Titel, Sammlung (Soll), Fehlt noch |
| Lagerplätze und Etiketten | Duell, Karten, Rangliste, Geschmack |
| Einbuchen, Lagern, Shopfloor, Inventur | Werke (Offline-IMDb), Vault-Abgleich |
| **Fotos je Stück** („ganz ins Lager") | Verkauf: Dubletten-Regel, Verkaufsindex, Pakete, Inserat, Preis, Erlös |

- **Zehnter Bereich „Filme & Medien"** mit eigener Bauart `exemplar`: jedes
  Stück verweist auf einen Titel im medien-Katalog. Später gehen Bücher, Spiele
  und Musik aus medien in denselben Bereich. Die Absage an „Spiele & Freizeit"
  bleibt, das hier ist kein Freizeitbereich, sondern der Medienbestand.
- **Der Titel kommt live aus medien** (Owner): der Einbuch-Lauf sucht im
  Katalog und legt dort bei Bedarf an („Titel auf der Hülle", Staffel aus dem
  Titel erkannt). Das Stück trägt die medien-Titelnummer und eine Kopie des
  Titels zur Anzeige. Ist medien aus, ist im Bereich kein Einbuchen möglich, das
  Übrige im Lager läuft weiter.
- **Der Verkauf bleibt in medien** (Owner): was weg soll, hängt am Titel und an
  der Wertung. medien liest Zustand, Edition und Kaufpreis vom Lager und meldet
  den Abgang (verkauft, Datum, Erlös) an das Lager-Stück zurück.
- **Fotos liegen im Lager** (Owner), aufgenommen im Einbuch-Scanner aus dem
  Kamerastrom; medien holt sie für Inserat und Duell vom Lager. **Entschieden
  2026-11-01 (Stufe-4-Runde): Fotos gelten für alle Sachen**, nicht für Vorräte.
  Die alte Absage „Fotos je Stück" ist damit aufgehoben.
- **Schutz: der Saganta-Login reicht** (Owner). Physische Scheiben sind kein
  Vault-Inhalt; der Vault-Abgleich bleibt in medien und kommt nie ins Lager.
- **Einbuchen wartet** (Owner), bis das Lager den Bereich kann.

**Festgelegt ohne eigene Frage** (folgt aus den Entscheiden, Einspruch jederzeit):

- **Kaufpreis und Konvolut-Preis gehören dem Lager**, für jeden Bereich: der
  Einbuch-Lauf verteilt einen Gesamtpreis gewichtet auf die Stücke des
  Durchgangs, wie bisher in medien. Das ist zugleich die Projectdeck-Aufgabe
  „Kaufpreis beim Einbuchen erfassen". medien liest den Einstand für die
  Warnung „Angebot unter Einstand".
- **Stück-Etiketten tragen ein eigenes Präfix**, damit der Scanner Platz
  (`L-`), Stück und EAN ohne Rückfrage auseinanderhält. Gedruckt nur für Stücke
  ohne lesbare EAN, wie in medien.
- **medien hält einen Spiegel des physischen Ist** mit Zeitstempel, Vorbild
  `vault_bericht`: ist das Lager nicht erreichbar, bleibt der letzte Stand
  stehen und medien sagt „Stand von …". Sonst füllte jeder Lager-Neustart die
  Fehlt-Liste mit 700 Titeln.
- **Beide Richtungen mit Dienst-Token** (`saganta/scripts/dienst-token.py`).
  In medien braucht das neue Methode-Pfad-Paare in `MASCHINENWEGE`
  (`app/sicherheit.py`), nicht einen offenen Pfad.
- **Mandanten:** medien ist bewusst einbenutzig („bleibt meine"). Der Bereich
  ist deshalb nur im Mandanten offen, an den ein Katalog angebunden ist; für
  alle anderen steht er ausgegraut mit einem Satz, statt in eine Seite zu
  führen, deren Einbuchen nie gelingt.
- **medien räumt danach ab:** Exemplar-Tabelle, Läufe und Inventur fallen dort,
  `#lager/*` und gedruckte `#ex/<id>` leiten ins Lager weiter.

## Läufe (Owner-Runden 2026-11-01, vierte Sitzung, drei Auswahlrunden)

Vor dem Bau von Stufe 4 gefragt, weil sie bestimmen, wie sich der Lauf am
Regal anfühlt:

- **Fotos für alle Sachen** (siehe oben), nicht für Vorräte.
- **Vorrat: Platz als Vorgabe je Durchgang.** Anders als in medien darf der
  Einbuch-Lauf einen Platz voreinstellen (Kühlschrank), damit der Wocheneinkauf
  ein Lauf ist und nicht zwei. Ohne Vorgabe landet alles auf dem Shopfloor.
- **Preis bei Vorräten: Gesamt plus Einzelpreis.** Am Ende des Laufs optional
  Gesamtbetrag und Laden (wird ein `einkauf`), je Posten ein freiwilliges
  Preisfeld. **Nichts wird verteilt**: 1 kg Mehl und 200 g Käse nach Menge
  gewichtet ergäben ausgedachte Einzelpreise. Zweck laut Owner: Ausgaben je
  Monat, Verlust in Euro, Preis je Produkt. Bei Sachen geht ein Gesamtbetrag
  auf die Stücke ohne eigenen Preis (gewichtet nach Marktwert, wenn ihn jedes
  hat, sonst zu gleichen Teilen).
- **Kein Beleg-Import** (Picnic, Kaufland-App): Preise von Hand, Produkte per
  Strichcode.
- **MHD als Vorschlag** (übliche Haltbarkeit des Produkts), korrigiert in der
  Quittung, ohne den nächsten Scan aufzuhalten.
- **Ein Posten je MHD**: derselbe Scan im selben Lauf erhöht die Menge, solange
  MHD und Platz gleich sind.
- **Lagern in drei Richtungen:** Einlagern nimmt nur, was keinen Platz hat;
  **Umlagern** nimmt nur, was schon in einem Fach liegt („entweder man
  lagert aus und dann ein oder von Anfang an um"); Auf den Shopfloor holt aus
  dem Fach, **auch Vorräte**. Ein Scan nimmt den **ganzen Posten**.
- **MHD-Rückfrage**, wenn mehrere passende Posten verschiedene MHDs haben
  (bei Sachen entscheidet wie in medien der Zustand).
- **Stück-Etiketten nur ohne Strichcode** (wie medien).

Festgelegt ohne eigene Frage: der eindeutige Strichcode an `sache` fällt
(Migration 0009). Er nennt die Sorte, nicht das Stück; zwei gleiche USB-Sticks
aus einem Konvolut hätten sonst nicht beide eingebucht werden können. Das
Stück erkennt man an der Kennung `S-0001` (fortlaufend je Mandant, nie neu
vergeben) und an der Seriennummer, die eindeutig bleibt.

## Stufen 6 bis 9 und die Nachbarprodukte (Owner-Runde 2026-11-01, fünfte Sitzung)

Fünf Auswahlrunden, während Stufe 4 und 5 in einer anderen Sitzung gebaut
wurden.

- **Fotos** (Owner, ergänzt die Stufe-4-Runde): Sachen behalten ihr Foto wie
  gebaut. **Vorrat bekommt ein Foto je Produkt, einmalig**, nicht je Posten
  („für Lebensmittel brauche ich nicht immer wieder ein Foto, eins reicht").
  **Filme & Medien: Foto je Stück optional**, gebraucht vor allem für den
  Verkauf über medien.
- **Werkstatt (Stufe 6):** Einbuchen heißt Fach scannen, dann Namen tippen,
  Zeile um Zeile; kein Etikett am Ding.
- **Suche „wo ist …" geht über wirklich alles** (Owner), auch die 700 bis 800
  Exemplare aus Filme & Medien.
- **Verliehen braucht Saganta Kontakte** (Owner). Die App gibt es noch nicht;
  sie wird ein eigenes Produkt (siehe unten), Stufe 7 wird deshalb geteilt:
  **7a Vermisst und Abgang** kommt nach Stufe 6, **7b Verliehen** nach Kontakte.
- **Mahnliste nur im Lager:** ein Kachelsatz („seit 40 Tagen bei …"), kein Push.
- **Inventur (Stufe 8) zählt auch Vorrat mit Menge.** Eine Abweichung kommt wie
  bei Sachen auf die Bestätigungsliste („Menge 3 statt 5 übernehmen?"), nichts
  wird von selbst gebucht.
- **Fristen:** feste Vorwarnung je Bereich (Richtwert Lebensmittel 7 Tage,
  Apotheke 30, Saatgut zur Saison), nur als Kachelsatz, kein Push, nicht je
  Produkt einstellbar.
- **Wert + Verkauf (Stufe 9): keine Ausweitung der Vorschläge.** Die
  bestehenden Elektronik-Vorschläge bleiben, für die übrigen Sachen nur Wert
  (Kaufpreis, Marktwert) und der Schutz „Im Einsatz". Das ersetzt die frühere
  Zeile „Verkaufsvorschläge für alle Einzelstücke".
- **Demo-Seed vom Februar leeren** (Owner: ja, vorher sichern). Erst nach dem
  Ausrollen von Stufe 4 und 5, damit kein Lauf und keine Migration
  dazwischenläuft.

**Nachbarprodukte (Reihenfolge Owner):** Lager Stufe 5 → **Saganta
Einkaufsliste** → **Saganta Kontakte** → Lager 6, 7a, 8, 9; 7b sobald Kontakte
steht.

- **Einkaufsliste:** unterschrittener Mindestbestand landet von selbst darauf;
  Abhaken bucht ins Lager (als Posten auf dem Shopfloor, noch nicht
  eingelagert); fehlende Zutaten geplanter Gerichte aus MealPrep. Eine geteilte
  Live-Liste im Mandanten war keine Anforderung.
- **Kontakte:** eigene native Android-App, die ins Android-Adressbuch abgleicht
  (SyncAdapter), dazu die Web-Seite. Erster Abnehmer ist der Lager-Verleih.

## Stufen

Neu geordnet nach der dritten Runde: die DVDs warten auf das Lager, deshalb
kommen die Läufe und der Medienbereich direkt nach dem Grundmodell.

| # | Stufe | Inhalt |
|---|---|---|
| 1 ✅ | **Bereiche + Startseite** | `bereich` an Produkten, Bereichswahl mit Satz je Kachel, Navigation je Bereich, alte Adressen leiten weiter. Wertsachen heißen Technik & Sachen |
| 2 ✅ | **Assets auflösen** | `saganta-assets` und `-api` stilllegen, Weiterleitung `assets.home.arpa` auf das Lager, Wecker-Eintrag, Prüfskripte, Projectdeck |
| 3 ✅ | **Grundmodell + Plätze** | Tabellen `platz`, `sache`, `verlauf`; `electronic_asset` geht in `sache` auf, Homelab-Felder fallen, Altorte werden Räume. Eingang „Plätze" mit Raumbaum, Etiketten drucken, Kisten mit Inhalt; damit gehen Kleidung und Saison auf. Shopfloor-Seite „noch nicht eingelagert" |
| 4 ✅ | **Einbuchen- und Lagern-Lauf** | Scanner wie in medien: Einbuchen mit Vorgabe je Durchgang, Fortschritt, Kaufpreis und Konvolut-Verteilung, Foto aus dem Kamerastrom; Lagern mit Pin; Stück-Etiketten |
| 5 | **Filme & Medien** | Bauart `exemplar`, Anbindung an den medien-Katalog in beide Richtungen, Spiegel in medien, Verkauf meldet den Abgang; medien baut Exemplare und Läufe ab. Danach bucht der Owner die 700 bis 800 Stück ein |
| 6 | **Werkstatt-Material** | Werkstatt-Dinge als `sache` (Fach scannen, Namen tippen), Suche „wo ist …" über alles im Eingang Plätze |
| 7a ✅ | **Vermisst, Abgang** | Vermisst, Verkauft/Weg für Sachen |
| 7b | **Verliehen** (nach Saganta Kontakte) | Verliehen an einen Kontakt, Mahnliste aus dem Verlauf als Kachelsatz |
| 8 | **Inventur je Fach** | Fach scannen, Stücke scannen, Vorrat mit Menge; alles auf die Bestätigungsliste |
| 9 | **Wert für alle Sachen** | Kaufpreis, Marktwert und Schutz „Im Einsatz" über jede Kategorie außer Filme & Medien; Vorschläge bleiben bei der Elektronik |

Bereiche, deren Bauart noch nicht gebaut ist, stehen auf der Startseite
**ausgegraut mit der Stufe, die sie öffnet**. Eine Kachel, die in eine leere
Seite führt, sähe aus wie ein kaputter Bereich.

## Stand

- **Stufe 1, 2026-11-01:** live. Migration 0007 (Altbestand = Lebensmittel),
  `/api/bereiche`, Navigation je Bereich, 164 Tests. Gesichert vorher nach
  `~/backups/lager-vor-bereichen-2026-11-01/app.db`.
- **Stufe 2, 2026-11-01:** `saganta-assets` und `saganta-assets-api` gestoppt
  und entfernt, Baum in `docker/_retired/saganta-assets-2026-11-01`, Weiterleitung
  `assets.home.arpa` → `lager.home.arpa/b/technik`, Wecker-Eintrag,
  control-map (`migrated`), Prüfskripte und Katalog bereinigt.
  **Offen:** der App-Katalog (`packages/ui/src/apps.ts`) wirkt erst mit dem
  nächsten Bau der Saganta-Apps, bis dahin zeigt der App-Wechsler noch „Besitz“
  (führt über die Weiterleitung ins Lager). Volume `saganta_assets-data` und die
  SOPS-Datei `infra/secrets/vault/assets-api.env.enc` stehen noch.
- **Stufe 3, 2026-11-01:** gebaut (Migration 0008, 181 Tests, darunter
  hin und zurück an einem Bestand im Stand 0007). `platz`, `sache` (aus
  `electronic_asset`, Zeilennummern bleiben), `verlauf`; Posten am Platz, der
  Ortstext fällt. Eingang „Plätze" mit Raumbaum, Etiketten (QR mit der Kennung,
  Bogen wie medien), Umziehen und Umbenennen; Seite „Shopfloor"; Kleidung und
  Saison offen als Kisten-Bereiche; Einbuchen wählt einen Platz oder „noch nicht
  einlagern"; Sachen bekommen Platz und Verbleib. Die Lager-App bucht weiter mit
  Ortstext ein (wird ein Raum gleichen Namens) und zeigt Kisten-Bereiche bis zum
  nächsten Bau unter „Kommt noch".
  Nach der Migration live erwartet: zwei Räume (Kühlschrank `L-001`,
  Vorratskammer `L-002`) mit allen 24 Posten, 9 Sachen auf dem Shopfloor
  „Im Einsatz", 1 Sache „noch nicht eingelagert".
- **Stufe 4, 2026-11-01:** live seit 13:57 (Owner-Freigabe nach grüner Probe).
  Gesichert vorher nach `~/backups/lager-vor-stufe4-2026-11-01/app.db` (Stand
  0008, 10 Sachen, 24 Posten). Nach der Migration: alle 10 Sachen mit Kennung
  `S-0001` bis `S-0010`, eindeutig nur noch Seriennummer und Kennung. Migration 0009: `einkauf`, `preis`/`eingangsmenge`/
  `einkauf_id` am Posten, `kennung`/`foto`/`einkauf_id` an der Sache, der
  eindeutige Strichcode an der Sache fällt. `/api/laeufe/einbuchen`, `/abschluss`,
  `/lagern`, `/api/einkaeufe`, Fotos unter `/api/sachen/<id>/foto` (Ablage
  `fotos/` im Volume, im Löschweg des Kontos). Oberfläche: Einbuch-Lauf je
  Bereich (`/b/<bereich>/lauf`, für Vorrat und Sachen; „Einbuchen" in der
  Leiste führt dorthin, das Formular bleibt über einen Link), Lagern-Lauf
  `/lagern` mit Pin, Scanner-Bühne mit Kamera (BarcodeDetector, sonst zxing aus
  dem Haus) und Foto aus dem Strom, Etiketten und Fotos auf der Sachen-Seite.
  214 Tests (33 neu). Die klickende Probe `scripts/lauf-probe.sh` lief ohne
  Befund (40 Prüfungen); die Sichtprobe fand vorher vier Dinge, die keine
  Prüfung sah („2 piece“, zu schmale Einheitenwahl, abgeschnittene Namen und
  Platzhalter).
  **Offen:** Auswertungen zu den Preisen (Ausgaben je Monat, Verlust in Euro,
  Preis je Produkt), Projectdeck-Aufgabe 177: die Daten werden ab jetzt
  erfasst, gezeigt wird noch nichts.
- **Stufe 5a, 2026-11-01:** Owner-Runde: 5a/5b getrennt, **eine Zustandsskala**
  für alle Sachen (Neu · Sehr gut · Gut · Gebraucht · Beschädigt · Ungeprüft),
  **Shopfloor-Gründe je Bereich** (Filme: Rippen · Schauen · Verkauf vorbereiten).
  Entscheid ohne Frage: **nur das Lager ruft medien** (Titel suchen/anlegen,
  Spiegel des Bestands), ein Schlüssel. **Lager-Seite gebaut, nicht live**
  (`235f1de`, Migration 0010, 229 Tests): Bereich `medien` (Bauart `exemplar`),
  Titelsuche im Lauf, Staffel aus der Hülle, Spiegel-Läufer, Treffer im Lauf nur
  im eigenen Bereich. **medien-Seite halb**, auf dem Ast `lager-spiegel` in
  medien (`082d227`, ohne Tests): Tabellen `lager_bestand`/`lager_stand`, drei
  Maschinenwege mit `X-Lager-Token`, Fehlt-Liste mit Lager-Stücken.
  Die Handlungssätze der medien-Startseite bleiben bewusst bei den eigenen
  Exemplaren: sie führen in Seiten, die Lager-Stücke nicht bewegen können.
  **Nachgezogen 2026-11-01 („Verbindung verbessern“):** medien-Seite fertig
  (Ast `lager-spiegel` `a6a8309`, 175 Tests, davon 10 neu): `/api/lager/stand`
  und der Satz „Stand von …“ in Fehlt noch und am Titel, Lager-Stücke im
  Titel-Dialog öffnen `lager.home.arpa/b/medien#S-0001` (vorher `#ex/NaN`).
  Lager (`9284d7c`, 234 Tests): **Einbuchen geht auch, wenn medien aus ist**,
  das Stück entsteht ohne `titel_id`, der Spiegel-Läufer trägt den Titel nach
  (vorher brach jeder Neustart von medien den Lauf ab); nach einem Fehlschlag
  1/2/4/8 min statt 15; die Kachel sagt, seit wann medien schweigt, und wie
  viele Stücke auf ihren Titel warten; der Name verweist auf den Titel in
  medien. Alarm `MedienLagerSpiegelVeraltet` (erst scharf mit Schlüssel).
  **Offen:** Handgriff `scripts/medien-schluessel.sh`, beide live,
  klickende Probe. Danach 5b.
- **Stufe 5b, medien-Seite, 2026-11-01:** „lager soll raus aus medien rein in
  saganta-lager“, „buchen, einlagern, auslagern, umlagern in saganta-lager“. In medien sind
  Einbuchen, Lagern, Shopfloor, Inventur, Scanner, Etiketten und Fotoaufnahme gelöscht
  (medien `docker/medien/RICHTUNG.md`), alte medien-Adressen führen hierher
  (`/b/medien/lauf`, `/lagern`, `/shopfloor`, Inventur vorerst `/plaetze`), ein Exemplar von
  Hand antwortet dort 409. **Offen:** Handgriff `scripts/medien-schluessel.sh`; der
  Verkauf von Lager-Stücken in medien (eigene Tabelle je Kennung, Abgang zurück ins Lager);
  Inventur hier (Stufe 8).
  **Nachgezogen am selben Tag:** medien führt Lager-Stücke jetzt als Exemplare
  (Verkauf dort, Lager-Felder dort gesperrt) und legt in medien gebuchte Abgänge
  unter `GET /api/lager/abgaenge` bereit (`X-Lager-Token`, liefert `kennung`,
  `abgang` Verkauft/Weg, `am`, `erloes`, `plattform`). Abholen und Ausbuchen
  gebaut mit Stufe 7a (2026-11-03, siehe dort).
- **Stufe 7a, 2026-11-03:** live (Auftrag „verbessere saganta lager“).
  Gesichert vorher nach `~/backups/lager-vor-stufe7a-2026-11-03/app.db` (Stand
  0010, 10 Sachen, 24 Posten). Migration 0011: `abgang` (verkauft, weg),
  `abgang_am`, `erloes`, `abgang_plattform` an der Sache; `verbleib` kennt
  „vermisst“ (behält den Platz, verliert den Grund). `POST`/`DELETE
  /api/electronics/<id>/abgang`, Gegenliste `?abgegangen=true`. Abgegangenes
  fällt aus jeder Liste (Bereichsliste, Platzinhalt, Belegung, Shopfloor, Suche,
  Portfolio, Verkaufskandidaten, Treffer im Lauf, Spiegel, Metrik
  `lager_geraete`), die Zeile bleibt. Ein Etikett oder eine Seriennummer einer
  abgegangenen Sache bucht im Lauf nichts (422 mit Datum). Ein Platz mit nur
  noch abgegangenen Sachen ist leer und löschbar; die Sachen verlieren dabei den
  Platz. Vermisst steht als Satz vor allem anderen auf der Startseite (blockiert).
  **Filme & Medien gehen nur in medien ab:** vor jedem Abzug holt der
  Spiegel-Läufer `GET /api/lager/abgaenge` und bucht hier aus (Verkauft mit
  Erlös, Datum, Plattform); Abgang und Zurücknehmen von Hand lehnt das Lager für
  Filme ab, sonst holte der nächste Abgleich ihn zurück. medien zeigt
  „Vermisst“ jetzt als Vermisst (fiel vorher auf „Shopfloor“). 260 Tests
  (11 neu). `scripts/lauf-probe.sh` klickt Vermisst, Verkauft mit Erlös und
  Zurücknehmen; **noch nicht gelaufen** (Handgriff).
  **Nachgezogen am selben Tag:** Ausbuch-Vorschlag nach 30 Tagen Vermisst
  (`AUSBUCHEN_NACH_TAGEN`, wie medien), gerechnet aus dem jüngsten
  Verlaufseintrag mit dem Wert „vermisst“; ohne Eintrag kein Datum. Satz
  `vermisst_lange` auf der Startseite, „seit …“ und „Als weg buchen?“ an der
  Sache (Formular mit „Weg“ vorbelegt). Gebucht wird nie von selbst.
  Lager-App 0.5.0 (saganta-apps `5dab24d`): Vermisst und Abgang im
  Sachen-Blatt, Hinweis nach 30 Tagen, Filme nur in medien; Platz-Dinge und
  Suche tragen dafür `verbleib` (lager `c7e7941`). Gebaut und geprüft, das
  Ausliefern ist ein Handgriff.
  **Offen:** Erlös in den Preis-Auswertungen (Aufgabe 177).
