from datetime import date

import pytest

from mealie.services.diet.planner import Candidate, DietPlanner, Person, Slot, split_batches
from mealie.services.diet.recipe_file import MealType

MON = date(2026, 10, 19)  # a Monday
WED, SUN = 2, 6


def candidate(i: int, meal: MealType, kcal: float, p: float, f: float, c: float, servings: float = 4) -> Candidate:
    return Candidate(
        f"{meal.value}-{i}", f"{meal.value} {i}", f"{meal.value}-{i}", servings, kcal, p, f, c, frozenset([meal])
    )


def balanced_pool() -> list[Candidate]:
    # a spread of macro profiles per meal type: high-protein, high-fat, high-carb and balanced
    pool = []
    profiles = [(0.30, 0.25, 0.45), (0.15, 0.45, 0.40), (0.12, 0.20, 0.68), (0.22, 0.30, 0.48), (0.35, 0.35, 0.30)]
    for meal in MealType:
        for i, (pp, fp, cp) in enumerate(profiles):
            kcal = 300 + 40 * i
            pool.append(candidate(i, meal, kcal, kcal * pp / 4, kcal * fp / 9, kcal * cp / 4))
    return pool


PERSONS = [
    Person("a", "Bartek", 2500, 160, 80, 280),
    Person("b", "Ania", 1800, 110, 60, 200),
]
SLOTS = [Slot(MealType.breakfast, 0.30), Slot(MealType.lunch, 0.40), Slot(MealType.dinner, 0.30)]


def test_split_batches_follows_cooking_days():
    batches = split_batches(MON, date(2026, 11, 1), {WED, SUN})
    assert batches == [
        (date(2026, 10, 19), date(2026, 10, 20)),  # period starts on Monday, before the first cooking day
        (date(2026, 10, 21), date(2026, 10, 24)),  # Wed..Sat
        (date(2026, 10, 25), date(2026, 10, 27)),  # Sun..Tue
        (date(2026, 10, 28), date(2026, 10, 31)),  # Wed..Sat
        (date(2026, 11, 1), date(2026, 11, 1)),  # Sunday, cut by the end of the period
    ]


def test_split_batches_eating_from_the_next_day():
    # cooking on Wednesday and Sunday evenings: that food is eaten from Thursday and from Monday
    plan = DietPlanner(PERSONS, SLOTS, balanced_pool(), {WED, SUN}, seed=1, eat_next_day=True).plan(
        MON, date(2026, 11, 1)
    )
    assert [(b.cook_date, b.start, b.end) for b in plan.batches] == [
        (date(2026, 10, 18), date(2026, 10, 19), date(2026, 10, 21)),  # cooked the Sunday before the period
        (date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 25)),  # Wed -> Thu..Sun
        (date(2026, 10, 25), date(2026, 10, 26), date(2026, 10, 28)),  # Sun -> Mon..Wed
        (date(2026, 10, 28), date(2026, 10, 29), date(2026, 11, 1)),  # Wed -> Thu..Sun
    ]
    same_day = DietPlanner(PERSONS, SLOTS, balanced_pool(), {WED, SUN}, seed=1).plan(MON, date(2026, 10, 25))
    assert all(b.cook_date == b.start for b in same_day.batches)


def test_split_batches_single_day_period():
    assert split_batches(MON, MON, {SUN}) == [(MON, MON)]


def test_plan_hits_kcal_and_quarter_portions():
    plan = DietPlanner(PERSONS, SLOTS, balanced_pool(), {WED, SUN}, seed=1).plan(MON, date(2026, 11, 1))

    assert len(plan.batches) == 5
    assert plan.warnings == []
    for batch in plan.batches:
        for slot in batch.slots:
            assert slot.recipe is not None
            assert slot.recipe.meal_types == frozenset([slot.meal_type])
            for portion in slot.portions:
                assert portion.portions >= 0.25
                assert (portion.portions * 4) == int(portion.portions * 4)
        for person, totals in zip(PERSONS, batch.totals, strict=True):
            assert totals.kcal == pytest.approx(person.kcal, rel=0.05)


def test_plan_is_reproducible_and_varies_between_batches():
    planner = DietPlanner(PERSONS, SLOTS, balanced_pool(), {WED, SUN}, seed=7)
    first = planner.plan(MON, date(2026, 11, 1))
    second = planner.plan(MON, date(2026, 11, 1))

    ids = lambda plan: [[s.recipe.id for s in b.slots if s.recipe] for b in plan.batches]  # noqa: E731
    assert ids(first) == ids(second)
    # consecutive batches should not serve the same lunch when there are alternatives
    lunches = [b.slots[1].recipe.id for b in first.batches if b.slots[1].recipe]
    assert all(a != b for a, b in zip(lunches, lunches[1:], strict=False))


def test_locked_and_excluded_slots():
    planner = DietPlanner(PERSONS, SLOTS, balanced_pool(), {SUN}, seed=3)
    base = planner.plan(MON, date(2026, 10, 25))
    current = base.batches[0].slots[1].recipe.id

    swapped = planner.plan(
        MON,
        date(2026, 10, 25),
        locked={0: {0: base.batches[0].slots[0].recipe.id, 2: base.batches[0].slots[2].recipe.id}},
        excluded={0: {1: [current]}},
    )
    assert swapped.batches[0].slots[1].recipe.id != current
    assert swapped.batches[0].slots[0].recipe.id == base.batches[0].slots[0].recipe.id
    assert swapped.batches[0].slots[2].recipe.id == base.batches[0].slots[2].recipe.id


def test_pins_that_do_not_fit_the_slot_are_ignored():
    planner = DietPlanner(PERSONS, SLOTS, balanced_pool(), {SUN}, seed=3)
    # a dinner recipe pinned into the breakfast slot (e.g. after the meal setup changed)
    plan = planner.plan(MON, MON, locked={0: {0: "dinner-1"}})
    assert plan.batches[0].slots[0].recipe.meal_types == frozenset([MealType.breakfast])


def test_missing_and_scarce_candidates_are_reported():
    pool = [c for c in balanced_pool() if c.meal_types != frozenset([MealType.dinner])]
    pool = [c for c in pool if not (MealType.breakfast in c.meal_types and c.id != "breakfast-0")]
    plan = DietPlanner(PERSONS, SLOTS, pool, {WED, SUN}, seed=1).plan(MON, date(2026, 11, 1))

    assert "no-candidates:dinner" in plan.warnings
    assert "few-candidates:breakfast:1" in plan.warnings
    assert all(b.slots[2].recipe is None and b.slots[2].portions == [] for b in plan.batches)
    assert all(b.slots[0].recipe.id == "breakfast-0" for b in plan.batches)


def test_recipes_without_kcal_are_ignored():
    pool = [candidate(0, MealType.lunch, 0, 0, 0, 0), candidate(1, MealType.lunch, 500, 30, 20, 50)]
    plan = DietPlanner(PERSONS[:1], [Slot(MealType.lunch, 1.0)], pool, {SUN}).plan(MON, MON)
    assert plan.batches[0].slots[0].recipe.id == "lunch-1"
    assert plan.batches[0].slots[0].candidates_count == 1


def test_large_pool_uses_local_search_quickly():
    pool = []
    for meal in MealType:
        for i in range(60):
            kcal = 250 + 7 * i
            pool.append(candidate(i, meal, kcal, kcal * (0.1 + (i % 7) / 30) / 4, kcal * 0.3 / 9, kcal * 0.45 / 4))
    slots = [
        Slot(MealType.breakfast, 0.25),
        Slot(MealType.snack, 0.10),
        Slot(MealType.lunch, 0.35),
        Slot(MealType.snack, 0.10),
        Slot(MealType.dinner, 0.20),
    ]
    plan = DietPlanner(PERSONS, slots, pool, {WED, SUN}, seed=1).plan(MON, date(2026, 11, 15))
    assert len(plan.batches) == 9
    for batch in plan.batches:
        snack_ids = [s.recipe.id for s in batch.slots if s.meal_type is MealType.snack]
        assert len(set(snack_ids)) == 2  # the same recipe twice a day is avoided
