# Zamrażarka i licznik kcal – projekt (2026-10-16)

Gałąź `zamrazarka-licznik` (z `plan-diety`). Rozszerza plan diety o bazę produktów, zamrażarkę porcji i dzienny licznik kcal w stylu Fitatu.

## Baza produktów

- Tabela `diet_products` (gospodarstwo): nazwa, marka, kod kreskowy, kcal/B/T/W na 100 g lub 100 ml (`unit`: g | ml), opcjonalna porcja (`portion_name`, `portion_grams`), źródło (`custom` | `off`), `off_code`.
- Źródła: ręcznie; Open Food Facts – wyszukiwanie po nazwie (stary `pl.openfoodfacts.org/cgi/search.pl`, przy błędzie/limicie `search.openfoodfacts.org`), kod kreskowy (`/api/v2/product/{code}`). Wynik z OFF zapisuje się lokalnie przy wyborze (bez duplikatów po `off_code`). Wyniki wyszukiwania w pamięci podręcznej (24 h), nagłówek User-Agent aplikacji.
- Produkty bez kcal w OFF są pomijane w wynikach.

## Zamrażarka

- Tabela `diet_freezer_batches` (gospodarstwo): przepis (id + nazwa na chwilę zamrożenia), data, ugotowane porcje, lista zmian (JSON), ręczna korekta (opcjonalna), suma kcal/B/T/W, foremki (JSON: `{capacity_ml, count, left}`), notatka.
- Bazowe makro = makro porcji przepisu × ugotowane porcje.
- Zmiany (produkty z bazy, gramy): `add` (+produkt), `remove` (−produkt, „dałem mniej / pominąłem”), `swap` (−zastąpiony +nowy). Po zmianach można nadpisać sumę ręcznie.
- Makro foremki = suma × pojemność / Σ(pojemność × liczba) – różne rozmiary w jednej partii.
- Stan: `left` per rozmiar; zdjęcie foremki ręcznie (−1) albo przez licznik; usunięcie partii.
- Podgląd wyliczeń (`POST /freezer/preview`) i zapis (`POST /freezer`) liczą to samo po stronie serwera.

## Licznik kcal

- Tabela `diet_diary_entries` (gospodarstwo): osoba (id z ustawień), data, posiłek (breakfast/lunch/snack/dinner), rodzaj (`product` | `recipe` | `freezer` | `quick`), odniesienie (id produktu/przepisu/partii + indeks foremki), ilość + jednostka (g/ml, porcja, foremka), nazwa i kcal/B/T/W zapisane w chwili dodania, `plan_entry_id` (z planu).
- Produkt: wartości × ilość/100 (albo porcje × `portion_grams`). Przepis: porcje × makro porcji. Zamrażarka: foremki (wielokrotność 0,5) × makro foremki, zmniejsza `left`; usunięcie wpisu przywraca stan. Szybko: nazwa + kcal (+ opcjonalne makro).
- „Dodaj z planu”: wpisy generatora z danego dnia (przepisy) z porcjami tej osoby → wpisy `recipe`; pomija już dodane (`plan_entry_id`). Generator zapamiętuje porcje osób w swoim śladzie wpisów.
- Dzień: wpisy w sekcjach + suma vs cel osoby.

## Interfejs

- Menu: „Licznik kcal”, „Zamrażarka”.
- Licznik: wybór osoby i dnia, paski postępu, sekcje posiłków, okno „Dodaj” (Produkt / Przepis / Zamrażarka / Szybko), „Dodaj z planu”, zakładka „Moje produkty” (lista, dodaj/edytuj/usuń).
- Wybór produktu (wspólny komponent): lokalne od razu, „Szukaj w Open Food Facts” po Enter, skaner kodów (aparat, BarcodeDetector z polyfillem; ręczne wpisanie kodu).
- Zamrażarka: lista partii, okno „Zamroź przepis” (przepis, data, porcje, zmiany, foremki, podgląd, korekta ręczna).

## Testy

- Jednostkowe: przeliczenia zamrażarki, parsowanie odpowiedzi OFF.
- API: produkty (CRUD, kod kreskowy z podstawionym OFF), zamrażarka (podgląd, zapis, foremki), licznik (dodanie/usunięcie każdego rodzaju, stan zamrażarki, z planu bez duplikatów), zakres gospodarstwa.
