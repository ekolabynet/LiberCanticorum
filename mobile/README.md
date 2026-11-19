# Liber Canticorum Mobile (PWA)

**PL** · Aplikacja na telefon i tablet (Android, iPhone/iPad, każda przeglądarka) – instalowana ze strony
<https://ekolabynet.github.io/LiberCanticorum/>, działa bez internetu.

**EN** · A phone and tablet app (Android, iPhone/iPad, any browser) installed from the page above. It works offline.

## Co potrafi / Features

- lista pieśni z wyszukiwaniem (bez polskich znaków) i filtrami kategorii oraz źródła (śpiewnika);
- tekst dużą czcionką, refren opcjonalnie po każdej zwrotce;
- akordy nad sylabami i akordy boczne (`‖`), transpozycja ±½ tonu, krzyżyki lub bemole, polskie (H, B, małe = moll) i angielskie nazwy;
- zestawy na Mszę z częściami i uwagami dla muzyków (wykonawca, tonacja, uwagi, na co zwrócić uwagę), przejście do następnej pieśni przesunięciem palca;
- nuty (strony PDF / zdjęcia) na pełnym ekranie: dotknięcie albo pedał Bluetooth (strzałki, PageDown) przewraca stronę;
- ekran nie wygasa, gdy pieśń jest otwarta; ciemny i jasny motyw; polski i angielski.

## Skąd pieśni / Where the songs come from

Aplikacja **nie zawiera żadnych pieśni**. Wpisujesz je sam w programie Liber Canticorum na komputerze, a potem przenosisz plikiem `*.lcm.json`:

1. Na komputerze wybierz **Plik → 📱 Eksport do aplikacji mobilnej**, albo w pilocie na telefonie **⇩ Offline → Biblioteka do aplikacji**.
2. Prześlij plik na telefon (e-mail, komunikator, kabel), jeśli nie pobrałeś go pilotem.
3. W aplikacji wybierz **📥 Importuj** i wskaż plik.

Dane zostają tylko na urządzeniu (IndexedDB) – aplikacja niczego nie wysyła.

The app **ships with no songs**. You enter them in Liber Canticorum on your computer and bring them over as an `*.lcm.json` file:

1. On the computer, choose File → 📱 Export to the mobile app, or in the phone remote choose ⇩ Offline → Library for the app.
2. Send the file to the phone (e-mail, messenger, cable) if the remote did not download it there.
3. In the app, tap 📥 Import and pick the file.

The data stays on the device and the app sends nothing anywhere.

## Instalacja na Androidzie / Installing on Android

Otwórz stronę w Chrome, a potem wybierz menu ⋮ → **Zainstaluj aplikację** (albo „Dodaj do ekranu głównego”).
Na iPhonie: Safari → Udostępnij → **Do ekranu początkowego**.

On Android, open the page in Chrome and choose ⋮ → Install app. On iPhone, use Safari → Share → Add to Home Screen.

## Format pliku `.lcm.json`

```json
{"format": "liber-canticorum-mobile", "version": 1, "app": "0.29.0", "made": "2026-11-19T12:00:00",
 "songs": [{"id": 1, "title": "…", "cat": "…", "src": "…", "tags": "…", "notes": "…",
            "ref": ["wiersz refrenu"], "verses": [["wiersz", "wiersz"]], "chords": "ChordPro z [akordami] i ‖ akordami bocznymi",
            "youtube": ["https://…"], "scores": [{"name": "…", "pages": ["data:image/jpeg;base64,…"]}]}],
 "sets": [{"id": 3, "name": "…", "date": "2026-12-06", "time": "12:00", "place": "…", "okres": "…", "day": "…",
           "parts": [{"part": "Wejście", "items": [{"id": 1, "title": "…", "notes": {"wykonawca": "…", "tonacja": "…", "uwagi": "…", "zwroc": "…"}}]}]}]}
```

Import „Dołącz / zaktualizuj” zastępuje pieśni i zestawy o tych samych `id`; „Zastąp wszystko” czyści bibliotekę.

## Rozwój / Development

Czysty HTML + JS, bez kompilacji. Lokalnie: `python3 -m http.server -d mobile 8000` i <http://localhost:8000/>.
`chords.js` to port `program/modul_akordy.py` (transpozycja sprawdzana na tych samych przypadkach co w Pythonie).
Publikacja: `.github/workflows/pages.yml` (GitHub Pages, źródło: GitHub Actions).

Licencja: GPL-3.0-or-later. Ikona: zob. `icons/LICENSE-ikona.txt`.
