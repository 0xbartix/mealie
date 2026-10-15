import pytest

from mealie.services.diet.recipe_file import MealType, RecipeFileError, parse_ingredient, parse_recipe_file

VALID = """---
nazwa: Owsianka z jabłkiem
porcje: 2
posilek: [sniadanie, przekąska]
kcal: 420
bialko: 18
tluszcz: 12
weglowodany: 60
czas: 15
tagi: [wege, szybkie]
zrodlo: https://example.com/owsianka
---
Szybkie śniadanie na ciepło.

## Składniki
- 100 g płatki owsiane
- 400 ml mleko 2%
- 1 szt jabłko, starte
- 1/2 łyżeczki cynamon
### Posypka
- 30 g masło orzechowe, bez cukru
- 2 jajka

## Przygotowanie
1. Płatki zalej mlekiem
   i gotuj 5 minut.
2. Dodaj jabłko.
"""


def test_parses_complete_file():
    recipe = parse_recipe_file(VALID)

    assert recipe.name == "Owsianka z jabłkiem"
    assert recipe.servings == 2
    assert recipe.meal_types == [MealType.breakfast, MealType.snack]
    assert (recipe.kcal, recipe.protein, recipe.fat, recipe.carbs) == (420, 18, 12, 60)
    assert recipe.time_minutes == 15
    assert recipe.tags == ["wege", "szybkie"]
    assert recipe.source == "https://example.com/owsianka"
    assert recipe.description == "Szybkie śniadanie na ciepło."
    assert recipe.steps == ["Płatki zalej mlekiem i gotuj 5 minut.", "Dodaj jabłko."]
    assert recipe.warnings == []

    names = [(i.quantity, i.unit, i.food, i.note) for i in recipe.ingredients]
    assert names == [
        (100, "g", "płatki owsiane", ""),
        (400, "ml", "mleko 2%", ""),
        (1, "szt", "jabłko", "starte"),
        (0.5, "łyżeczka", "cynamon", ""),
        (30, "g", "masło orzechowe", "bez cukru"),
        (2, None, "jajka", ""),
    ]
    assert recipe.ingredients[4].title == "Posypka"
    assert recipe.ingredients[5].title is None


@pytest.mark.parametrize(
    "line, expected",
    [
        ("100g ryż", (100, "g", "ryż")),
        ("0,5 kg ziemniaki", (0.5, "kg", "ziemniaki")),
        ("1 1/2 szklanki mąka pszenna", (1.5, "szklanka", "mąka pszenna")),
        ("½ szt. cebula", (0.5, "szt", "cebula")),
        ("2 łyżki oliwa", (2, "łyżka", "oliwa")),
        ("3 ząbki czosnek", (3, "ząbek", "czosnek")),
        ("1 / 4 opakowania tofu", (0.25, "opak", "tofu")),
        ("1 500 ml woda", (1500, "ml", "woda")),
        ("1 000 g mąka", (1000, "g", "mąka")),
        ("1½ szklanki mąka", (1.5, "szklanka", "mąka")),
        ("1-2 ząbki czosnek", (2, "ząbek", "czosnek")),
        ("2–3 łyżki oliwa", (3, "łyżka", "oliwa")),
        ("2 x 100 g jogurt", (200, "g", "jogurt")),
        ("2 xylitol", (2, None, "xylitol")),
    ],
)
def test_ingredient_variants(line, expected):
    parsed = parse_ingredient(line)
    assert parsed is not None
    assert (parsed.quantity, parsed.unit, parsed.food) == expected


@pytest.mark.parametrize("line", ["sól do smaku", "g ryż", "100 g", "", "100 g 5% jogurt", "1 - jajko"])
def test_ingredient_rejects_lines_without_quantity_or_food(line):
    assert parse_ingredient(line) is None


def test_reports_all_errors_with_line_numbers():
    text = """---
nazwa:
porcje: 0
posilek: [deser]
kcal: dużo
bialko: 10
---
## Składniki
- 100 g ryż
- sól do smaku
"""
    with pytest.raises(RecipeFileError) as exc:
        parse_recipe_file(text)

    errors = exc.value.errors
    assert "brak pola „nazwa”" in errors
    assert "pole „porcje” musi być większe od zera" in errors
    assert any("nieznany posiłek „deser”" in e for e in errors)
    assert any("pole „kcal” musi być liczbą" in e for e in errors)
    assert "brak pola „tluszcz”" in errors
    assert "brak pola „weglowodany”" in errors
    assert any(e.startswith("linia 10:") and "sól do smaku" in e for e in errors)


def test_missing_front_matter_and_sections():
    with pytest.raises(RecipeFileError, match="musi zaczynać się"):
        parse_recipe_file("## Składniki\n- 1 g sól\n")

    with pytest.raises(RecipeFileError, match="Składniki"):
        parse_recipe_file(
            "---\nnazwa: X\nporcje: 1\nposilek: obiad\nkcal: 1\nbialko: 0\ntluszcz: 0\nweglowodany: 0\n---\n"
        )


def test_warns_when_kcal_does_not_match_macros():
    text = VALID.replace("kcal: 420", "kcal: 900")
    recipe = parse_recipe_file(text)
    assert len(recipe.warnings) == 1
    assert "nie zgadza się z makro" in recipe.warnings[0]


@pytest.mark.parametrize("value", [".nan", ".inf", "-.inf"])
def test_rejects_non_finite_numbers(value):
    with pytest.raises(RecipeFileError, match="zwykłą liczbą"):
        parse_recipe_file(VALID.replace("czas: 15", f"czas: {value}"))


def test_accepts_comma_decimals_and_single_meal_string():
    text = VALID.replace("posilek: [sniadanie, przekąska]", "posilek: Obiad").replace("bialko: 18", "bialko: 18,5")
    recipe = parse_recipe_file(text)
    assert recipe.meal_types == [MealType.lunch]
    assert recipe.protein == 18.5
