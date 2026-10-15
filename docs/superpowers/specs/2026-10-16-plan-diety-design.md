# Plan diety – projekt (2026-10-16)

Fork `0xbartix/mealie`, gałąź `plan-diety`. Cel: planowanie posiłków pod kalorie i makro, z gotowaniem na zapas, na bazie przepisów importowanych z plików o stałym formacie.

## Zakres

W zakresie:
1. Osoby z własną kaloryką i makro (liczba osób ustawiana w funkcji).
2. Dni gotowania w tygodniu – gotowanie na zapas do następnego dnia gotowania.
3. Liczba posiłków dziennie (1–6) z podziałem kalorii.
4. Dobór przepisów z bazy pod powyższe + przeliczenie porcji, zapis do kalendarza Mealie.
5. Importer przepisów z plików `.md` (nagłówek YAML z gotowym makro).

Poza zakresem (na później): koszyk Frisco/Delio/Auchan, hosting (osobna część).

## 1. Importer plików

Jeden przepis = jeden plik `.md`:

```markdown
---
nazwa: Owsianka z jabłkiem
porcje: 2
posilek: [sniadanie]          # sniadanie / obiad / kolacja / przekaska
kcal: 420                     # na 1 porcję
bialko: 18                    # g na porcję
tluszcz: 12
weglowodany: 60
czas: 15                      # min, opcjonalnie
tagi: [wege]                  # opcjonalnie
zrodlo: https://...           # opcjonalnie
---
## Składniki
- 100 g płatki owsiane
- 1 szt jabłko, starte

## Przygotowanie
1. ...
```

- Wymagane: `nazwa`, `porcje` (>0), `posilek` (min. 1 ze znanych), `kcal`, `bialko`, `tluszcz`, `weglowodany` (liczby ≥0), sekcja `## Składniki` z min. 1 pozycją.
- Składnik: `ilość [jednostka] produkt[, uwaga]`; ilość może być ułamkiem (`0.5`, `0,5`, `1/2`). Jednostka rozpoznawana ze stałej listy (g, dag, kg, ml, l, szt, łyżka/łyżki, łyżeczka/łyżeczki, szklanka/szklanki, opak, puszka, ząbek/ząbki, plaster/plastry, garść, szczypta); gdy drugie słowo nie jest jednostką – składnik bez jednostki (`2 jajka`). Linia bez ilości na początku to błąd z numerem linii.
- Jednostki i produkty dopasowywane po nazwie (bez wielkości liter) do istniejących w Mealie, brakujące tworzone.
- `posilek` → kategorie Mealie: Śniadanie, Obiad, Kolacja, Przekąska (tworzone, jeśli brak).
- kcal/makro → pola wartości odżywczych przepisu (`calories`, `proteinContent`, `fatContent`, `carbohydrateContent`) jako liczby; `porcje` → `recipeServings`.
- Ponowny import tej samej `nazwy` (w gospodarstwie) aktualizuje przepis zamiast duplikować.
- Ostrzeżenie (nie błąd), gdy kcal różni się od 4·B + 9·T + 4·W o >15%.
- UI: „Importuj z plików” w menu tworzenia przepisu – wiele `.md` albo `.zip`; raport per plik: dodany / zaktualizowany / błąd (z opisem) / ostrzeżenie.
- Dokumentacja: szablon + instrukcja dla AI do zamiany przepisu ze strony na ten format.

## 2. Ustawienia i planer

Ustawienia per gospodarstwo:
- Osoby: imię, kcal, białko g, tłuszcz g, węglowodany g, aktywna tak/nie.
- Dni gotowania: zbiór dni tygodnia (min. 1).
- Posiłki: lista slotów `{typ, udział %}`, 1–6 slotów, suma 100%. Domyślne podziały:
  - 3: śniadanie 30, obiad 40, kolacja 30
  - 4: śniadanie 25, obiad 35, przekąska 10, kolacja 30
  - 5: śniadanie 25, przekąska 10, obiad 35, przekąska 10, kolacja 20
  - (1, 2, 6 – analogicznie, edytowalne)

Generowanie dla okresu [start, koniec]:
1. **Partie**: od dnia gotowania do dnia przed następnym dniem gotowania; pierwsza partia zaczyna się w dniu startu, nawet jeśli to nie dzień gotowania; ostatnia kończy się na końcu okresu.
2. **Kandydaci** na slot: przepisy z kategorią slotu i kompletnym makro (kcal>0).
3. **Porcja** osoby p w slocie s: `kcal_p · udział_s / kcal_porcji_przepisu`, zaokrąglona do 0,25 (min. 0,25).
4. **Ocena** kombinacji przepisów partii: suma po osobach kwadratów względnych odchyłek B/T/W (i kcal po zaokrągleniu) od celu + kara za przepis użyty w poprzedniej partii (dla tego samego typu posiłku) + kara za ten sam przepis w dwóch slotach jednego dnia.
5. **Szukanie**: losowe próbkowanie + poprawianie po jednym slocie (local search), stałe ziarno → wynik powtarzalny.
6. **Za mało przepisów**: plan powstaje z powtórzeniami, komunikat ile kandydatów ma dany typ posiłku; brak kandydatów → slot pusty z komunikatem.
7. **Podgląd**: dni × osoby, kcal/B/T/W vs cel, kolory: ≤5% zielony, ≤15% żółty, >15% czerwony. „Zamień” w slocie partii → następny najlepszy przepis dla tego slotu przy pozostałych bez zmian.
8. **Zapis do kalendarza**:
   - Każdy dzień: wpis na slot z przepisem, `recipe_scale = suma porcji osób danego dnia / porcje przepisu`, tekst: „Bartek: 1¼ porcji (525 kcal) · Ania: ¾ porcji (315 kcal)”.
   - Dzień gotowania partii: notatka „Ugotuj: …” z łączną liczbą porcji per przepis na całą partię.
   - Wpisy z generatora są zapamiętane (tabela powiązań); ponowne generowanie okresu usuwa tylko je, ręczne wpisy zostają.
   - Dzięki `recipe_scale` wbudowane „dodaj do listy zakupów” liczy właściwe ilości.

## 3. Interfejs i kod

- Strona gospodarstwa „Plan diety”: karta Ustawienia, karta Generuj (okres → podgląd → Zamień → Zapisz do kalendarza).
- Backend: `mealie/services/diet/` (czytnik, planer, zapis), `mealie/routes/households/controller_diet.py`, modele w `mealie/db/models/household/diet.py`, schematy `mealie/schema/diet/`, jedna migracja Alembic.
- Frontend: `pages/household/diet/`, `components/Domain/Diet/`, klient API, tłumaczenia en-US + pl-PL.
- Zmiany w plikach Mealie ograniczone do rejestracji tras/modeli/repo, menu i tłumaczeń.

## 4. Testy

- pytest: czytnik (pliki poprawne, błędne, niezgodny kcal, ponowny import), planer (partie vs dni gotowania, kcal ±5% przy wystarczających kandydatach, porcje co 0,25, suma do ugotowania = suma zjedzona, powtarzalność ziarna, brak kandydatów), API (ustawienia, podgląd, zapis, ręczne wpisy nietknięte, import).
- Uruchomienie lokalne: import ~20 przykładowych przepisów, plan 2 tygodnie dla 2 osób, kalendarz + lista zakupów, zrzuty ekranu.
