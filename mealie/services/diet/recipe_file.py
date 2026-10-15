"""
Parser for diet recipe files: one Markdown file per recipe, with a YAML front matter
holding the per-serving nutrition and the meal types the recipe fits.

    ---
    nazwa: Owsianka z jabłkiem
    porcje: 2
    posilek: [sniadanie]
    kcal: 420
    bialko: 18
    tluszcz: 12
    weglowodany: 60
    ---
    ## Składniki
    - 100 g płatki owsiane
    - 1 szt jabłko, starte

    ## Przygotowanie
    1. ...
"""

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

import yaml


class MealType(StrEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


MEAL_TYPE_ALIASES: dict[str, MealType] = {
    "sniadanie": MealType.breakfast,
    "breakfast": MealType.breakfast,
    "obiad": MealType.lunch,
    "lunch": MealType.lunch,
    "kolacja": MealType.dinner,
    "dinner": MealType.dinner,
    "przekaska": MealType.snack,
    "snack": MealType.snack,
}

# canonical unit -> spellings accepted in files (compared without diacritics, lowercase, no trailing dot)
UNIT_ALIASES: dict[str, list[str]] = {
    "g": ["g", "gr", "gram", "gramy", "gramow"],
    "dag": ["dag", "dkg"],
    "kg": ["kg"],
    "ml": ["ml"],
    "l": ["l", "litr", "litry", "litrow"],
    "szt": ["szt", "sztuka", "sztuki", "sztuk"],
    "łyżka": ["lyzka", "lyzki", "lyzek", "lyz", "lyzke"],
    "łyżeczka": ["lyzeczka", "lyzeczki", "lyzeczek", "lyzeczke", "lyzecz"],
    "szklanka": ["szklanka", "szklanki", "szklanek", "szkl", "szklanke"],
    "opak": ["opak", "opakowanie", "opakowania", "opakowan"],
    "puszka": ["puszka", "puszki", "puszek", "puszke"],
    "ząbek": ["zabek", "zabki", "zabkow"],
    "plaster": ["plaster", "plastry", "plastrow", "plasterek", "plasterki", "plasterkow"],
    "garść": ["garsc", "garsci", "garscie"],
    "szczypta": ["szczypta", "szczypty", "szczypte", "szczypt"],
    "pęczek": ["peczek", "peczki", "peczkow"],
    "kostka": ["kostka", "kostki", "kostek", "kostke"],
}

UNICODE_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}


def fold(text: str) -> str:
    """Lowercase and strip Polish diacritics, for forgiving comparisons."""
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


_UNIT_LOOKUP = {alias: canonical for canonical, aliases in UNIT_ALIASES.items() for alias in aliases}

_QTY = r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|[½¼¾⅓⅔]"
_INGREDIENT_RE = re.compile(rf"^(?P<qty>(?:\d+\s+)?(?:{_QTY}))\s*(?P<rest>.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<text>.*)$")


class RecipeFileError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class IngredientLine:
    quantity: float
    unit: str | None
    food: str
    note: str
    original_text: str
    title: str | None = None


@dataclass
class RecipeFile:
    name: str
    servings: float
    meal_types: list[MealType]
    kcal: float
    protein: float
    fat: float
    carbs: float
    ingredients: list[IngredientLine]
    steps: list[str]
    description: str = ""
    time_minutes: int | None = None
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    warnings: list[str] = field(default_factory=list)


def parse_quantity(raw: str) -> float:
    raw = raw.strip().replace(",", ".")
    total = 0.0
    for part in raw.split():
        if part in UNICODE_FRACTIONS:
            total += UNICODE_FRACTIONS[part]
        elif "/" in part:
            num, den = part.split("/")
            total += float(num) / float(den)
        else:
            total += float(part)
    return total


def parse_ingredient(text: str) -> IngredientLine | None:
    """Parses `ilość [jednostka] produkt[, uwaga]`; returns None when there's no leading quantity."""
    original = text.strip()
    # "1/2" may be written with spaces around the slash; glue it before matching
    compact = re.sub(r"(\d)\s*/\s*(\d)", r"\1/\2", original)
    match = _INGREDIENT_RE.match(compact)
    if not match:
        return None

    try:
        quantity = parse_quantity(match.group("qty"))
    except (ValueError, ZeroDivisionError):
        return None

    rest = match.group("rest").strip()
    unit: str | None = None
    first, _, remainder = rest.partition(" ")
    canonical = _UNIT_LOOKUP.get(fold(first).rstrip("."))
    if canonical:
        unit = canonical
        rest = remainder.strip()

    food, _, note = rest.partition(",")
    food = food.strip()
    if not food:
        return None

    return IngredientLine(quantity=quantity, unit=unit, food=food, note=note.strip(), original_text=original)


def _number(meta: dict, key: str, errors: list[str], required: bool = True) -> float | None:
    value = meta.get(key)
    if value is None or value == "":
        if required:
            errors.append(f"brak pola „{key}”")
        return None
    try:
        number = float(str(value).replace(",", ".").split()[0])
    except (ValueError, IndexError):
        errors.append(f"pole „{key}” musi być liczbą (jest: {value!r})")
        return None
    if number < 0:
        errors.append(f"pole „{key}” nie może być ujemne")
        return None
    return number


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _split_front_matter(text: str) -> tuple[str, str, int]:
    """Returns (yaml, body, line number where the body starts)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RecipeFileError(["plik musi zaczynać się od linii „---” (nagłówek z danymi przepisu)"])
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :]), i + 2
    raise RecipeFileError(["brak zamykającej linii „---” po nagłówku"])


def parse_recipe_file(text: str) -> RecipeFile:
    text = text.lstrip("﻿")
    front, body, body_start = _split_front_matter(text)

    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError as e:
        line = getattr(getattr(e, "problem_mark", None), "line", None)
        where = f" (linia {line + 2})" if line is not None else ""
        raise RecipeFileError([f"nagłówek nie jest poprawnym YAML{where}"]) from e
    if not isinstance(meta, dict):
        raise RecipeFileError(["nagłówek musi zawierać pola w postaci „klucz: wartość”"])
    meta = {fold(str(k)): v for k, v in meta.items()}

    errors: list[str] = []
    warnings: list[str] = []

    name = str(meta.get("nazwa") or "").strip()
    if not name:
        errors.append("brak pola „nazwa”")

    servings = _number(meta, "porcje", errors)
    if servings is not None and servings <= 0:
        errors.append("pole „porcje” musi być większe od zera")

    meal_types: list[MealType] = []
    for raw in _as_list(meta.get("posilek")):
        meal_type = MEAL_TYPE_ALIASES.get(fold(raw))
        if meal_type is None:
            errors.append(f"nieznany posiłek „{raw}” (dozwolone: sniadanie, obiad, kolacja, przekaska)")
        elif meal_type not in meal_types:
            meal_types.append(meal_type)
    if not meal_types and not any("posiłek" in e for e in errors):
        errors.append("brak pola „posilek” (np. posilek: [obiad])")

    kcal = _number(meta, "kcal", errors)
    protein = _number(meta, "bialko", errors)
    fat = _number(meta, "tluszcz", errors)
    carbs = _number(meta, "weglowodany", errors)
    time = _number(meta, "czas", errors, required=False)

    # Body: optional description, then "## Składniki" and "## Przygotowanie" sections
    sections: dict[str, list[tuple[int, str]]] = {"opis": []}
    current = "opis"
    for offset, line in enumerate(body.splitlines()):
        heading = re.match(r"^\s*##\s+(.*)$", line)
        if heading and not line.lstrip().startswith("###"):
            title = fold(heading.group(1).strip())
            if title.startswith("skladnik"):
                current = "skladniki"
            elif title.startswith("przygotowanie") or title.startswith("sposob") or title.startswith("kroki"):
                current = "przygotowanie"
            else:
                current = "inne"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append((body_start + offset, line))

    ingredients: list[IngredientLine] = []
    pending_title: str | None = None
    for line_no, line in sections.get("skladniki", []):
        if not line.strip():
            continue
        sub = re.match(r"^\s*###\s+(.*)$", line)
        if sub:
            pending_title = sub.group(1).strip()
            continue
        item = _LIST_ITEM_RE.match(line)
        content = item.group("text") if item else line
        parsed = parse_ingredient(content)
        if parsed is None:
            errors.append(
                f"linia {line_no}: nie rozumiem składnika „{content.strip()}” – "
                "zapisz jako „ilość jednostka produkt”, np. „100 g ryż”"
            )
            continue
        parsed.title, pending_title = pending_title, None
        ingredients.append(parsed)
    if "skladniki" not in sections:
        errors.append("brak sekcji „## Składniki”")
    elif not ingredients and not any("składnik" in e for e in errors):
        errors.append("sekcja „## Składniki” jest pusta")

    steps: list[str] = []
    for _, line in sections.get("przygotowanie", []):
        if not line.strip():
            continue
        item = _LIST_ITEM_RE.match(line)
        if item:
            steps.append(item.group("text").strip())
        elif steps:
            steps[-1] = f"{steps[-1]} {line.strip()}"
        else:
            steps.append(line.strip())

    description = "\n".join(line for _, line in sections["opis"]).strip()

    if errors:
        raise RecipeFileError(errors)

    assert servings is not None and kcal is not None and protein is not None and fat is not None and carbs is not None

    if kcal > 0:
        from_macros = 4 * protein + 9 * fat + 4 * carbs
        if abs(kcal - from_macros) / kcal > 0.15:
            warnings.append(
                f"kcal ({kcal:g}) nie zgadza się z makro (4·B + 9·T + 4·W = {from_macros:g}) – sprawdź wartości"
            )
    else:
        warnings.append("kcal = 0 – przepis nie będzie dobierany do planu")

    return RecipeFile(
        name=name,
        servings=servings,
        meal_types=meal_types,
        kcal=kcal,
        protein=protein,
        fat=fat,
        carbs=carbs,
        ingredients=ingredients,
        steps=steps,
        description=description,
        time_minutes=int(time) if time else None,
        tags=_as_list(meta.get("tagi")),
        source=str(meta["zrodlo"]).strip() if meta.get("zrodlo") else None,
        warnings=warnings,
    )
