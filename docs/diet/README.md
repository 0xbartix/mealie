# Plan diety – pliki z przepisami

Jeden przepis = jeden plik `.md`. Import: **Utwórz → Import z plików** (można wybrać wiele plików naraz albo jeden `.zip`).
Ponowny import pliku o tej samej `nazwie` aktualizuje przepis zamiast tworzyć duplikat.

Gotowe przykłady (18 przepisów: śniadania, obiady, kolacje, przekąski) są w katalogu [`przyklady/`](przyklady/) –
możesz je zaimportować wszystkie naraz jako bazę startową.

## Szablon

```markdown
---
nazwa: Owsianka z jabłkiem
porcje: 2
posilek: [sniadanie]          # sniadanie / obiad / kolacja / przekaska (można kilka)
kcal: 420                     # wszystkie wartości NA 1 PORCJĘ
bialko: 18                    # gramy
tluszcz: 12
weglowodany: 60
czas: 15                      # minuty, opcjonalnie
tagi: [wege, szybkie]         # opcjonalnie
zrodlo: https://...           # opcjonalnie
---
Krótki opis (opcjonalnie).

## Składniki
- 100 g płatki owsiane
- 400 ml mleko 2%
- 1 szt jabłko, starte
### Posypka
- 30 g masło orzechowe

## Przygotowanie
1. Płatki zalej mlekiem i gotuj 5 minut.
2. Dodaj starte jabłko i masło orzechowe.
```

## Zasady

- Składnik: `ilość [jednostka] produkt[, uwaga]`, produkt **w mianowniku** („płatki owsiane”, nie „płatków owsianych”) –
  wtedy te same produkty z różnych przepisów sumują się na liście zakupów.
- Ilość: `100`, `0,5`, `1/2`, `1 1/2`, `½`.
- Jednostki: g, dag, kg, ml, l, szt, łyżka, łyżeczka, szklanka, opak, puszka, ząbek, plaster, garść, szczypta, pęczek, kostka
  (odmiany typu „łyżki”, „ząbki” też są rozpoznawane). Bez jednostki też można: `2 jajka`.
- `### Nazwa` w składnikach tworzy podgrupę (np. sos, posypka).
- Przepis trafia do planu, gdy ma `posilek` i `kcal` większe od zera.
- Jeśli kcal nie zgadza się z makro (4·B + 9·T + 4·W) o więcej niż 15%, import przejdzie z ostrzeżeniem.

## Polecenie dla AI (Claude / ChatGPT)

Wklej poniższe polecenie, a pod nim przepis ze strony albo zdjęcie:

```text
Zamień poniższy przepis na plik Markdown dokładnie w tym formacie (nic poza plikiem):

---
nazwa: <nazwa>
porcje: <liczba porcji>
posilek: [<sniadanie|obiad|kolacja|przekaska>]
kcal: <kcal na 1 porcję>
bialko: <g na 1 porcję>
tluszcz: <g na 1 porcję>
weglowodany: <g na 1 porcję>
czas: <minuty>
tagi: [<opcjonalne tagi>]
zrodlo: <adres strony, jeśli jest>
---
## Składniki
- <ilość> <jednostka> <produkt w mianowniku>[, <uwaga>]

## Przygotowanie
1. <krok>

Zasady: wartości odżywcze policz na 1 porcję z gramatur składników (tabele wartości odżywczych);
jednostki tylko z listy: g, dag, kg, ml, l, szt, łyżka, łyżeczka, szklanka, opak, puszka, ząbek, plaster,
garść, szczypta, pęczek, kostka; produkty w mianowniku; liczby bez jednostek w nagłówku.
```
