# Donau Entrümpelung Regensburg — Website

Statische One-Page-Website (HTML/CSS/JS) mit PHP-Formular-Backend für die
Entrümpelungsfirma "Donau Entrümpelung Regensburg". Kein CMS, keine
Datenbank — kleine Angriffsfläche, ausreichend für eine selten geänderte Seite.

## Struktur

```
donau-entruempelung/
├── index.html                     One-Pager mit Anker-Navigation
├── impressum.html                 Impressum (mit Platzhaltern)
├── datenschutz.html               Datenschutzerklärung (mit Platzhaltern)
├── css/styles.css                 Gesamtes Styling
├── js/main.js                     Mobile Nav, Formular-Statusmeldung, Upload-Vorprüfung
├── php/anfrage-verarbeiten.php    Serverseitige Formularverarbeitung + E-Mail-Versand
├── assets/logo-donau-entruempelung.svg
├── .htaccess                      Security-Header (Apache/Hostinger)
└── robots.txt
```

## Vor dem Live-Gang noch zu erledigen

Alle mit `[PLATZHALTER]` bzw. `.placeholder` markierten Stellen ersetzen:

- [ ] Domain buchen (z. B. `donau-entruempelung-regensburg.de`)
- [ ] Hosting bei Hostinger einrichten (PHP-Support erforderlich)
- [ ] Telefonnummer in `index.html`, `impressum.html` (Suche nach `PLATZHALTER`/`placeholder`)
- [ ] WhatsApp-Business-Nummer im WhatsApp-Banner (`index.html`, `wa.me/49PLATZHALTER`)
- [ ] Geschäftliche E-Mail-Adresse in `index.html`, `impressum.html`, `datenschutz.html`
      sowie in `php/anfrage-verarbeiten.php` (`EMPFAENGER_EMAIL`, `ABSENDER_ADRESSE` —
      die Absenderadresse muss zur eigenen Domain gehören, sonst landen Mails im Spam)
- [ ] Anschrift (Straße, PLZ) in `index.html`, `impressum.html`
- [ ] USt-IdNr. und Inhaber-Name in `impressum.html`
- [ ] Aufbewahrungsdauer der E-Mail-Anfragen in `datenschutz.html`
- [ ] Echte Fotos von Team/Transporter ergänzen (aktuell bewusst nur Icons, keine Fake-Fotos)
- [ ] Impressum & Datenschutzerklärung von einem Anwalt/einer IHK-Vorlage final
      prüfen lassen — insbesondere wegen der Foto-Uploads im Formular
- [ ] `.htaccess`: HTTPS-Weiterleitung aktivieren, sobald das SSL-Zertifikat aktiv ist

## Formular / Sicherheit

- Serverseitige Validierung aller Felder (Pflichtfelder, PLZ-Format, E-Mail, etc.)
- Datei-Uploads: max. 5 Dateien, je max. 5 MB, nur JPG/PNG/HEIC/PDF —
  MIME-Typ wird serverseitig per `finfo` geprüft (nicht nur Dateiendung)
- Dateinamen werden serverseitig neu generiert, Originalnamen werden verworfen
- Uploads werden **nicht dauerhaft gespeichert** — sie werden direkt aus dem von
  PHP verwalteten temporären Pfad als E-Mail-Anhang verschickt und danach von
  PHP automatisch gelöscht
- Honeypot-Feld (`firma_webseite`) gegen einfache Bots, kein Captcha
- Alle E-Mail-Header werden von Zeilenumbrüchen bereinigt (Schutz vor Header-Injection)

## Lokale Vorschau

Die Seite ist rein statisch (bis auf das PHP-Formular) und lässt sich direkt
im Browser öffnen (`index.html`) oder mit einem lokalen PHP-Server testen:

```bash
cd donau-entruempelung
php -S localhost:8000
```

Das Formular selbst versendet nur dann E-Mails, wenn der Server über einen
funktionierenden Mailversand (z. B. `sendmail`/SMTP, wie bei Hostinger
üblich) verfügt.
