"""Nutrition maths for freezer batches: base recipe × servings, ingredient changes, split into molds."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Macros:
    kcal: float = 0
    protein: float = 0
    fat: float = 0
    carbs: float = 0

    def __add__(self, other: Macros) -> Macros:
        return Macros(
            self.kcal + other.kcal, self.protein + other.protein, self.fat + other.fat, self.carbs + other.carbs
        )

    def __sub__(self, other: Macros) -> Macros:
        return self + other.scaled(-1)

    def scaled(self, factor: float) -> Macros:
        return Macros(self.kcal * factor, self.protein * factor, self.fat * factor, self.carbs * factor)

    def clamped(self) -> Macros:
        return Macros(max(self.kcal, 0), max(self.protein, 0), max(self.fat, 0), max(self.carbs, 0))

    def rounded(self, digits: int = 1) -> Macros:
        return Macros(
            round(self.kcal, digits), round(self.protein, digits), round(self.fat, digits), round(self.carbs, digits)
        )

    def as_dict(self) -> dict[str, float]:
        return {"kcal": self.kcal, "protein": self.protein, "fat": self.fat, "carbs": self.carbs}


def for_amount(per_100: Macros, grams: float) -> Macros:
    """Nutrition of `grams` of a product given per 100 g (or 100 ml)."""
    return per_100.scaled(grams / 100)


@dataclass(frozen=True)
class Change:
    kind: str  # add | remove | swap
    product: Macros  # per 100 g
    grams: float
    replaced: Macros | None = None  # per 100 g, swap only
    replaced_grams: float | None = None

    def delta(self) -> Macros:
        if self.kind == "add":
            return for_amount(self.product, self.grams)
        if self.kind == "remove":
            return for_amount(self.product, self.grams).scaled(-1)
        assert self.replaced is not None and self.replaced_grams is not None
        return for_amount(self.product, self.grams) - for_amount(self.replaced, self.replaced_grams)


@dataclass(frozen=True)
class MoldGroup:
    capacity_ml: float
    count: int


@dataclass
class BatchResult:
    base: Macros
    deltas: list[Macros]
    total: Macros
    per_mold: list[Macros]  # one entry per mold group: nutrition of a single mold


def compute_batch(
    per_serving: Macros,
    servings: float,
    changes: list[Change],
    molds: list[MoldGroup],
    override: Macros | None = None,
) -> BatchResult:
    base = per_serving.scaled(servings)
    deltas = [change.delta() for change in changes]
    total = base
    for delta in deltas:
        total = total + delta
    total = (override if override is not None else total).clamped()

    volume = sum(m.capacity_ml * m.count for m in molds)
    per_mold = [total.scaled(m.capacity_ml / volume) if volume else Macros() for m in molds]
    return BatchResult(base=base, deltas=deltas, total=total, per_mold=per_mold)
