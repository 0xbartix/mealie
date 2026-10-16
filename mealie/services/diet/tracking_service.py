"""Products, freezer and the daily kcal diary of a household."""

import re
from datetime import date as Date
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from pydantic import UUID4

from mealie.db.models.household.diet import DietDiaryEntry, DietFreezerBatch, DietProduct
from mealie.db.models.recipe import RecipeModel
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.diet.tracking import (
    DietAmountUnit,
    DietDiaryCreate,
    DietDiaryDay,
    DietDiaryEntryOut,
    DietDiaryFromPlan,
    DietDiaryFromPlanResult,
    DietDiaryKind,
    DietFreezerAdjust,
    DietFreezerBatchOut,
    DietFreezerModificationOut,
    DietFreezerMoldOut,
    DietFreezerPreview,
    DietFreezerRequest,
    DietMacros,
    DietModificationKind,
    DietOffProduct,
    DietProductCreate,
    DietProductOut,
    DietProductSave,
    DietProductSearch,
    DietProductSource,
    DietRecipeOption,
)
from mealie.schema.household.household import HouseholdInDB
from mealie.schema.meal_plan.new_meal import PlanEntryType
from mealie.schema.response.pagination import PaginationQuery
from mealie.services._base_service import BaseService
from mealie.services.diet.diet_service import DietService, parse_number, tracked_matches
from mealie.services.diet.freezer import Change, Macros, MoldGroup, compute_batch
from mealie.services.diet.off_client import OffUnavailable, OpenFoodFactsClient
from mealie.services.diet.recipe_file import MealType, fold

ENTRY_TYPE_TO_MEAL: dict[str, MealType] = {
    PlanEntryType.breakfast.value: MealType.breakfast,
    PlanEntryType.lunch.value: MealType.lunch,
    PlanEntryType.dinner.value: MealType.dinner,
    PlanEntryType.snack.value: MealType.snack,
}
BARCODE_RE = re.compile(r"\d{6,14}")


class DietNotFound(Exception):
    pass


def _macros(source: Any) -> Macros:
    return Macros(source.kcal, source.protein, source.fat, source.carbs)


def _from_dict(data: dict | None) -> Macros:
    data = data or {}
    return Macros(data.get("kcal", 0), data.get("protein", 0), data.get("fat", 0), data.get("carbs", 0))


def _out(macros: Macros) -> DietMacros:
    rounded = macros.clamped().rounded()
    return DietMacros(kcal=rounded.kcal, protein=rounded.protein, fat=rounded.fat, carbs=rounded.carbs)


class DietTrackingService(BaseService):
    def __init__(
        self,
        repos: AllRepositories,
        household: HouseholdInDB,
        diet: DietService,
        off: OpenFoodFactsClient,
    ) -> None:
        self.repos = repos
        self.session = repos.session
        self.group_id: UUID4 = household.group_id
        self.household_id: UUID4 = household.id
        self.diet = diet
        self.off = off
        super().__init__()

    # ================================================================
    # helpers

    def _scoped(self, model: Any) -> sa.Select:
        return sa.select(model).where(model.household_id == self.household_id)

    def _get(self, model: Any, item_id: UUID) -> Any:
        item = self.session.execute(self._scoped(model).where(model.id == item_id)).scalar_one_or_none()
        if item is None:
            raise DietNotFound(f"{model.__tablename__}:{item_id}")
        return item

    # ================================================================
    # Products

    def list_products(self, search: str | None = None) -> list[DietProductOut]:
        products = self.session.execute(self._scoped(DietProduct).order_by(DietProduct.name)).scalars().all()
        if search:
            words = fold(search).split()
            products = [
                p for p in products if all(w in fold(f"{p.name} {p.brand or ''} {p.barcode or ''}") for w in words)
            ]
        return [DietProductOut.model_validate(p) for p in products]

    def create_product(self, data: DietProductCreate) -> DietProductOut:
        save = DietProductSave(**data.model_dump(), group_id=self.group_id, household_id=self.household_id)
        product = DietProduct(session=self.session, **save.model_dump())
        self.session.add(product)
        self.session.commit()
        return DietProductOut.model_validate(product)

    def update_product(self, product_id: UUID, data: DietProductCreate) -> DietProductOut:
        product = self._get(DietProduct, product_id)
        for key, value in data.model_dump().items():
            setattr(product, key, value)
        self.session.commit()
        return DietProductOut.model_validate(product)

    def delete_product(self, product_id: UUID) -> None:
        self.session.delete(self._get(DietProduct, product_id))
        self.session.commit()

    def search_products(self, query: str) -> DietProductSearch:
        local = self.list_products(query)
        try:
            known = {p.off_code for p in local if p.off_code}
            off = [p for p in self.off.search(query) if p.code not in known]
            return DietProductSearch(local=local, off=off)
        except OffUnavailable:
            return DietProductSearch(local=local, off_unavailable=True)

    def _save_off(self, found: DietOffProduct) -> DietProductOut:
        existing = self.session.execute(
            self._scoped(DietProduct).where(DietProduct.off_code == found.code)
        ).scalar_one_or_none()
        if existing:
            return DietProductOut.model_validate(existing)
        product = DietProduct(
            session=self.session,
            **DietProductSave(
                name=found.name[:200],
                brand=found.brand,
                barcode=found.code if BARCODE_RE.fullmatch(found.code) else None,
                unit=found.unit,
                kcal=min(found.kcal, 1000),
                protein=min(found.protein, 100),
                fat=min(found.fat, 100),
                carbs=min(found.carbs, 100),
                portion_name=(found.portion_name or "")[:100] or None,
                portion_grams=found.portion_grams if found.portion_grams and found.portion_grams <= 10000 else None,
                group_id=self.group_id,
                household_id=self.household_id,
                source=DietProductSource.off,
                off_code=found.code,
            ).model_dump(),
        )
        self.session.add(product)
        self.session.commit()
        return DietProductOut.model_validate(product)

    def save_off_product(self, code: str) -> DietProductOut:
        if not BARCODE_RE.fullmatch(code):
            raise ValueError("invalid-code")
        found = self.off.by_barcode(code)
        if found is None:
            raise DietNotFound(f"off:{code}")
        return self._save_off(found)

    def product_by_barcode(self, code: str) -> DietProductOut:
        if not BARCODE_RE.fullmatch(code):
            raise ValueError("invalid-code")
        local = (
            self.session.execute(
                self._scoped(DietProduct).where(sa.or_(DietProduct.barcode == code, DietProduct.off_code == code))
            )
            .scalars()
            .first()
        )
        if local:
            return DietProductOut.model_validate(local)
        try:
            found = self.off.by_barcode(code)
        except OffUnavailable as e:
            raise ValueError("off-unavailable") from e
        if found is None:
            raise DietNotFound(f"barcode:{code}")
        return self._save_off(found)

    # ================================================================
    # Recipes with nutrition (for the freezer and the diary)

    def recipe_options(self) -> list[DietRecipeOption]:
        stmt = (
            sa.select(RecipeModel)
            .where(RecipeModel.group_id == self.group_id)
            .options(sa.orm.lazyload("*"), sa.orm.selectinload(RecipeModel.nutrition))
            .order_by(RecipeModel.name)
        )
        options = []
        for recipe in self.session.execute(stmt).scalars():
            nutrition = recipe.nutrition
            kcal = parse_number(nutrition.calories) if nutrition else 0
            if kcal <= 0:
                continue
            assert nutrition is not None
            options.append(
                DietRecipeOption(
                    id=recipe.id,
                    name=recipe.name or "",
                    slug=recipe.slug or "",
                    servings=recipe.recipe_servings or recipe.recipe_yield_quantity or 1,
                    kcal=kcal,
                    protein=parse_number(nutrition.protein_content),
                    fat=parse_number(nutrition.fat_content),
                    carbs=parse_number(nutrition.carbohydrate_content),
                )
            )
        return options

    def _recipe(self, recipe_id: UUID) -> DietRecipeOption:
        for option in self.recipe_options():
            if option.id == recipe_id:
                return option
        raise DietNotFound(f"recipe:{recipe_id}")

    # ================================================================
    # Freezer

    def _product_macros(self, product_id: UUID) -> tuple[DietProduct, Macros]:
        product = self._get(DietProduct, product_id)
        return product, _macros(product)

    def preview_freezer(self, data: DietFreezerRequest) -> DietFreezerPreview:
        recipe = self._recipe(data.recipe_id)
        changes: list[Change] = []
        names: list[tuple[str, str | None]] = []
        for mod in data.modifications:
            product, per_100 = self._product_macros(mod.product_id)
            replaced_name, replaced = None, None
            if mod.kind is DietModificationKind.swap:
                assert mod.replaced_product_id is not None
                replaced_product, replaced = self._product_macros(mod.replaced_product_id)
                replaced_name = replaced_product.name
            changes.append(Change(mod.kind.value, per_100, mod.grams, replaced, mod.replaced_grams))
            names.append((product.name, replaced_name))

        result = compute_batch(
            per_serving=_macros(recipe),
            servings=data.servings,
            changes=changes,
            molds=[MoldGroup(m.capacity_ml, m.count) for m in data.molds],
            override=Macros(data.override.kcal, data.override.protein, data.override.fat, data.override.carbs)
            if data.override
            else None,
        )
        modifications = []
        for mod, (name, replaced_name), delta in zip(data.modifications, names, result.deltas, strict=True):
            d = delta.rounded()
            modifications.append(
                DietFreezerModificationOut(
                    **mod.model_dump(),
                    product_name=name,
                    replaced_name=replaced_name,
                    delta_kcal=d.kcal,
                    delta_protein=d.protein,
                    delta_fat=d.fat,
                    delta_carbs=d.carbs,
                )
            )
        molds = []
        for mold, per_mold in zip(data.molds, result.per_mold, strict=True):
            m = per_mold.rounded()
            molds.append(
                DietFreezerMoldOut(
                    capacity_ml=mold.capacity_ml,
                    count=mold.count,
                    left=mold.count,
                    kcal=m.kcal,
                    protein=m.protein,
                    fat=m.fat,
                    carbs=m.carbs,
                )
            )
        return DietFreezerPreview(
            recipe_name=recipe.name,
            servings=data.servings,
            base=_out(result.base),
            modifications=modifications,
            override=data.override,
            total=_out(result.total),
            molds=molds,
        )

    def _batch_out(self, batch: DietFreezerBatch) -> DietFreezerBatchOut:
        molds = [DietFreezerMoldOut(**m) for m in batch.molds]
        return DietFreezerBatchOut(
            id=batch.id,
            recipe_id=batch.recipe_id,
            recipe_name=batch.recipe_name,
            frozen_on=batch.frozen_on,
            servings=batch.servings,
            note=batch.note,
            base=DietMacros(**batch.base),
            modifications=[DietFreezerModificationOut(**m) for m in batch.modifications],
            override=DietMacros(**batch.override) if batch.override else None,
            total=DietMacros(**batch.total),
            molds=molds,
            molds_left=sum(m.left for m in molds),
            molds_total=sum(m.count for m in molds),
        )

    def create_freezer_batch(self, data: DietFreezerRequest) -> DietFreezerBatchOut:
        preview = self.preview_freezer(data)
        batch = DietFreezerBatch(
            session=self.session,
            group_id=self.group_id,
            household_id=self.household_id,
            recipe_id=data.recipe_id,
            recipe_name=preview.recipe_name,
            frozen_on=data.frozen_on,
            servings=data.servings,
            note=data.note,
            modifications=[m.model_dump(mode="json") for m in preview.modifications],
            base=preview.base.model_dump(),
            override=preview.override.model_dump() if preview.override else None,
            total=preview.total.model_dump(),
            molds=[m.model_dump() for m in preview.molds],
        )
        self.session.add(batch)
        self.session.commit()
        return self._batch_out(batch)

    def list_freezer(self, include_empty: bool = False) -> list[DietFreezerBatchOut]:
        batches = self.session.execute(
            self._scoped(DietFreezerBatch).order_by(
                DietFreezerBatch.frozen_on.desc(), DietFreezerBatch.created_at.desc()
            )
        ).scalars()
        result = [self._batch_out(b) for b in batches]
        return result if include_empty else [b for b in result if b.molds_left > 0]

    def _change_molds(self, batch: DietFreezerBatch, mold_index: int, delta: float) -> None:
        molds = [dict(m) for m in batch.molds]
        if not 0 <= mold_index < len(molds):
            raise ValueError("invalid-mold")
        left = round(molds[mold_index]["left"] + delta, 2)
        if left < 0:
            raise ValueError("not-enough-molds")
        molds[mold_index]["left"] = min(left, molds[mold_index]["count"])
        batch.molds = molds  # reassign so SQLAlchemy notices the JSON change

    def adjust_freezer(self, batch_id: UUID, data: DietFreezerAdjust) -> DietFreezerBatchOut:
        batch = self._get(DietFreezerBatch, batch_id)
        self._change_molds(batch, data.mold_index, data.delta)
        self.session.commit()
        return self._batch_out(batch)

    def delete_freezer_batch(self, batch_id: UUID) -> None:
        self.session.delete(self._get(DietFreezerBatch, batch_id))
        self.session.commit()

    # ================================================================
    # Diary

    def _person(self, person_id: str):
        for person in self.diet.get_settings().persons:
            if person.id == person_id:
                return person
        raise DietNotFound(f"person:{person_id}")

    def diary_day(self, person_id: str, day: Date) -> DietDiaryDay:
        person = self._person(person_id)
        entries = (
            self.session.execute(
                self._scoped(DietDiaryEntry)
                .where(DietDiaryEntry.person_id == person_id, DietDiaryEntry.date == day)
                .order_by(DietDiaryEntry.created_at)
            )
            .scalars()
            .all()
        )
        totals = Macros()
        for entry in entries:
            totals = totals + _macros(entry)
        return DietDiaryDay(
            person_id=person_id,
            date=day,
            entries=[DietDiaryEntryOut.model_validate(e) for e in entries],
            totals=_out(totals),
            target=DietMacros(kcal=person.kcal, protein=person.protein, fat=person.fat, carbs=person.carbs),
        )

    def add_diary_entry(self, data: DietDiaryCreate, plan_entry_id: int | None = None) -> DietDiaryEntryOut:
        self._person(data.person_id)
        values: dict[str, Any] = {
            "group_id": self.group_id,
            "household_id": self.household_id,
            "person_id": data.person_id,
            "date": data.date,
            "meal_type": data.meal_type.value,
            "kind": data.kind.value,
            "amount": data.amount,
            "plan_entry_id": plan_entry_id,
        }

        if data.kind is DietDiaryKind.product:
            if data.product_id is None:
                raise ValueError("product-required")
            product = self._get(DietProduct, data.product_id)
            if data.amount_unit is DietAmountUnit.portion:
                if not product.portion_grams:
                    raise ValueError("product-has-no-portion")
                grams = data.amount * product.portion_grams
            else:
                grams = data.amount
            nutrition = _macros(product).scaled(grams / 100)
            if data.amount_unit is DietAmountUnit.portion:
                unit = DietAmountUnit.portion
            else:
                unit = DietAmountUnit.millilitres if product.unit == "ml" else DietAmountUnit.grams
            name = product.name
            if unit is DietAmountUnit.portion:
                # "Chleb żytni (1 kromka = 35 g)" – the diary then only needs to show "2 ×"
                portion = product.portion_name or "porcja"
                if not re.search(r"\d\s*(g|ml)\b", portion, re.IGNORECASE):  # e.g. OFF's "1 szklanka (250 ml)"
                    portion = f"{portion} = {product.portion_grams:g} {product.unit}"
                name = f"{product.name} ({portion})"
            values.update(product_id=product.id, amount_unit=unit.value, name=name[:255])

        elif data.kind is DietDiaryKind.recipe:
            if data.recipe_id is None:
                raise ValueError("recipe-required")
            recipe = self._recipe(data.recipe_id)
            nutrition = _macros(recipe).scaled(data.amount)
            values.update(recipe_id=recipe.id, amount_unit=DietAmountUnit.portion.value, name=recipe.name)

        elif data.kind is DietDiaryKind.freezer:
            if data.batch_id is None or data.mold_index is None:
                raise ValueError("freezer-mold-required")
            if round(data.amount * 2) != data.amount * 2:
                raise ValueError("molds-in-halves")
            batch = self._get(DietFreezerBatch, data.batch_id)
            self._change_molds(batch, data.mold_index, -data.amount)
            mold = batch.molds[data.mold_index]
            nutrition = _from_dict(mold).scaled(data.amount)
            capacity = f"{mold['capacity_ml']:g} ml"
            values.update(
                batch_id=batch.id,
                mold_index=data.mold_index,
                amount_unit=DietAmountUnit.mold.value,
                name=f"{batch.recipe_name} ({capacity})",
            )

        else:
            if not data.name or data.kcal is None:
                raise ValueError("quick-needs-name-and-kcal")
            nutrition = Macros(data.kcal, data.protein or 0, data.fat or 0, data.carbs or 0)
            values.update(amount=1, amount_unit=DietAmountUnit.portion.value, name=data.name.strip())

        rounded = nutrition.clamped().rounded()
        entry = DietDiaryEntry(session=self.session, **values, **rounded.as_dict())
        self.session.add(entry)
        self.session.commit()
        return DietDiaryEntryOut.model_validate(entry)

    def delete_diary_entry(self, entry_id: UUID) -> None:
        entry = self._get(DietDiaryEntry, entry_id)
        if entry.kind == DietDiaryKind.freezer.value and entry.batch_id is not None and entry.mold_index is not None:
            batch = self.session.execute(
                self._scoped(DietFreezerBatch).where(DietFreezerBatch.id == entry.batch_id)
            ).scalar_one_or_none()
            if batch is not None and entry.mold_index < len(batch.molds):
                self._change_molds(batch, entry.mold_index, entry.amount)
        self.session.delete(entry)
        self.session.commit()

    def diary_from_plan(self, data: DietDiaryFromPlan) -> DietDiaryFromPlanResult:
        self._person(data.person_id)
        day = data.date.isoformat()
        tracked = [
            t
            for t in self.diet.tracked_entries()
            if t.get("date") == day and t.get("recipe") and data.person_id in (t.get("portions") or {})
        ]
        if not tracked:
            return DietDiaryFromPlanResult(created=0, skipped=0)

        entries = self.repos.meals.page_all(
            PaginationQuery(page=1, per_page=-1, query_filter=f"date >= {day} AND date <= {day}")
        ).items
        current = {e.id: e for e in entries}
        already = set(
            self.session.execute(
                sa.select(DietDiaryEntry.plan_entry_id).where(
                    DietDiaryEntry.household_id == self.household_id,
                    DietDiaryEntry.person_id == data.person_id,
                    DietDiaryEntry.plan_entry_id.in_([t["id"] for t in tracked]),
                )
            ).scalars()
        )

        created = skipped = 0
        for t in tracked:
            entry = current.get(t["id"])
            if entry is None or not tracked_matches(t, entry) or t["id"] in already:
                skipped += 1
                continue
            try:
                self.add_diary_entry(
                    DietDiaryCreate(
                        person_id=data.person_id,
                        date=data.date,
                        meal_type=ENTRY_TYPE_TO_MEAL.get(entry.entry_type.value, MealType.snack),
                        kind=DietDiaryKind.recipe,
                        recipe_id=UUID(t["recipe"]),
                        amount=t["portions"][data.person_id],
                    ),
                    plan_entry_id=t["id"],
                )
                created += 1
            except DietNotFound:
                skipped += 1
        return DietDiaryFromPlanResult(created=created, skipped=skipped)
