<?php
/**
 * Anfrage-Formular: Verarbeitung
 *
 * - Nimmt Formulardaten + Foto-Uploads entgegen, validiert serverseitig,
 *   verschickt eine E-Mail an den Firmeninhaber und leitet zurück.
 * - Uploads werden NICHT dauerhaft auf dem Server gespeichert: sie werden
 *   direkt aus dem von PHP verwalteten temporären Upload-Pfad als
 *   E-Mail-Anhang gelesen und nie in ein eigenes Verzeichnis verschoben.
 *   PHP löscht die temporäre Datei automatisch am Ende des Requests.
 *
 * [PLATZHALTER] EMPFAENGER_EMAIL unten anpassen, sobald die geschäftliche
 * E-Mail-Adresse feststeht.
 */

declare(strict_types=1);

// --- Konfiguration -----------------------------------------------------

const EMPFAENGER_EMAIL = 'info@donau-entruempelung-regensburg.de'; // [PLATZHALTER]
const ABSENDER_ADRESSE  = 'formular@donau-entruempelung-regensburg.de'; // [PLATZHALTER] – muss zur eigenen Domain gehören
const REDIRECT_ZIEL     = '../index.html';

const MAX_DATEIEN   = 5;
const MAX_DATEIGROESSE = 5 * 1024 * 1024; // 5 MB
const ERLAUBTE_MIME_TYPEN = [
    'image/jpeg',
    'image/png',
    'image/heic',
    'image/heif',
    'application/pdf',
];
const ERLAUBTE_ENDUNGEN = ['jpg', 'jpeg', 'png', 'heic', 'heif', 'pdf'];

// --- Hilfsfunktionen -----------------------------------------------------

function redirect_mit_status(string $status): void
{
    header('Location: ' . REDIRECT_ZIEL . '?status=' . urlencode($status) . '#anfrage');
    exit;
}

/** Entfernt Zeilenumbrüche, um Header-Injection in E-Mails zu verhindern. */
function bereinige_header_wert(string $wert): string
{
    return trim(str_replace(["\r", "\n"], '', $wert));
}

/** Escaped einfachen Text für die Ausgabe im (Plaintext-)E-Mail-Body. */
function bereinige_text(string $wert): string
{
    return trim($wert);
}

// --- Nur POST erlaubt ------------------------------------------------

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('HTTP/1.1 405 Method Not Allowed');
    exit('Methode nicht erlaubt.');
}

// --- Honeypot: stilles Verwerfen (kein Hinweis für Bots) ---------------

if (!empty($_POST['firma_webseite'])) {
    redirect_mit_status('success');
}

// --- Pflichtfelder validieren ------------------------------------------

$fehler = [];

$art = $_POST['art'] ?? '';
if (!in_array($art, ['privat', 'gewerblich'], true)) {
    $fehler[] = 'art';
}

$objektart = $_POST['objektart'] ?? '';
$ERLAUBTE_OBJEKTARTEN = ['haus', 'wohnung', 'keller', 'garage', 'gewerbeeinheit', 'sonstiges'];
if (!in_array($objektart, $ERLAUBTE_OBJEKTARTEN, true)) {
    $fehler[] = 'objektart';
}

$wohnflaeche = filter_var($_POST['wohnflaeche'] ?? '', FILTER_VALIDATE_INT, [
    'options' => ['min_range' => 1, 'max_range' => 2000],
]);
if ($wohnflaeche === false) {
    $fehler[] = 'wohnflaeche';
}

$etage = $_POST['etage'] ?? '';
$ERLAUBTE_ETAGEN = ['keller', 'eg', '1og', '2og', '3og', '4og-plus'];
if (!in_array($etage, $ERLAUBTE_ETAGEN, true)) {
    $fehler[] = 'etage';
}

$aufzug = $_POST['aufzug'] ?? '';
if (!in_array($aufzug, ['ja', 'nein'], true)) {
    $fehler[] = 'aufzug';
}

$parken = $_POST['parken'] ?? '';
if (!in_array($parken, ['gut', 'mittel', 'schlecht'], true)) {
    $fehler[] = 'parken';
}

$adresse = bereinige_text((string) ($_POST['adresse'] ?? ''));
if ($adresse === '' || mb_strlen($adresse) > 200) {
    $fehler[] = 'adresse';
}

$plz = trim((string) ($_POST['plz'] ?? ''));
if (!preg_match('/^\d{4,5}$/', $plz)) {
    $fehler[] = 'plz';
}

$name = bereinige_text((string) ($_POST['name'] ?? ''));
if ($name === '' || mb_strlen($name) > 150) {
    $fehler[] = 'name';
}

$telefon = trim((string) ($_POST['telefon'] ?? ''));
if (!preg_match('/^[0-9+\/\s()\-]{5,25}$/', $telefon)) {
    $fehler[] = 'telefon';
}

$email = filter_var(trim((string) ($_POST['email'] ?? '')), FILTER_VALIDATE_EMAIL);
if ($email === false) {
    $fehler[] = 'email';
}

if (empty($_POST['dsgvo'])) {
    $fehler[] = 'dsgvo';
}

// Optionale Felder
$terminwunsch = trim((string) ($_POST['terminwunsch'] ?? ''));
if ($terminwunsch !== '' && !preg_match('/^\d{4}-\d{2}-\d{2}$/', $terminwunsch)) {
    $terminwunsch = '';
}
$freitext = bereinige_text((string) ($_POST['freitext'] ?? ''));
if (mb_strlen($freitext) > 3000) {
    $freitext = mb_substr($freitext, 0, 3000);
}

// Zusätzlich gewünschte Leistungen (Checkboxen, alle optional)
$ERLAUBTE_ZUSATZLEISTUNGEN = [
    'tapeten-teppich'  => 'Tapeten-/Teppichentfernung',
    'umzug'            => 'Umzug',
    'einlagerung'      => 'Einlagerung',
    'gebaeudereinigung'=> 'Gebäudereinigung',
    'fenster-glas'     => 'Fenster- & Glasreinigung',
    'treppenhaus'      => 'Treppenhausreinigung',
    'bauendreinigung'  => 'Sonder-/Bauendreinigung',
];
$zusatzleistungen = [];
if (!empty($_POST['zusatzleistungen']) && is_array($_POST['zusatzleistungen'])) {
    foreach ($_POST['zusatzleistungen'] as $wert) {
        if (isset($ERLAUBTE_ZUSATZLEISTUNGEN[$wert])) {
            $zusatzleistungen[] = $ERLAUBTE_ZUSATZLEISTUNGEN[$wert];
        }
    }
}

if (!empty($fehler)) {
    redirect_mit_status('error');
}

// --- Datei-Uploads validieren -------------------------------------------

$anhaenge = []; // ['pfad' => tmp_name, 'name' => sicherer_dateiname, 'mime' => ...]

if (!empty($_FILES['fotos']) && is_array($_FILES['fotos']['tmp_name'])) {
    $anzahl = count(array_filter($_FILES['fotos']['tmp_name']));

    if ($anzahl > MAX_DATEIEN) {
        redirect_mit_status('error');
    }

    $finfo = finfo_open(FILEINFO_MIME_TYPE);

    foreach ($_FILES['fotos']['tmp_name'] as $index => $tmpName) {
        if ($tmpName === '' || $_FILES['fotos']['error'][$index] === UPLOAD_ERR_NO_FILE) {
            continue;
        }

        if ($_FILES['fotos']['error'][$index] !== UPLOAD_ERR_OK) {
            redirect_mit_status('error');
        }

        if (!is_uploaded_file($tmpName)) {
            redirect_mit_status('error');
        }

        if ($_FILES['fotos']['size'][$index] > MAX_DATEIGROESSE) {
            redirect_mit_status('error');
        }

        $mimeTyp = finfo_file($finfo, $tmpName);
        $originalName = (string) $_FILES['fotos']['name'][$index];
        $endung = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));

        if (!in_array($mimeTyp, ERLAUBTE_MIME_TYPEN, true) || !in_array($endung, ERLAUBTE_ENDUNGEN, true)) {
            redirect_mit_status('error');
        }

        // Dateiname serverseitig neu generieren (keine Originalnamen übernehmen)
        $sicherer_name = 'foto-' . bin2hex(random_bytes(8)) . '.' . $endung;

        $anhaenge[] = [
            'pfad' => $tmpName,
            'name' => $sicherer_name,
            'mime' => $mimeTyp,
        ];
    }

    finfo_close($finfo);
}

// --- E-Mail zusammenstellen ---------------------------------------------

$boundary = 'DER-' . bin2hex(random_bytes(16));

$betreff = 'Neue Anfrage (' . ($art === 'gewerblich' ? 'Gewerblich' : 'Privat') . ') – ' . $plz;
$betreff = bereinige_header_wert($betreff);

$ETAGEN_LABEL = [
    'keller' => 'Keller', 'eg' => 'Erdgeschoss', '1og' => '1. OG', '2og' => '2. OG',
    '3og' => '3. OG', '4og-plus' => '4. OG oder höher',
];
$OBJEKTART_LABEL = [
    'haus' => 'Haus', 'wohnung' => 'Wohnung', 'keller' => 'Keller',
    'garage' => 'Garage', 'gewerbeeinheit' => 'Gewerbeeinheit', 'sonstiges' => 'Sonstiges',
];

$body = "Neue Anfrage über das Website-Formular\n";
$body .= "========================================\n\n";
$body .= "Art: " . ($art === 'gewerblich' ? 'Gewerblich' : 'Privat') . "\n";
$body .= "Objektart: " . $OBJEKTART_LABEL[$objektart] . "\n";
$body .= "Wohn-/Nutzfläche: {$wohnflaeche} m²\n";
$body .= "Etage: " . $ETAGEN_LABEL[$etage] . "\n";
$body .= "Aufzug vorhanden: " . ($aufzug === 'ja' ? 'Ja' : 'Nein') . "\n";
$body .= "Parksituation: " . ucfirst($parken) . "\n";
$body .= "Adresse: {$adresse}\n";
$body .= "PLZ: {$plz}\n";
$body .= "Terminwunsch: " . ($terminwunsch !== '' ? $terminwunsch : '(keine Angabe)') . "\n\n";
$body .= "Gewünschte Zusatzleistungen: " . (empty($zusatzleistungen) ? '(keine)' : implode(', ', $zusatzleistungen)) . "\n\n";
$body .= "Name: {$name}\n";
$body .= "Telefon: {$telefon}\n";
$body .= "E-Mail: {$email}\n\n";
$body .= "Nachricht:\n" . ($freitext !== '' ? $freitext : '(keine Angabe)') . "\n\n";
$body .= "Anzahl angehängter Fotos: " . count($anhaenge) . "\n";

$headers = [];
$headers[] = 'From: Donau Entrümpelung Website <' . ABSENDER_ADRESSE . '>';
$headers[] = 'Reply-To: ' . bereinige_header_wert($email);
$headers[] = 'MIME-Version: 1.0';

if (empty($anhaenge)) {
    $headers[] = 'Content-Type: text/plain; charset=UTF-8';
    $nachricht = $body;
} else {
    $headers[] = 'Content-Type: multipart/mixed; boundary="' . $boundary . '"';

    $nachricht = "--{$boundary}\r\n";
    $nachricht .= "Content-Type: text/plain; charset=UTF-8\r\n\r\n";
    $nachricht .= $body . "\r\n";

    foreach ($anhaenge as $anhang) {
        $inhalt = file_get_contents($anhang['pfad']);
        if ($inhalt === false) {
            continue;
        }
        $nachricht .= "--{$boundary}\r\n";
        $nachricht .= 'Content-Type: ' . $anhang['mime'] . '; name="' . $anhang['name'] . "\"\r\n";
        $nachricht .= "Content-Transfer-Encoding: base64\r\n";
        $nachricht .= 'Content-Disposition: attachment; filename="' . $anhang['name'] . "\"\r\n\r\n";
        $nachricht .= chunk_split(base64_encode($inhalt));
    }

    $nachricht .= "--{$boundary}--";
}

$erfolg = mail(EMPFAENGER_EMAIL, $betreff, $nachricht, implode("\r\n", $headers));

// Hinweis: PHP entfernt die tmp_name-Dateien der Uploads automatisch nach
// Ende des Requests – es findet keine dauerhafte Speicherung statt.

redirect_mit_status($erfolg ? 'success' : 'error');
