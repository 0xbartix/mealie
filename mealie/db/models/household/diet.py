import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import auto_init
from .._model_utils.guid import GUID


class HouseholdDietSettings(SqlAlchemyBase, BaseMixins):
    """Calorie/macro targets and batch-cooking setup of a household (one row per household)."""

    __tablename__ = "household_diet_settings"

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )

    persons: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    cooking_days: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    meal_slots: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    # ids of meal plan entries written by the planner, so regenerating a period only replaces those
    generated_entry_ids: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    eat_next_day: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    shopping_list: Mapped[str] = mapped_column(sa.String, nullable=False, default="period")
    # shopping lists written by the planner: [{id, start, end}]
    generated_list_ids: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class DietProduct(SqlAlchemyBase, BaseMixins):
    """A food with nutrition per 100 g (or 100 ml), entered by hand or saved from Open Food Facts."""

    __tablename__ = "diet_products"

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    brand: FilterableColumn[str | None] = mapped_column(sa.String, nullable=True)
    barcode: FilterableColumn[str | None] = mapped_column(sa.String, nullable=True, index=True)
    unit: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="g")
    kcal: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    protein: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    portion_name: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    portion_grams: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    source: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="custom")
    off_code: FilterableColumn[str | None] = mapped_column(sa.String, nullable=True, index=True)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class DietFreezerBatch(SqlAlchemyBase, BaseMixins):
    """A cooked recipe portioned into freezer molds; macros are fixed when it is frozen."""

    __tablename__ = "diet_freezer_batches"

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    recipe_name: Mapped[str] = mapped_column(sa.String, nullable=False)
    frozen_on: FilterableColumn[datetime.date] = mapped_column(sa.Date, nullable=False, index=True)
    servings: Mapped[float] = mapped_column(sa.Float, nullable=False)
    note: Mapped[str] = mapped_column(sa.String, nullable=False, default="")
    # snapshots: [{kind, product_id, product_name, grams, replaced_..., delta}], {kcal, protein, fat, carbs}
    modifications: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    base: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    override: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    total: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    # [{capacity_ml, count, left, kcal, protein, fat, carbs}] – macros per single mold
    molds: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class DietDiaryEntry(SqlAlchemyBase, BaseMixins):
    """One thing a person ate on a day; nutrition is stored as it was when added."""

    __tablename__ = "diet_diary_entries"

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )

    person_id: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    date: FilterableColumn[datetime.date] = mapped_column(sa.Date, nullable=False, index=True)
    meal_type: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    kind: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    product_id: Mapped[GUID | None] = mapped_column(GUID, nullable=True)
    recipe_id: Mapped[GUID | None] = mapped_column(GUID, nullable=True)
    batch_id: Mapped[GUID | None] = mapped_column(GUID, nullable=True)
    mold_index: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    plan_entry_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    amount: Mapped[float] = mapped_column(sa.Float, nullable=False)
    amount_unit: Mapped[str] = mapped_column(sa.String, nullable=False)
    name: Mapped[str] = mapped_column(sa.String, nullable=False)
    kcal: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    protein: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    fat: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)
    carbs: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0)

    @auto_init()
    def __init__(self, **_) -> None:
        pass
