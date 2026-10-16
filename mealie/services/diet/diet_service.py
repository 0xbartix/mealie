import io
import random
import re
import zipfile
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from pydantic import UUID4
from slugify import slugify
from sqlalchemy.orm import lazyload, selectinload

from mealie.db.models.household.diet import HouseholdDietSettings
from mealie.db.models.recipe import RecipeModel
from mealie.db.models.recipe.ingredient import IngredientFoodModel, IngredientUnitModel
from mealie.db.models.users import User
from mealie.lang.providers import Translator
from mealie.repos.repository_factory import AllRepositories
from mealie.repos.repository_generic import HouseholdRepositoryGeneric
from mealie.schema.diet.diet import (
    DietImportReport,
    DietImportResult,
    DietImportStatus,
    DietPlanBatch,
    DietPlanPortion,
    DietPlanPreview,
    DietPlanRecipe,
    DietPlanRequest,
    DietPlanSaveResult,
    DietPlanSlot,
    DietPlanTotals,
    DietSettingsOut,
    DietSettingsSave,
    DietSettingsUpdate,
    DietShoppingListMode,
    DietShoppingListRef,
)
from mealie.schema.household.group_shopping_list import ShoppingListAddRecipeParamsBulk, ShoppingListCreate
from mealie.schema.household.household import HouseholdInDB
from mealie.schema.meal_plan.new_meal import PlanEntryType, ReadPlanEntry, SavePlanEntry
from mealie.schema.recipe.recipe import Recipe, RecipeCategory, RecipeTag
from mealie.schema.recipe.recipe_category import CategorySave, TagSave
from mealie.schema.recipe.recipe_ingredient import (
    IngredientFood,
    IngredientUnit,
    RecipeIngredient,
    SaveIngredientFood,
    SaveIngredientUnit,
)
from mealie.schema.recipe.recipe_nutrition import Nutrition
from mealie.schema.recipe.recipe_settings import RecipeSettings
from mealie.schema.recipe.recipe_step import RecipeStep
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.user.user import PrivateUser
from mealie.services._base_service import BaseService
from mealie.services.diet.planner import Batch, Candidate, DietPlanner, Person, Plan, Slot
from mealie.services.diet.recipe_file import MealType, RecipeFile, RecipeFileError, fold, parse_recipe_file
from mealie.services.household_services.shopping_lists import ShoppingListService
from mealie.services.parser_services._base import DataMatcher
from mealie.services.recipe.recipe_service import RecipeService

MEAL_CATEGORY_NAMES: dict[MealType, str] = {
    MealType.breakfast: "Śniadanie",
    MealType.lunch: "Obiad",
    MealType.dinner: "Kolacja",
    MealType.snack: "Przekąska",
}
CATEGORY_SLUG_TO_MEAL: dict[str, MealType] = {
    **{slugify(name): meal for meal, name in MEAL_CATEGORY_NAMES.items()},
    **{meal.value: meal for meal in MealType},
}
MEAL_TO_ENTRY_TYPE: dict[MealType, PlanEntryType] = {
    MealType.breakfast: PlanEntryType.breakfast,
    MealType.lunch: PlanEntryType.lunch,
    MealType.dinner: PlanEntryType.dinner,
    MealType.snack: PlanEntryType.snack,
}
UNIT_PLURALS = {
    "łyżka": "łyżki",
    "łyżeczka": "łyżeczki",
    "szklanka": "szklanki",
    "puszka": "puszki",
    "ząbek": "ząbki",
    "plaster": "plastry",
    "garść": "garście",
    "szczypta": "szczypty",
    "pęczek": "pęczki",
    "kostka": "kostki",
}
# units shown by their short form in ingredient lists
ABBREVIATED_UNITS = {"g", "dag", "kg", "ml", "l", "szt", "opak"}

MAX_IMPORT_FILES = 500
PRUNE_AFTER_DAYS = 120
# marks recipes created by the file importer; only those may be updated by a later import
IMPORT_MARKER = "plan-diety-import"
MAX_FILE_BYTES = 512 * 1024


def parse_number(value: str | None) -> float:
    """Reads the first number out of a nutrition string such as "420 kcal" or "18,5 g"."""
    if not value:
        return 0.0
    match = re.search(r"\d+(?:[.,]\d+)?", value)
    return float(match.group().replace(",", ".")) if match else 0.0


def format_portions(value: float) -> str:
    whole = int(value)
    fraction = {0.25: "¼", 0.5: "½", 0.75: "¾"}.get(round(value - whole, 2), "")
    return f"{whole if whole or not fraction else ''}{fraction}"


def portions_word(value: float) -> str:
    if value != int(value):
        return "porcji"
    n = int(value)
    if n == 1:
        return "porcja"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "porcje"
    return "porcji"


def entry_fingerprint(entry: ReadPlanEntry) -> dict:
    """What the planner remembers about an entry it wrote, to recognise it later."""
    return {
        "id": entry.id,
        "date": entry.date.isoformat(),
        "type": entry.entry_type.value,
        "recipe": str(entry.recipe_id) if entry.recipe_id else None,
        "title": entry.title,
    }


FINGERPRINT_KEYS = ("id", "date", "type", "recipe", "title")


def tracked_matches(tracked: dict, entry: ReadPlanEntry) -> bool:
    """Whether a remembered planner entry still is the meal plan entry the planner wrote."""
    fingerprint = entry_fingerprint(entry)
    return all(tracked.get(key) == fingerprint[key] for key in FINGERPRINT_KEYS)


WEEKDAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]


def _short(day: date) -> str:
    return day.strftime("%d.%m")


def _fmt(value: float) -> str:
    return f"{round(value, 1):g}"


class DietService(BaseService):
    def __init__(
        self, repos: AllRepositories, user: PrivateUser, household: HouseholdInDB, translator: Translator
    ) -> None:
        self.repos = repos
        self.user = user
        self.household = household
        self.translator = translator
        self.group_id: UUID4 = household.group_id
        self.household_id: UUID4 = household.id
        self.settings_repo = HouseholdRepositoryGeneric(
            repos.session,
            "household_id",
            HouseholdDietSettings,
            DietSettingsOut,
            group_id=self.group_id,
            household_id=self.household_id,
        )
        super().__init__()

    # ================================================================
    # Settings

    def get_settings(self) -> DietSettingsOut:
        settings = self.settings_repo.get_one(self.household_id)
        if settings is None:
            settings = self.settings_repo.create(
                DietSettingsSave(group_id=self.group_id, household_id=self.household_id)
            )
        return settings

    def update_settings(self, data: DietSettingsUpdate) -> DietSettingsOut:
        self.get_settings()
        save = DietSettingsSave(**data.model_dump(), group_id=self.group_id, household_id=self.household_id)
        return self.settings_repo.update(self.household_id, save.model_dump(mode="json"))

    # ================================================================
    # Planning

    def _candidates(self) -> list[Candidate]:
        stmt = (
            sa.select(RecipeModel)
            .where(RecipeModel.group_id == self.group_id)
            .options(
                lazyload("*"),
                selectinload(RecipeModel.nutrition),
                selectinload(RecipeModel.recipe_category),
            )
        )
        candidates = []
        for recipe in self.repos.session.execute(stmt).scalars():
            meal_types = frozenset(
                CATEGORY_SLUG_TO_MEAL[c.slug] for c in recipe.recipe_category if c.slug in CATEGORY_SLUG_TO_MEAL
            )
            nutrition = recipe.nutrition
            if not meal_types or nutrition is None:
                continue
            kcal = parse_number(nutrition.calories)
            if kcal <= 0:
                continue
            candidates.append(
                Candidate(
                    id=str(recipe.id),
                    name=recipe.name or "",
                    slug=recipe.slug or "",
                    servings=recipe.recipe_servings or recipe.recipe_yield_quantity or 1,
                    kcal=kcal,
                    protein=parse_number(nutrition.protein_content),
                    fat=parse_number(nutrition.fat_content),
                    carbs=parse_number(nutrition.carbohydrate_content),
                    meal_types=meal_types,
                )
            )
        return candidates

    def _plan(self, request: DietPlanRequest) -> tuple[Plan, int, DietSettingsOut]:
        settings = self.get_settings()
        persons = [Person(p.id, p.name, p.kcal, p.protein, p.fat, p.carbs) for p in settings.persons if p.active]
        if not persons:
            raise ValueError("no-persons")

        seed = request.seed if request.seed is not None else random.randint(1, 999_999)
        planner = DietPlanner(
            persons=persons,
            slots=[Slot(s.meal_type, s.share / 100) for s in settings.meal_slots],
            candidates=self._candidates(),
            cooking_weekdays=set(settings.cooking_days),
            seed=seed,
            eat_next_day=settings.eat_next_day,
        )
        plan = planner.plan(
            request.start_date,
            request.end_date,
            locked={b: {s: str(r) for s, r in slots.items()} for b, slots in request.locked.items()},
            excluded={
                b: {s: [str(r) for r in ids] for s, ids in slots.items()} for b, slots in request.excluded.items()
            },
        )
        return plan, seed, settings

    def preview(self, request: DietPlanRequest) -> DietPlanPreview:
        plan, seed, _ = self._plan(request)
        batches = []
        for batch in plan.batches:
            slots = []
            for slot in batch.slots:
                recipe = slot.recipe
                slots.append(
                    DietPlanSlot(
                        slot_index=slot.slot_index,
                        meal_type=slot.meal_type,
                        recipe=DietPlanRecipe(
                            id=recipe.id,
                            name=recipe.name,
                            slug=recipe.slug,
                            servings=recipe.servings,
                            kcal=recipe.kcal,
                            protein=recipe.protein,
                            fat=recipe.fat,
                            carbs=recipe.carbs,
                        )
                        if recipe
                        else None,
                        portions=[
                            DietPlanPortion(person_id=p.person_id, portions=p.portions, kcal=p.kcal)
                            for p in slot.portions
                        ],
                        portions_per_day=slot.portions_per_day,
                        portions_per_batch=slot.portions_per_day * batch.days,
                        candidates_count=slot.candidates_count,
                    )
                )
            batches.append(
                DietPlanBatch(
                    index=batch.index,
                    cook_date=batch.cook_date,
                    start_date=batch.start,
                    end_date=batch.end,
                    days=batch.days,
                    slots=slots,
                    totals=[
                        DietPlanTotals(person_id=t.person_id, kcal=t.kcal, protein=t.protein, fat=t.fat, carbs=t.carbs)
                        for t in batch.totals
                    ],
                )
            )
        return DietPlanPreview(seed=seed, batches=batches, warnings=plan.warnings)

    def save(self, request: DietPlanRequest) -> DietPlanSaveResult:
        plan, _, settings = self._plan(request)
        names = {p.id: p.name for p in settings.persons}
        meals = self.repos.meals
        tracked = [t for t in self._settings_model().generated_entry_ids or [] if isinstance(t, dict)]

        # Replace only what the planner wrote itself. SQLite reuses the ids of deleted rows, so an id alone
        # may point at a manual entry added later: an entry counts as ours only while it still looks as we wrote it.
        in_period = meals.page_all(
            PaginationQuery(
                page=1,
                per_page=-1,
                # with "eat next day" the first cooking note sits the day before the period
                query_filter=f"date >= {min([request.start_date, *(b.cook_date for b in plan.batches)])}"
                f" AND date <= {request.end_date}",
            )
        ).items
        current = {e.id: e for e in in_period}
        stale = {t["id"] for t in tracked if t["id"] in current and tracked_matches(t, current[t["id"]])}
        removed = 0
        created: list[dict] = []
        try:
            for entry_id in sorted(stale):
                meals.delete(entry_id)
                stale.discard(entry_id)
                removed += 1

            for batch in plan.batches:
                cooked = [slot for slot in batch.slots if slot.recipe is not None]
                if not cooked:
                    continue
                days = "1 dzień" if batch.days == 1 else f"{batch.days} dni"
                dishes = " · ".join(
                    f"{slot.recipe.name}: {format_portions(total)} {portions_word(total)}"
                    for slot in cooked
                    if slot.recipe is not None and (total := slot.portions_per_day * batch.days)
                )
                note = meals.create(
                    SavePlanEntry(
                        date=batch.cook_date,
                        entry_type=MEAL_TO_ENTRY_TYPE[cooked[0].meal_type],
                        title=f"Dzień gotowania – na {days}",
                        text=dishes,
                        group_id=self.group_id,
                        user_id=self.user.id,
                    )
                )
                created.append(entry_fingerprint(note))

                for offset in range(batch.days):
                    day = batch.start + timedelta(days=offset)
                    for slot in cooked:
                        assert slot.recipe is not None
                        entry = meals.create(
                            SavePlanEntry(
                                date=day,
                                entry_type=MEAL_TO_ENTRY_TYPE[slot.meal_type],
                                text=" · ".join(
                                    f"{names.get(p.person_id, '?')}: {format_portions(p.portions)} "
                                    f"{portions_word(p.portions)} ({round(p.kcal)} kcal)"
                                    for p in slot.portions
                                ),
                                recipe_id=slot.recipe.id,
                                recipe_scale=slot.portions_per_day / slot.recipe.servings,
                                group_id=self.group_id,
                                user_id=self.user.id,
                            )
                        )
                        created.append(
                            {**entry_fingerprint(entry), "portions": {p.person_id: p.portions for p in slot.portions}}
                        )
        except Exception:
            self.repos.session.rollback()
            raise
        finally:
            # record progress even after a failure, so entries written so far are still replaced next time
            deleted = {t["id"] for t in tracked if t["id"] in current and tracked_matches(t, current[t["id"]])} - stale
            horizon = (datetime.now(UTC).date() - timedelta(days=PRUNE_AFTER_DAYS)).isoformat()
            kept = [t for t in tracked if t["id"] not in deleted and t["date"] >= horizon]
            model = self._settings_model()
            model.generated_entry_ids = kept + created
            self.repos.session.commit()

        lists = self._write_shopping_lists(plan, request, settings)
        return DietPlanSaveResult(created=len(created), removed=removed, shopping_lists=lists)

    def _write_shopping_lists(
        self, plan: Plan, request: DietPlanRequest, settings: DietSettingsOut
    ) -> list[DietShoppingListRef]:
        """Shopping lists for the plan; lists the planner wrote earlier for an overlapping period are replaced."""
        model = self._settings_model()
        start, end = request.start_date.isoformat(), request.end_date.isoformat()
        tracked = [t for t in model.generated_list_ids or [] if isinstance(t, dict)]
        overlapping = [t for t in tracked if t["start"] <= end and t["end"] >= start]
        for old in overlapping:
            try:
                self.repos.group_shopping_lists.delete(old["id"])
            except Exception:
                self.repos.session.rollback()  # already deleted by hand
        kept = [t for t in tracked if t not in overlapping]

        groups: list[tuple[str, list[Batch]]] = []
        if settings.shopping_list is DietShoppingListMode.period:
            groups = [(f"Plan diety {_short(request.start_date)}–{_short(request.end_date)}", plan.batches)]
        elif settings.shopping_list is DietShoppingListMode.batch:
            for batch in plan.batches:
                days = "1 dzień" if batch.days == 1 else f"{batch.days} dni"
                groups.append(
                    (f"Gotowanie {WEEKDAYS[batch.cook_date.weekday()]} {_short(batch.cook_date)} (na {days})", [batch])
                )

        service = ShoppingListService(self.repos)
        written: list[DietShoppingListRef] = []
        for name, batches in groups:
            scales: dict[str, tuple[UUID4, float]] = {}
            for batch in batches:
                for slot in batch.slots:
                    if slot.recipe is None:
                        continue
                    recipe_id, scale = scales.get(slot.recipe.id, (UUID(slot.recipe.id), 0.0))
                    scales[slot.recipe.id] = (
                        recipe_id,
                        scale + slot.portions_per_day * batch.days / slot.recipe.servings,
                    )
            if not scales:
                continue
            shopping_list = service.create_one_list(ShoppingListCreate(name=name), owner_id=self.user.id)
            service.add_recipe_ingredients_to_list(
                shopping_list.id,
                [
                    ShoppingListAddRecipeParamsBulk(recipe_id=recipe_id, recipe_increment_quantity=round(scale, 3))
                    for recipe_id, scale in scales.values()
                ],
            )
            written.append(DietShoppingListRef(id=shopping_list.id, name=name))
            first, last = batches[0].start, batches[-1].end
            kept.append({"id": str(shopping_list.id), "start": first.isoformat(), "end": last.isoformat()})

        model = self._settings_model()
        model.generated_list_ids = kept
        self.repos.session.commit()
        return written

    def tracked_entries(self) -> list[dict]:
        """Meal plan entries the planner wrote, with each person's portions."""
        return [t for t in self._settings_model().generated_entry_ids or [] if isinstance(t, dict)]

    def _settings_model(self) -> HouseholdDietSettings:
        self.get_settings()
        return self.repos.session.execute(
            sa.select(HouseholdDietSettings).where(HouseholdDietSettings.household_id == self.household_id)
        ).scalar_one()

    # ================================================================
    # Import

    def import_files(self, files: list[tuple[str, bytes]]) -> DietImportReport:
        documents: list[tuple[str, bytes | None, str | None]] = []
        for file_name, content in files:
            if fold(file_name).endswith(".zip"):
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as archive:
                        for info in archive.infolist():
                            name = info.filename
                            if info.is_dir() or "__MACOSX" in name or not fold(name).endswith(".md"):
                                continue
                            if info.file_size > MAX_FILE_BYTES:
                                documents.append((name, None, "plik jest za duży (maks. 512 KB)"))
                                continue
                            documents.append((name, archive.read(info), None))
                except zipfile.BadZipFile:
                    documents.append((file_name, None, "to nie jest poprawne archiwum .zip"))
            elif fold(file_name).endswith((".md", ".markdown", ".txt")):
                if len(content) > MAX_FILE_BYTES:
                    documents.append((file_name, None, "plik jest za duży (maks. 512 KB)"))
                else:
                    documents.append((file_name, content, None))
            else:
                documents.append((file_name, None, "obsługiwane są pliki .md i .zip"))

        if len(documents) > MAX_IMPORT_FILES:
            raise ValueError(f"too-many-files:{MAX_IMPORT_FILES}")

        importer = _RecipeFileImporter(self.repos, self.user, self.household, self.translator)
        results = []
        for name, document, error in documents:
            if error or document is None:
                results.append(DietImportResult(file_name=name, status=DietImportStatus.error, errors=[error or ""]))
                continue
            results.append(importer.import_one(name, document))
        return DietImportReport(results=results)


class _RecipeFileImporter:
    """Creates or updates recipes from parsed files, reusing units, foods, categories and tags by name."""

    def __init__(
        self, repos: AllRepositories, user: PrivateUser, household: HouseholdInDB, translator: Translator
    ) -> None:
        self.repos = repos
        self.group_id = household.group_id
        self.household = household
        self.recipe_service = RecipeService(repos, user, household, translator=translator)
        self.matcher = DataMatcher(repos, food_fuzzy_match_threshold=100, unit_fuzzy_match_threshold=100)
        self._categories: dict[str, RecipeCategory] = {}
        self._tags: dict[str, RecipeTag] = {}

    def import_one(self, file_name: str, content: bytes) -> DietImportResult:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return DietImportResult(
                file_name=file_name, status=DietImportStatus.error, errors=["plik musi być zapisany w UTF-8"]
            )
        try:
            data = parse_recipe_file(text)
        except RecipeFileError as e:
            return DietImportResult(file_name=file_name, status=DietImportStatus.error, errors=e.errors)
        except Exception as e:
            return DietImportResult(
                file_name=file_name, status=DietImportStatus.error, errors=[f"nie udało się odczytać pliku: {e}"]
            )

        try:
            existing = self._find_existing(data.name)
            if existing and IMPORT_MARKER not in (self.recipe_service.get_one(existing).extras or {}):
                return DietImportResult(
                    file_name=file_name,
                    status=DietImportStatus.error,
                    recipe_name=data.name,
                    recipe_slug=existing,
                    errors=[
                        f"masz już przepis „{data.name}” dodany inaczej niż z pliku – "
                        "zmień nazwę w pliku albo usuń tamten przepis"
                    ],
                )
            if existing:
                recipe = self.recipe_service.get_one(existing)
                self._apply(recipe, data)
                saved = self.recipe_service.update_one(existing, recipe)
                status = DietImportStatus.updated
            else:
                recipe = Recipe(name=data.name, extras={IMPORT_MARKER: "tak"})
                self._apply(recipe, data)
                prefs = self.household.preferences
                recipe.settings = RecipeSettings(
                    public=prefs.recipe_public if prefs else False,
                    show_nutrition=True,
                    show_assets=prefs.recipe_show_assets if prefs else False,
                    landscape_view=prefs.recipe_landscape_view if prefs else False,
                    disable_comments=prefs.recipe_disable_comments if prefs else False,
                )
                saved = self.recipe_service.create_one(recipe)
                status = DietImportStatus.created
        except Exception as e:
            self.repos.session.rollback()
            return DietImportResult(
                file_name=file_name,
                status=DietImportStatus.error,
                recipe_name=data.name,
                errors=[f"nie udało się zapisać przepisu: {e}"],
            )

        return DietImportResult(
            file_name=file_name,
            status=status,
            recipe_name=saved.name,
            recipe_slug=saved.slug,
            warnings=data.warnings,
        )

    def _find_existing(self, name: str) -> str | None:
        """Slug of this household's recipe with the same name (other households' recipes are never touched)."""
        wanted = name.strip().casefold()
        rows = self.repos.session.execute(
            sa.select(RecipeModel.slug, RecipeModel.name)
            .join(User, RecipeModel.user_id == User.id)
            .where(RecipeModel.group_id == self.group_id, User.household_id == self.household.id)
        )
        for slug, recipe_name in rows:
            if (recipe_name or "").strip().casefold() == wanted:
                return slug
        return None

    def _apply(self, recipe: Recipe, data: RecipeFile) -> None:
        recipe.name = data.name
        recipe.description = data.description
        recipe.recipe_servings = data.servings
        if data.source:
            recipe.org_url = data.source
        if data.time_minutes:
            recipe.total_time = None
            recipe.total_time_seconds = data.time_minutes * 60

        meal_slugs = set(CATEGORY_SLUG_TO_MEAL)
        kept_categories = [c for c in recipe.recipe_category or [] if c.slug not in meal_slugs]
        recipe.recipe_category = kept_categories + [self._category(MEAL_CATEGORY_NAMES[m]) for m in data.meal_types]

        tags = {t.slug: t for t in recipe.tags or []}
        for tag_name in data.tags:
            tag = self._tag(tag_name)
            tags[tag.slug] = tag
        recipe.tags = list(tags.values())

        recipe.recipe_ingredient = [
            RecipeIngredient(
                quantity=line.quantity,
                unit=self._unit(line.unit) if line.unit else None,
                food=self._food(line.food),
                note=line.note,
                original_text=line.original_text,
                title=line.title,
            )
            for line in data.ingredients
        ]
        recipe.recipe_instructions = [RecipeStep(text=step) for step in data.steps]
        recipe.nutrition = Nutrition(
            calories=_fmt(data.kcal),
            protein_content=_fmt(data.protein),
            fat_content=_fmt(data.fat),
            carbohydrate_content=_fmt(data.carbs),
        )
        if recipe.settings:
            recipe.settings.show_nutrition = True

    def _category(self, name: str) -> RecipeCategory:
        slug = slugify(name)
        if slug not in self._categories:
            category = self.repos.categories.get_one(slug, "slug") or self.repos.categories.create(
                CategorySave(name=name, group_id=self.group_id)
            )
            self._categories[slug] = RecipeCategory(
                id=category.id, group_id=category.group_id, name=category.name, slug=category.slug
            )
        return self._categories[slug]

    def _tag(self, name: str) -> RecipeTag:
        slug = slugify(name)
        if slug not in self._tags:
            tag = self.repos.tags.get_one(slug, "slug") or self.repos.tags.create(
                TagSave(name=name, group_id=self.group_id)
            )
            self._tags[slug] = RecipeTag(id=tag.id, group_id=tag.group_id, name=tag.name, slug=tag.slug)
        return self._tags[slug]

    def _unit(self, name: str) -> IngredientUnit:
        unit = self.matcher.find_unit_match(name)
        if unit is None:
            unit = self.repos.ingredient_units.create(
                SaveIngredientUnit(
                    name=name,
                    plural_name=UNIT_PLURALS.get(name),
                    abbreviation=name if name in ABBREVIATED_UNITS else "",
                    use_abbreviation=name in ABBREVIATED_UNITS,
                    group_id=self.group_id,
                )
            )
            self.matcher.units_by_alias[IngredientUnitModel.normalize(name)] = unit
        return unit

    def _food(self, name: str) -> IngredientFood:
        food = self.matcher.find_food_match(name)
        if food is None:
            food = self.repos.ingredient_foods.create(SaveIngredientFood(name=name, group_id=self.group_id))
            self.matcher.foods_by_alias[IngredientFoodModel.normalize(name)] = food
        return food
