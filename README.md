<p align="center"><img src="ikony/liber_canticorum_128.png" width="128" alt="Liber Canticorum"></p>

# Liber Canticorum 0.12.0
*wolny śpiewnik dla wspólnot*

*Liber canticorum* to po łacinie „księga pieśni”. *Liber* znaczy „księga”, a zarazem przywodzi na myśl
*libre*, czyli „wolny”, jak wolne oprogramowanie. Ikona to czerwone inicjałowe **C** z rękopiśmiennego
czeskiego kancjonału z 1586 roku (*Cantional písnek rozmaitých a nábožných*), postawione na karcie pergaminu.

Program do przygotowywania i wyświetlania slajdów z tekstami pieśni (rzutnik, ekran w kościele),
z nutami, odtwarzaczem głosów, pilotem w telefonie i śpiewnikiem offline. To następca wersji „Śpiewnik – slajdy” 7.x.
Działa na Windows, macOS i Linux. Startuje z pustą bazą: teksty, nuty i nagrania wpisujesz i dodajesz sam.

**Numeracja wersji.** Od wersji 0.9.7 program ma numerację 0.x.y (wcześniejsze wydania nosiły numery 7.x–9.7).
0.x oznacza, że program wciąż szybko się rozwija; kolejne wydania to 0.10.x, 0.12.0 itd.

## Instalacja i uruchomienie

Po rozpakowaniu w folderze są tylko programy do uruchamiania i ten folder `program`:

```
LiberCanticorum_0.12.0/
├── Liber Canticorum.bat       ← Windows (po 1. starcie obok pojawi się skrót z ikoną)
├── Liber Canticorum.desktop   ← Linux (ikona pojawi się po 1. starcie)
├── Liber Canticorum.command   ← macOS
├── PRZECZYTAJ.txt
└── program/                   ← kod, ikony, tła, baza pieśni, ta dokumentacja
```

Program uruchamiający (`program/uruchom.py`) przy pierwszym starcie tworzy środowisko z bibliotekami
i pokazuje okienko z postępem (w Linuksie bez Tkintera – okno terminala). Trwa to kilka minut i wymaga internetu.
Później program startuje od razu; po aktualizacji brakujące biblioteki doinstalują się same.
W Windows uruchamiający tworzy w folderze skrót „Liber Canticorum” z ikoną (i odświeża go po przeniesieniu folderu),
a pliki dla innych systemów ukrywa. W Linuksie wpisuje ikonę do pliku `.desktop` i chowa pliki innych systemów.

Z terminala: `program/start.sh` (Linux, macOS) albo `program\start.bat` (Windows).

**Skrót w menu i na pulpicie:** `python3 program/uruchom.py --skrot` (Windows: `program\start.bat skrot`).

**Środowisko z bibliotekami jest wspólne dla wszystkich wersji** (od 8.5):
- Linux / macOS: `~/.local/share/LiberCanticorum/venv`, Windows: `%LOCALAPPDATA%\LiberCanticorum\venv`.
- Nowa wersja programu nie pobiera więc ponownie ok. 600 MB bibliotek, tylko doinstalowuje to, co się zmieniło.
- Przy pierwszym uruchomieniu skrypt startowy znajduje `.venv` z poprzedniej instalacji (folder obok)
  i proponuje **przeniesienie** go, co trwa chwilę i nic nie pobiera.

**Przejście z poprzedniej wersji (7.x „Śpiewnik – slajdy” albo wcześniejsza 8.x/9.0):**
- Rozpakuj nową wersję obok starej i uruchom „Liber Canticorum”. Środowisko przeniesie się samo, jak wyżej.
- Przy pierwszym uruchomieniu program przejmie ustawienia oraz zrobi **kopię** bazy pieśni
  ze starego folderu. Stara baza zostaje nietknięta.
- Później w każdej chwili: **Plik → Importuj z poprzedniej instalacji**. Program pokaże bazy znalezione obok
  (z liczbą pieśni i datą), a do wyboru są dwie opcje:
  - **„Dołącz pieśni”:** dodaje pieśni, których jeszcze nie ma, razem z nutami, nagraniami i podglądami MuseScore.
    Do pieśni o tym samym tytule dokłada brakujące załączniki i uzupełnia pustą kategorię, tagi i nagrania.
    Ponowny import niczego nie dubluje. Działa też ze starymi bazami z wersji 7.0,
  - **„Zastąp bieżącą bazę”:** bieżąca baza zostaje zapisana jako kopia zapasowa `.bak-data`,
  - opcjonalnie przenosi też ustawienia: motywy, zestaw, ścieżkę do MuseScore, SoundFont.
- Bazę zapisaną w innym miejscu otworzysz w menu Plik → Otwórz / utwórz inną bazę.

- **Linux / macOS:** `./start.sh` (za pierwszym razem `chmod +x start.sh`).
  Na Debianie, Ubuntu i Mincie mogą być potrzebne pakiety systemowe:
  `sudo apt install python3-venv libportaudio2`.
- **Windows:** dwuklik na `start.bat`. Potrzebny jest Python z python.org z zaznaczonym „Add python.exe to PATH”.

Opcjonalnie możesz doinstalować **odtwarzacz YouTube wbudowany w program** (ok. +250 MB).
Bez niego nagrania otwierają się w przeglądarce.

- Linux / macOS: `./start.sh --odtwarzacz`
- Windows: `start.bat odtwarzacz` (z wiersza poleceń)

Ręcznie wygląda to tak:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt            # Windows: .venv\Scripts\pip ...
.venv/bin/pip install -r requirements-odtwarzacz.txt  # opcjonalnie
.venv/bin/python liber_canticorum.py
```

Żeby odinstalować, usuń folder `.venv`.

## Pliki

| Plik | Co to jest |
|---|---|
| `liber_canticorum.py` | program główny |
| `modul_nuty.py` | wyszukiwanie nut (CPDL, MuseScore, IMSLP), podgląd nut, odtwarzacz MIDI z głosami |
| `modul_brzmienia.py` | brzmienia odtwarzacza: odtwarzacz SoundFont (.sf2/.sf3) – chór, organy |
| `modul_youtube.py` | wyszukiwanie i odtwarzanie nagrań z YouTube |
| `modul_pilot.py` | pilot w telefonie lub tablecie przez Wi-Fi |
| `modul_html.py` | śpiewnik offline w jednym pliku HTML (telefon, tablet) |
| `ikony.py`, `ikony/` | ikony Font Awesome Free (SVG), barwione kolorem motywu |
| `generuj_tla.py` | generator teł; pozwala odtworzyć lub zmienić obrazy w `tla/` |
| `tla/` | 16 teł (11 ciemnych, 5 jasnych) w wersjach 16:9 i 4:3, `tla.json` z zalecanymi kolorami i marginesami |
| `liber_canticorum.db` | baza pieśni; tworzy się sama przy pierwszym uruchomieniu |
| `generuj_ikone.py` | generator ikony programu (inicjał C z kancjonału z 1586 r.): SVG, PNG, ICO |

## Co potrafi

**Baza pieśni.** Wszystko jest w jednym pliku `liber_canticorum.db` (SQLite): teksty, ustawienia i załączniki.
Inną bazę otworzysz w menu Plik.
- **Kategorie:** okres liturgiczny lub rodzaj, np. Adwent, Maryjne, Eucharystyczne. Można dopisywać własne.
  Lista pieśni jest pogrupowana według kategorii.
- **Tagi:** dowolne, po przecinku, np. *komunia, kanon, schola*. Program podpowiada istniejące tagi.
- **Wyszukiwanie** (Ctrl+F) przeszukuje tytuł, tekst, tagi i uwagi, bez względu na polskie znaki.
  Do tego dochodzą filtry według kategorii i tagu.

**Import:**
- z plików DOCX, ODT, PDF, TXT i HTML,
- ze strony WWW,
- z plików JSON z wersji 6.x.
- **zbiory pieśni**: strona lub plik z wieloma ponumerowanymi pieśniami (np. dział śpiewnika internetowego, jak
  „Pieśni na Adwent” w Śpiewniku ks. Siedleckiego) jest rozpoznawany jako zbiór. Program pokazuje listę znalezionych
  pieśni z podglądem, odznacza te, które już są w bazie, proponuje kategorię z nagłówka działu i zapisuje numer
  pieśni, dział i źródło w uwagach, a linki do nagrań – przy pieśni (opcjonalnie pobiera mp3 jako załączniki).
  Zapis „ * ” zamienia na podział wersów, rozpoznaje „Refren:”, „Antyfona:” i usuwa odsyłacze „Ref.” / „Ant.”.
- **ze słów pod nutami** (Plik → Importuj słowa z nut): MuseScore 3 i 4 (.mscz, .mscx), MusicXML (.musicxml, .mxl),
  MIDI z tekstem (.mid, .kar) i PDF z nutami (np. wydruk z MuseScore). MuseScore nie jest do tego potrzebny.
  Program składa sylaby w słowa, rozdziela zwrotki, rozpoznaje refren (fragment, pod którym jest tylko jedna linijka
  słów, choć gdzie indziej jest ich więcej) i dzieli tekst na wiersze po interpunkcji. Zwrotki wydrukowane zwykłym
  tekstem pod nutami w PDF też są dołączane. Wynik zawsze pokazuje się w oknie importu do poprawienia,
  a plik nut zostaje dołączony do pieśni po jej zapisaniu.
  Ze skanów (PDF bez warstwy tekstu) słów odczytać się nie da.
- **znane pieśni, wersje i aranżacje.** Przy imporcie i przy zapisie nowej pieśni program szuka w bazie tej samej
  pieśni (ten sam lub podobny tytuł, ten sam początek tekstu, tytuł = pierwszy wiersz drugiej). Można wtedy dodać
  pieśń jako nową albo **dołączyć do istniejącej**: inny tekst zapisuje się jako *wersja tekstu* (np. „Śpiewnik
  oazowy 2026, s. 5”), plik nut – jako kolejna *aranżacja* z opisem, a tagi, uwagi, nagrania i źródła się sumują.
  Ponowny import tego samego śpiewnika niczego nie dubluje. W zakładce „Nuty, wersje i nagrania” są wersje tekstu
  (podgląd z porównaniem różnic, „Ustaw jako tekst główny” – poprzedni tekst staje się wersją, nic nie ginie)
  i opis wersji/aranżacji każdego pliku (Melodia, Chór SATB, Organy…). Dwie pieśni, które już są w bazie
  osobno, łączy Pieśń → Połącz z inną pieśnią – zestawy na Mszę wskazują potem na pieśń wynikową.
- **Wygląd slajdów dla wszystkich pieśni:** w zakładce „Wygląd slajdów” przycisk „Zastosuj do wszystkich pieśni
  w bazie…” (numerowanie zwrotek każda pieśń zachowuje swoje); „Ustaw jako domyślne” zapisuje się od razu.
- **Cofnij ostatnie zmiany w bazie** (Plik, Ctrl+Shift+Z): przed każdym importem, łączeniem, zamianą tekstu
  i usunięciem pieśni program robi kopię bazy (ostatnie 8, w ukrytym folderze obok bazy). Z listy wybiera się
  zmianę – baza wraca do stanu sprzed niej; bieżący stan też zostaje zachowany, więc cofnięcie można cofnąć.
- **Akordy – widok dla gitarzystów** (zakładka „Akordy”, Pieśń → Akordy, Ctrl+G): tekst z akordami w zapisie
  ChordPro – „[a]Chwalcie [E]Pana” (akord przed sylabą) albo z boku wiersza po „‖”: „Pozdrawiam Cię, Matko ‖ D e / A D”.
  Widok pokazuje akordy nad sylabami, ma transpozycję (± półtony, krzyżyki albo bemole), wielkość pisma, pełny
  ekran, przechodzenie po pieśniach zestawu (Pieśń → Akordy całego zestawu) i zapis do PDF. Polska notacja
  (H, B, moll małą literą, „is”/„es”) i angielska (B, Bb, Am). Tekst z wierszami akordów nad słowami (wklejony
  albo z pliku TXT/DOCX) zamienia się na ChordPro automatycznie przy imporcie albo przyciskiem. Slajdy pokazują
  sam tekst. Śpiewnik offline HTML (telefon) ma przycisk „🎸 Akordy” z transpozycją.
- **ze śpiewnika PDF, w którym nuty są obrazkami** (np. śpiewnik mszalny zrobiony w calibre – tekstem są tylko
  nagłówki): każda część staje się pieśnią „Msza Rycerska – Kyrie” z kategorią „Części stałe Mszy”, tagami
  „kyrie” i „Msza Rycerska” (zestaw na Mszę od razu proponuje tę mszę jako motyw części stałych) i nutami
  w załączniku PDF – wycięte są tylko systemy tej części, nie całe strony. Nagłówek największy to nazwa mszy,
  średni – podtytuł (np. „In festis duplicibus”), najmniejszy – część; rubryki trafiają do uwag. Jeśli na komputerze
  jest program **tesseract** (OCR, z językiem polskim), program odczytuje też autorów („m.: J. Gałuszka”) i szkic słów
  spod nut – szkic jest zwykle niepełny, więc wstawia się go tylko po zaznaczeniu opcji w oknie importu.
- **ze śpiewnika tekstowego PDF** (setki pieśni: „123. Tytuł”, zwrotki, refreny, akordy z boku – np. śpiewnik
  oazowy złożony w InDesignie): tytuły są rozpoznawane po kroju i wielkości pisma, a nie tylko po numerze,
  więc „1.” zwrotki nie myli się z „1.” pieśni i pieśni się nie zlewają. Akordy (także „(H7) E A H7…”, „/x2”),
  żywa pagina, numery stron, litery działów na marginesie, sentencje w stopce i ramki z boku (np. wersja
  hiszpańska) są pomijane – akordy trafiają do zakładki „Akordy” (nad sylabami, gdy stały nad tekstem, albo
  z boku wiersza). Śpiewniki bez numerów (tytuły kapitalikami, np. „Woda Życia”) też są rozpoznawane – tytuły
  sprawdzane ze spisem treści. Numer pieśni trafia do uwag („…, nr 356”).
- **ze śpiewnika PDF z nutami** (np. śpiewnik oazowy – wiele pieśni, każda z tytułem, autorami, nutami ze słowami
  i dalszymi zwrotkami pod spodem): wystarczy zaimportować plik PDF. Program sam rozpoznaje, że to śpiewnik,
  i pokazuje listę pieśni do zaznaczenia. Z każdej strony bierze tytuł (wiersz nad „t.: … m.: …”), autorów
  (do uwag), dział i poddział (np. „Śpiewy na Eucharystię – Procesja wejścia” → tag „wejście”), refren i 1. zwrotkę
  spod nut (bez akordów i numerów taktów), dalsze zwrotki z tekstu pod nutami – także z następnej strony.
  Kilka pieśni na jednej stronie (np. „Święty” i „Baranku Boży” pod Kyrie) jest rozdzielanych po tytułach
  z autorami albo po tytule tuż nad nutami. Gdy nuty są obrazkiem, pieśń dostaje tytuł i stronę PDF,
  a w uwagach informację, że słów nie dało się odczytać.
  Strony z nutami danej pieśni mogą trafić do niej jako załącznik PDF (duże obrazki są przy tym zmniejszane).
  Ukryte, przycięte warstwy tekstu (częste w plikach z programów DTP) są pomijane. Słowa spod nut zależą od
  odstępów w pliku – czasem dwa słowa się skleją („namradosną”), więc warto je przejrzeć.
- z nut już dołączonych do pieśni: zakładka „Nuty i nagrania” → „Słowa z tych nut → do tekstu pieśni”.

Program sam rozpoznaje refren („Ref.”) i zwrotki („1.”, „2.”).

**Slajdy.** Podgląd zmienia się na żywo. Do wyboru są:
- format 16:9 lub 4:3,
- automatyczny rozmiar czcionki,
- kolory tekstu, refrenu i tła,
- marginesy,
- **obrazy tła**, jasne lub ciemne (szczegóły niżej w części „Tła”).

**Pokaz** (F5) wyświetla się na pełnym ekranie, domyślnie na drugim monitorze (rzutniku).

| Klawisz | Działanie |
|---|---|
| → / spacja / PgDn | dalej |
| ← / PgUp | wstecz |
| B | czarny ekran |
| **C** | **czyste tło** (bez tekstu) |
| Esc | koniec pokazu |

**Dane Mszy i zapisane zestawy.** Nad zestawem wpisujesz dzień, godzinę i miejsce; okres liturgiczny i rok czytań
(A/B/C, I/II) program wylicza sam z daty (można zmienić). Przycisk 💾 zapisuje zestaw w bazie, lista „Zestaw:”
pokazuje zapisane (najnowsze u góry), ✚ zaczyna nowy.

**Zestaw bez okazji.** W polu rodzaju wybierz „Bez okazji”: zamiast części Mszy jest jedna lista utworów
(koncert, próba, nabożeństwo) z nazwą, datą i miejscem; kolejność zmieniasz przeciąganiem. Pieśni przechodzą
między rodzajami bez utraty, a zapisane zestawy bez okazji mają na liście znak ♪.

**Pojedyncza pieśń dla niewidomych:** Pieśń → „♿ Eksport dla niewidomych” (Ctrl+Shift+D, przycisk „Niewidomi”
na pasku) – ten sam DOCX/TXT/HTML z nagłówkami, refrenem i zwrotkami, bez liturgii.

**📖 Liturgia dnia i propozycje.** Program pobiera teksty Mszy z danego dnia: antyfony na wejście i na Komunię,
kolektę, czytania, psalm z refrenem, aklamację, Ewangelię, modlitwę nad darami, prefację i modlitwę po Komunii.
Źródła: gregorianski.pl (pełny mszalik), niezbednik.niedziela.pl i opoka.org.pl (czytania); domyślnie program
próbuje po kolei i uzupełnia brakujące części. Pobrana liturgia zostaje w bazie, więc potem działa bez internetu.
Obok tekstów program pokazuje pieśni z Twojej bazy, które nawiązują do słów i fraz liturgii (np. refren psalmu,
antyfona, Ewangelia), z podpowiedzią, do której części Mszy pasują; ★ oznacza pieśń z kategorii bieżącego okresu.
Jedno kliknięcie dodaje pieśń do zestawu. Teksty liturgiczne należą do wydawców (Pallottinum/KEP) –
program ich nie rozpowszechnia, tylko wyświetla je ze stron źródłowych.

**📦 Materiały…** (zestaw) i Pieśń → „Eksport materiałów” – wszystko do jednego folderu: teksty (DOCX, TXT, HTML),
slajdy (PDF, PPTX), nuty PDF (dołączone i przeliczone z MuseScore, także połączone w jeden plik), dołączone nagrania
i **nagrania do nauki** z nut. Przy nagraniach wybierasz **głosy** (S, A, T, B, inne) i **warianty**: całość,
głos z delikatnym podkładem harmonii, sam głos, oraz tempo z nut i/lub wolniejsze. Okno od razu pokazuje,
ile plików powstanie, i ostrzega, gdy jest ich za dużo. **♿ Dla niewidomych** to ten sam eksport z wersją
tekstów dla czytników ekranu (większa czcionka, DOCX + TXT, bez slajdów i obrazków).

**Szukaj w sieci** (Plik → „Szukaj w śpiewnikach internetowych i nut w MuseScore”, Ctrl+Shift+F):
1. *Teksty w śpiewnikach* – program pobiera spisy pieśni (Śpiewnik ks. Siedleckiego z tekstami, Śpiewnik
   Niezbędnika Katolika – tytuły, tekst na żądanie) i szuka w nich po tytule i słowach; wynik można zaimportować
   jako nową pieśń albo wstawić do bieżącej.
2. *Nuty w MuseScore* – wyniki z musescore.com w kolejności: **melodia** (jeden głos), potem aranżacje: chór,
   organy/fortepian, inne. Pobrany w przeglądarce plik dołączasz przyciskiem „Dołącz pobrany plik nut”.
3. *Dostępność dla bazy* – tabela dla wszystkich pieśni (albo bieżącej listy): czy tekst jest w śpiewnikach,
   ile jest nut-melodii i aranżacji w MuseScore; zapis do CSV. Zapytania idą co sekundę, żeby nie obciążać serwisu.

**♿ Dla niewidomych…** – naraz kilka formatów (DOCX, TXT, HTML) w jednym folderze, a do tego
**nagrania do nauki** (MP3) z nut dołączonych do pieśni (MIDI albo MuseScore): całość oraz każdy głos osobno
na delikatnym podkładzie całej harmonii (organy, fisharmonia, smyczki albo chór; głośność podkładu i tempo do wyboru).
Teksty podają nazwy plików z nagraniami przy każdej pieśni. Mszalik z pieśniami zestawu i (jeśli pobrana) liturgią dnia, ułożony w kolejności Mszy:
DOCX z prawdziwymi nagłówkami (czytniki ekranu: NVDA, JAWS, VoiceOver, TalkBack), TXT w UTF-8 dla notatników
i monitorów brajlowskich albo HTML do otwarcia w telefonie. Do wyboru pełne teksty, wersja skrócona lub same pieśni
oraz wielkość czcionki dla słabowidzących.

**Zestaw na Mszę** ma części: Przed mszą, Wejście, Kyrie, Gloria, Psalm (melodia), Alleluja (melodia aklamacji), Ofiarowanie, Sanctus, Agnus Dei, Komunia, Uwielbienie, Wyjście, Po mszy. Zaznacz część i kliknij „↓ Do zestawu” (bez zaznaczenia program sam rozpozna część po tytule lub tagu, np. „komunia”). Przy częściach z pieśniami możesz dodać kilka pieśni; części stałe oraz melodia psalmu i aklamacji przyjmują jedną pozycję. Części stałe najlepiej brać z jednej mszy: oznacz pieśni Kyrie/Gloria/Sanctus/Agnus Dei wspólnym tagiem (np. „Msza o Aniołach”) i wybierz ją w polu „Części stałe” – wypełni wszystkie cztery naraz. Pieśni przeciągasz między częściami; pokaz i eksport idą w kolejności Mszy, a w DOCX nagłówek mówi, na którą część jest pieśń.

**Eksport:**
- **PDF**, wygląda identycznie jak podgląd,
- **PPTX**, z tekstem do edycji,
- **DOCX dla osób niewidomych i słabowidzących** (szczegóły niżej).

**Eksport DOCX dla osób niewidomych i słabowidzących:**
- prawdziwe nagłówki: każda pieśń to nagłówek 1. poziomu, więc w czytniku ekranu przechodzi się między nimi klawiszem H,
- język dokumentu ustawiony na polski, żeby syntezator mowy dobrze wymawiał tekst,
- wersy w oryginalnym układzie, z oznaczeniami „Refren:”, „Zwrotka 1:” i „(Refren)” w miejscu powtórzenia,
- bez tabel, obrazów, kolorów i pustych akapitów; czcionka 14 pt,
- plik nadaje się też dla monitora brajlowskiego i do druku powiększonego.

**Nuty i nagrania** (zakładka przy każdej pieśni):
- **załączniki:** nuty PDF, pliki MuseScore (.mscz, .mscx), MusicXML, MIDI i nagrania audio.
  Zapisują się w bazie i otwierasz je jednym kliknięciem (np. .mscz w programie MuseScore),
- **Szukaj nut w sieci:**
  - **CPDL**, darmowa biblioteka nut chóralnych: wyszukiwanie w programie, lista plików utworu
    i pobranie ich prosto do pieśni,
  - **MuseScore, IMSLP, Google:** wyszukiwanie w przeglądarce, bo te serwisy nie mają otwartego API.
    Pobrany plik dodajesz przyciskiem „Dodaj pliki…”,
- **Odtwarzacz MIDI do nauki głosów:**
  - czterogłos jest rozpoznawany automatycznie jako sopran, alt, tenor i bas,
    także wtedy, gdy plik ma wszystkie głosy w jednej ścieżce jako akordy,
  - każdy głos można wyciszyć albo ustawić mu głośność,
  - tryb **„Ćwicz głos”**: wybrany głos gra głośno, pozostałe ciszej,
  - tempo od 25 do 200 % i transpozycja,
  - wałek pianoli z kursorem; kliknięcie przewija utwór,
  - zapis do WAV,
- **YouTube:**
  - wyszukiwanie w programie przez oficjalne API; potrzebny jest własny, darmowy klucz
    („YouTube Data API v3” z Google Cloud Console). Bez klucza wyszukiwanie otwiera się w przeglądarce
    i wklejasz link,
  - nagrania zapisane przy pieśni,
  - **Wideo:** odtwarzacz YouTube na pełnym ekranie rzutnika,
  - **Tylko dźwięk + czyste tło:** odtwarzacz w małym okienku na Twoim ekranie, a rzutnik pokazuje samo tło slajdu.

Odtwarzanie idzie przez oficjalny osadzony odtwarzacz YouTube. Program nie pobiera i nie wycina ścieżek
dźwiękowych, bo zabrania tego regulamin YouTube.
Publiczne odtwarzanie nagrań i wyświetlanie tekstów może wymagać zgody właścicieli praw (np. przez ZAiKS).
Za to odpowiada użytkownik.

## Nuty z MuseScore

Pliki **.mscz**, .mscx i MusicXML program **pokazuje**, ale ich nie edytuje.
Jeśli MuseScore 3 lub 4 jest zainstalowany na komputerze, program po dołączeniu pliku
w tle przelicza go do PDF (podgląd) i MIDI (odtwarzacz głosów).
Wynik zapisuje w bazie, więc te nuty widać potem także w pilocie i w śpiewniku offline,
gdzie MuseScore nie jest już potrzebny. Bez MuseScore widać miniaturę pierwszej strony.
MuseScore jest wyszukiwany automatycznie. Jeśli się nie znajdzie, wskaż go w menu Ustawienia → Ścieżka do MuseScore.

**MuseScore 4 na Linuksie (AppImage).** MuseScore 4 na Linuksie wydawany jest jako plik AppImage. Program:
- **sam go znajduje** w folderach `~/Applications`, `~/Aplikacje`, `~/Programy`, `~/AppImages`, `~/bin`,
  `~/Pobrane`, `~/Downloads`, `~/Pulpit`, `/opt` i innych. Gdy plików jest kilka, wybiera najnowszą wersję,
- **sam nadaje mu prawo do uruchamiania** (`chmod +x`), bo pobrane pliki zwykle go nie mają,
- **radzi sobie bez FUSE.** Nowsze Ubuntu i Mint nie mają domyślnie biblioteki `libfuse2`, bez której AppImage nie startuje.
  Program wtedy sam przełącza się na tryb bez FUSE (`APPIMAGE_EXTRACT_AND_RUN=1`).
  Działa to wolniej o kilka sekund na konwersję. Szybciej będzie po instalacji
  `sudo apt install libfuse2` (Ubuntu 22.04, Mint 21) albo `sudo apt install libfuse2t64` (Ubuntu 24.04, Mint 22),
- przy wskazywaniu pliku w Ustawieniach **sprawdza, czy MuseScore działa**, i pokazuje jego wersję,
- przycisk **„Otwórz w programie”** otwiera pliki .mscz wprost w tym MuseScore, także wtedy, gdy AppImage
  nie jest w systemie skojarzony z plikami .mscz,
- radzi sobie ze znanymi kaprysami MuseScore 4 w linii poleceń:
  - pomocniczy proces obsługi awarii, który zostaje w tle (program bierze gotowy plik i zamyka MuseScore),
  - kod błędu przy zamykaniu, mimo że plik zapisano,
  - kłopoty z oknami (wtedy próbuje trybu bez okien).

**Ustawienia → Test MuseScore** wykonuje próbną konwersję krótkiego utworu i pokazuje raport:
wersję MuseScore, użyty tryb, wynik (PDF, MIDI, pozycje nut) i dziennik z komunikatami MuseScore.
Przycisk „Kopiuj raport” kopiuje go do schowka, żeby łatwo było go komuś przesłać.
Przycisk „Otwórz w programie” otwiera plik w MuseScore do edycji.

**Podgląd nut** (dwuklik na załączniku):
- przewijanie strona po stronie: strzałki, spacja, pedał Bluetooth albo kliknięcie,
- dwie strony obok siebie,
- tryb „do szerokości”,
- pełny ekran (F11),
- przycisk „Głosy (MIDI)”.

**Jak dodać nuty:**
- przeciągnij plik na okno programu: nuty trafiają do bieżącej pieśni, a teksty (DOCX, TXT…) są importowane,
- albo otwórz „Szukaj nut w sieci…”. To okno nie blokuje programu.
  Pliki pobrane w przeglądarce (np. z MuseScore.com) **pojawiają się w nim same**, bo okno pilnuje folderu Pobrane.
  Zaznaczasz je i klikasz „Dołącz”.
- CPDL bywa niedostępny dla programów (ochrona przed botami). Wtedy program otwiera CPDL w przeglądarce.

## Odtwarzacz głosów: brzmienia i nuty ze słowami

**Brzmienia z SoundFontu,** czyli prawdziwe nagrane próbki:
- barwy **Choir Aahs** (chór „aa”), **Voice Oohs** (chór „uu”), **Church Organ** (organy kościelne),
  **Reed Organ** (fisharmonia), fortepian, smyczki i inne,
- osobna barwa dla każdego głosu (np. bas na organach) oraz suwak **„Podkład organowy”** pod śpiewanymi głosami,
- program sam znajduje pliki SoundFont na komputerze, w tym bibliotekę brzmień instalowaną z MuseScore (.sf3)
  i FluidR3 (.sf2). Inny plik wskażesz przyciskiem „SoundFont…”,
- gdy na komputerze nie ma żadnego SoundFontu, odtwarzacz gra prostym tonem i podpowiada, co zrobić.
  „Skąd pobrać?” otwiera stronę darmowego **GeneralUser GS**: pobierz go i wskaż plik .sf2 przyciskiem „SoundFont…”,
- odtwarzacz SoundFont jest wbudowany w program (numpy), bez FluidSynth i bez kompilowania czegokolwiek.
  Nie ma pogłosu ani filtrów, więc brzmienie bywa trochę „suchsze” niż w MuseScore.

**Nuty ze słowami w czasie odtwarzania:** głosy otwierane z pliku MuseScore (.mscz) pokazują nad wałkiem pianoli
**prawdziwe nuty ze słowami**:
- **kursor przesuwa się po nutach razem z dźwiękiem**, a strony przewracają się same,
- kursor zgadza się z dźwiękiem także przy zmienionym tempie,
- **kliknięcie nuty przewija odtwarzanie do tego miejsca**, co jest wygodne do ćwiczenia trudnego fragmentu,
- położenie nut zapisuje MuseScore podczas konwersji (.spos) i zostaje ono w bazie,
- nuty i wałek pianoli włączasz i wyłączasz osobno,
- **powiększanie nut:** przyciski −/+, „Szerokość”, „Strona” albo Ctrl + kółko myszy. Przy mniejszym
  powiększeniu widać całą frazę, a nie jeden takt. Program zapamiętuje ustawienie.

**Słowa pod nutami** (gdy plik MIDI zawiera tekst, np. z MuseScore 4):
- duża czcionka z regulacją A−/A+,
- każda zwrotka w osobnym wierszu,
- cała fraza widoczna naraz, a po sylabach przeskakuje tylko czerwone zaznaczenie, więc tekst nie miga.

Przycisk **„MIDI – odtwarzanie głosów”** otwiera odtwarzacz dla plików MIDI oraz dla plików MuseScore.

**Pliki MIDI ze słowami** (karaoke, .kar) wyświetlają bieżący fragment tekstu i podświetlają aktualną sylabę.
Polskie znaki są odczytywane z UTF-8 albo Windows-1250.

## Telefon i tablet

**Pilot** (menu Pokaz → Pilot w telefonie, Ctrl+P): telefon i komputer muszą być w tej samej sieci Wi-Fi.
Gdy Wi-Fi nie ma, włącz hotspot w telefonie i połącz z nim komputer. Zeskanuj kod QR aparatem telefonu.
Nic nie trzeba instalować, działa też na iPhonie i iPadzie. Pilot ma zakładki:
- **Pokaz:** bieżący i następny slajd, przyciski ◀ ▶ (albo przesunięcie palcem), czarny ekran, czyste tło, start i koniec pokazu,
- **Slajdy:** miniatury; dotknięcie przełącza slajd na rzutniku,
- **Pieśni:** wyszukiwanie w bazie; „Pokaż” wyświetla pieśń na rzutniku,
- **Nuty:** nuty bieżącej pieśni na pełnym ekranie (PDF, zdjęcia, MuseScore), pobieranie plików
  oraz **„Dodaj z telefonu”**: zdjęcie nut, PDF albo MIDI trafia od razu do pieśni w bazie,
- **Zestaw:** pieśni zestawu i pokaz całości,
- **⇩ Offline:** pobranie śpiewnika offline na telefon albo tablet (cały albo sam zestaw, z nutami lub bez).

Dostęp chroni 6-cyfrowy PIN zawarty w kodzie QR. Pilot działa tylko wtedy, gdy go włączysz.
Na Windowsie zezwól zaporze na dostęp w sieci prywatnej.

**Śpiewnik offline** to jeden plik HTML. Pobierzesz go przez pilota albo zapiszesz w menu
Plik → Eksport śpiewnika offline lub przyciskiem „HTML (telefon)” przy zestawie.
Działa bez internetu i bez komputera, w każdej przeglądarce:
- **tekst** dla śpiewających: duża czcionka, motyw jasny, sepia lub ciemny,
- **slajdy** na pełnym ekranie z tłami, np. telefon podłączony do rzutnika kablem USB-C–HDMI,
- **nuty** dla organisty i chóru: przewracanie dotknięciem lub pedałem Bluetooth, w poziomie dwie strony, ekran nie gaśnie,
- wyszukiwanie, kategorie, zestaw w kolejności.

**Chmura (Nextcloud, Google Drive) – na razie:** trzymaj `liber_canticorum.db` i wyeksportowany śpiewnik HTML
w folderze synchronizowanym na komputerze (klient Nextcloud lub Dysk Google na komputer).
Na telefonie otwierasz plik HTML z aplikacji Nextcloud lub Dysk.
Bazy nie edytuj jednocześnie na dwóch komputerach.

**W planach:** aplikacja na Androida (PySide6) z pełną obsługą chmury z telefonu,
czyli pobieraniem i dodawaniem pieśni i nut bez komputera.
Dla Nextcloud przez standardowy WebDAV, dla Google Drive przez API Google.

## Tła

**Jasne tła w stylu iluminowanych ksiąg chórałowych.** Na nich tekst jest ciemnobrązowy jak atrament,
a refren czerwony jak rubryki:
- **jasne: graduał:** pergamin, czerwona czterolinia z czarnymi neumami u góry i u dołu, złocony inicjał,
  ornament piórkowy w czerwieni i błękicie na marginesie,
- **jasne: chorał renesans:** pięciolinia z notacją menzuralną (brewisy, romby, ligatury, kustosz),
  duży inicjał na złotym polu,
- **jasne: iluminacja:** bordiura z wici, liści i kwiatów oraz inicjał, jak w księgach godzinek,
- **jasne: kolonialny:** wielkie folio chórowe w stylu ksiąg z Meksyku i Limy: duże czarne nuty
  na grubych czerwonych liniach, inicjał w szachownicy, kwiaty i foliacja,
- **jasne: pergamin:** sama karta pergaminu z delikatną liniaturą.

**Ciemne tła:** kodeks (neumy na ciemnym pergaminie), iluminacja (złote wici), adwent (wieniec), Boże Narodzenie
(Gwiazda Betlejemska), maryjne (12 gwiazd, lilie), Wielki Post (krzyż, korona cierniowa), Wielkanoc
(Chi-Rho, Α i Ω), Duch Święty (siedem płomieni), gotyk (ostrołuki), witraż (rozety) i czyste.

Po wybraniu tła program sam ustawia zalecane kolory tekstu i **marginesy**, żeby tekst nie wchodził
na nuty i inicjały. Te ustawienia można potem zmienić.
- Suwak **„Wyciszenie tła”** na ciemnym tle przyciemnia ozdobniki, a na jasnym je rozjaśnia.
- Pod jasnym tekstem rysuje się cień, a pod ciemnym jasna poświata. Dzięki temu tekst jest czytelny
  także tam, gdzie wypada na nuty.

Wszystkie tła są narysowane od zera przez `generuj_tla.py`. Nie są kopiami istniejących rękopisów.
Własny obraz tła wybierzesz opcją „Inny plik…”, a własny motyw dodasz, wrzucając plik JPG lub PNG do folderu `tla/`.

## Licencja

- **Kod programu:** GNU General Public License w wersji 3 lub późniejszej (GPL-3.0-or-later), pełny tekst w pliku `LICENSE`.
  Możesz używać, kopiować, zmieniać i rozpowszechniać program, także zmieniony, pod warunkiem
  udostępnienia kodu źródłowego na tej samej licencji. Program jest dostarczany bez gwarancji.
- **Ikony** (`ikony/`): [Font Awesome Free](https://fontawesome.com) 7, Fonticons, Inc., licencja CC BY 4.0
  (`ikony/LICENSE-FontAwesome.txt`). Ikony są w programie barwione kolorem tekstu z motywu systemu.
  W menu Ustawienia:
  - **Pasek narzędzi:** ikony z podpisem, z napisem obok albo same ikony,
  - **Ikony → Styl:** pełne albo **konturowe (lżejsze)**,
  - **Ikony → Kolory:** systemowe, **jasne pastelowe**, białe (pod ciemny wygląd), kolorowe albo złote (liturgiczne).
    Kolory są przypisane do rodzajów działań: pliki, eksport, pokaz, muzyka, sieć, usuwanie.

  Zmiana działa od razu, bez ponownego uruchamiania.
- **Ikona programu** (`ikony/liber_canticorum*`, `ikony/zrodla/`): litera C z karty tytułowej kancjonału
  z 1586 r. Fotografia: **Mkonik80**, praca własna, licencja **CC BY-SA 4.0**,
  [Wikimedia Commons](https://commons.wikimedia.org/wiki/Special:Redirect/page/56366360).
  Litera została wycięta ze zdjęcia, oczyszczona z tła i zamieniona na wektor. Ikona jest utworem zależnym,
  więc też jest na licencji **CC BY-SA 4.0** (zgodnej w jedną stronę z GPL-3.0). Szczegóły w `ikony/LICENSE-ikona.txt`.
- **Obrazy teł** (`tla/`): CC0 1.0, czyli domena publiczna. Możesz z nimi robić, co chcesz (`tla/LICENSE-CC0.txt`).
- **Biblioteki** mają licencje zgodne z GPL: PySide6 (LGPL-3), python-pptx, python-docx i mido (MIT),
  pypdf, numpy, sounddevice, soundfile i qrcode (BSD/MIT), pypdfium2 (Apache-2.0 / BSD).
- **SoundFonty** nie są dołączone do programu i mają własne licencje (np. GeneralUser GS – licencja zezwalająca
  na swobodne użycie; FluidR3 – MIT; biblioteka brzmień MuseScore – MIT).
