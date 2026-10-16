"""
Batch-cooking diet planner.

The period is split into batches: a batch starts on a cooking day (or on the first day of the
period) and lasts until the day before the next cooking day. Each meal slot of a batch gets one
recipe that is eaten on every day of the batch. Every person's portion of a slot is sized to hit
`person.kcal * slot.share`, rounded to a quarter of a serving, so the recipe choice mostly drives
how close the day gets to the person's macro targets.
"""

import itertools
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from mealie.services.diet.recipe_file import MealType

PORTION_STEP = 0.25
EXHAUSTIVE_LIMIT = 4000
RESTARTS = 12
PREVIOUS_BATCH_PENALTY = 0.03
REUSE_PENALTY = 0.01
SAME_DAY_DUPLICATE_PENALTY = 0.5


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float


@dataclass(frozen=True)
class Slot:
    meal_type: MealType
    share: float  # fraction of the daily kcal, 0..1


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    slug: str
    servings: float
    kcal: float  # per serving
    protein: float
    fat: float
    carbs: float
    meal_types: frozenset[MealType]


@dataclass
class Portion:
    person_id: str
    portions: float
    kcal: float


@dataclass
class SlotPlan:
    slot_index: int
    meal_type: MealType
    recipe: Candidate | None
    portions: list[Portion]
    candidates_count: int

    @property
    def portions_per_day(self) -> float:
        return sum(p.portions for p in self.portions)


@dataclass
class Totals:
    person_id: str
    kcal: float
    protein: float
    fat: float
    carbs: float


@dataclass
class Batch:
    index: int
    start: date  # first day eaten
    end: date  # last day eaten
    cook_date: date
    slots: list[SlotPlan]
    totals: list[Totals]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass
class Plan:
    batches: list[Batch]
    warnings: list[str] = field(default_factory=list)


def split_batches(
    start: date, end: date, cooking_weekdays: set[int], eat_next_day: bool = False
) -> list[tuple[date, date]]:
    """
    Splits [start, end] into the days eaten from each cooking; weekday numbers follow `date.weekday()`
    (0 = Monday). With `eat_next_day` food cooked on a cooking day is eaten from the following day.
    """
    shift = timedelta(days=1 if eat_next_day else 0)
    batches: list[tuple[date, date]] = []
    batch_start = start
    day = start + timedelta(days=1)
    while day <= end:
        if (day - shift).weekday() in cooking_weekdays:
            batches.append((batch_start, day - timedelta(days=1)))
            batch_start = day
        day += timedelta(days=1)
    batches.append((batch_start, end))
    return batches


def portion_for(person: Person, slot: Slot, recipe: Candidate) -> float:
    if recipe.kcal <= 0:
        return PORTION_STEP
    raw = person.kcal * slot.share / recipe.kcal
    return max(PORTION_STEP, round(raw / PORTION_STEP) * PORTION_STEP)


def _totals(persons: list[Person], slots: list[Slot], recipes: list[Candidate | None]) -> list[Totals]:
    result = []
    for person in persons:
        t = Totals(person.id, 0.0, 0.0, 0.0, 0.0)
        for slot, recipe in zip(slots, recipes, strict=True):
            if recipe is None:
                continue
            p = portion_for(person, slot, recipe)
            t.kcal += p * recipe.kcal
            t.protein += p * recipe.protein
            t.fat += p * recipe.fat
            t.carbs += p * recipe.carbs
        result.append(t)
    return result


def _rel(value: float, target: float) -> float:
    return (value - target) / target if target > 0 else 0.0


def deviation(person: Person, totals: Totals) -> float:
    return (
        2 * _rel(totals.kcal, person.kcal) ** 2
        + _rel(totals.protein, person.protein) ** 2
        + _rel(totals.fat, person.fat) ** 2
        + _rel(totals.carbs, person.carbs) ** 2
    )


class DietPlanner:
    def __init__(
        self,
        persons: list[Person],
        slots: list[Slot],
        candidates: list[Candidate],
        cooking_weekdays: set[int],
        seed: int = 0,
        eat_next_day: bool = False,
    ) -> None:
        self.persons = persons
        self.slots = slots
        self.candidates = [c for c in candidates if c.kcal > 0 and c.servings > 0]
        self.cooking_weekdays = cooking_weekdays
        self.seed = seed
        self.eat_next_day = eat_next_day

    def _slot_candidates(self, slot: Slot) -> list[Candidate]:
        return [c for c in self.candidates if slot.meal_type in c.meal_types]

    def _score(self, recipes: list[Candidate | None], previous: set[str], used: dict[str, int]) -> float:
        totals = _totals(self.persons, self.slots, recipes)
        score = sum(deviation(p, t) for p, t in zip(self.persons, totals, strict=True))
        seen: set[str] = set()
        for recipe in recipes:
            if recipe is None:
                continue
            if recipe.id in seen:
                score += SAME_DAY_DUPLICATE_PENALTY
            seen.add(recipe.id)
            if recipe.id in previous:
                score += PREVIOUS_BATCH_PENALTY
            score += REUSE_PENALTY * used.get(recipe.id, 0)
        return score

    def _choose(
        self,
        options: list[list[Candidate | None]],
        previous: set[str],
        used: dict[str, int],
        rng: random.Random,
    ) -> list[Candidate | None]:
        if math.prod(len(o) for o in options) <= EXHAUSTIVE_LIMIT:
            return list(min(itertools.product(*options), key=lambda combo: self._score(list(combo), previous, used)))

        best: list[Candidate | None] | None = None
        best_score = math.inf
        for _ in range(RESTARTS):
            current = [rng.choice(o) for o in options]
            current_score = self._score(current, previous, used)
            improved = True
            while improved:
                improved = False
                for i, slot_options in enumerate(options):
                    for option in slot_options:
                        if option is current[i]:
                            continue
                        trial = current.copy()
                        trial[i] = option
                        trial_score = self._score(trial, previous, used)
                        if trial_score < current_score - 1e-12:
                            current, current_score, improved = trial, trial_score, True
            if current_score < best_score:
                best, best_score = current, current_score
        assert best is not None
        return best

    def plan(
        self,
        start: date,
        end: date,
        locked: dict[int, dict[int, str]] | None = None,
        excluded: dict[int, dict[int, list[str]]] | None = None,
    ) -> Plan:
        """
        `locked[batch][slot]` pins a recipe id to a slot; `excluded[batch][slot]` removes recipe ids
        from a slot's options (used by "swap" to get the next best recipe).
        """
        locked = locked or {}
        excluded = excluded or {}
        rng = random.Random(self.seed)
        by_id = {c.id: c for c in self.candidates}
        plan = Plan(batches=[])

        slot_candidates = [self._slot_candidates(s) for s in self.slots]
        batch_days = split_batches(start, end, self.cooking_weekdays, self.eat_next_day)
        needed = len(batch_days)
        for slot, available in zip(self.slots, slot_candidates, strict=True):
            if not available:
                plan.warnings.append(f"no-candidates:{slot.meal_type.value}")
            elif len(available) < min(needed, 3):
                plan.warnings.append(f"few-candidates:{slot.meal_type.value}:{len(available)}")

        previous: set[str] = set()
        used: dict[str, int] = {}
        for index, (batch_start, batch_end) in enumerate(batch_days):
            options: list[list[Candidate | None]] = []
            for slot_index, slot_options in enumerate(slot_candidates):
                pinned = locked.get(index, {}).get(slot_index)
                if pinned and pinned in by_id and self.slots[slot_index].meal_type in by_id[pinned].meal_types:
                    options.append([by_id[pinned]])
                    continue
                skip = set(excluded.get(index, {}).get(slot_index, []))
                remaining: list[Candidate | None] = [c for c in slot_options if c.id not in skip]
                options.append(remaining or (list(slot_options) or [None]))

            recipes = self._choose(options, previous, used, rng)
            slots = []
            for slot_index, (slot, recipe) in enumerate(zip(self.slots, recipes, strict=True)):
                portions = []
                if recipe is not None:
                    for person in self.persons:
                        p = portion_for(person, slot, recipe)
                        portions.append(Portion(person.id, p, p * recipe.kcal))
                slots.append(SlotPlan(slot_index, slot.meal_type, recipe, portions, len(slot_candidates[slot_index])))

            cook_date = batch_start - timedelta(days=1 if self.eat_next_day else 0)
            plan.batches.append(
                Batch(index, batch_start, batch_end, cook_date, slots, _totals(self.persons, self.slots, recipes))
            )
            previous = {r.id for r in recipes if r is not None}
            for r in recipes:
                if r is not None:
                    used[r.id] = used.get(r.id, 0) + 1

        return plan
