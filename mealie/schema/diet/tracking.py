from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import UUID4, ConfigDict, Field, field_validator, model_validator

from mealie.schema._mealie import MealieModel
from mealie.services.diet.recipe_file import MealType

# ================================================================
# Products


class DietProductUnit(StrEnum):
    g = "g"
    ml = "ml"


class DietProductSource(StrEnum):
    custom = "custom"
    off = "off"


class DietMacros(MealieModel):
    kcal: Annotated[float, Field(ge=0)] = 0
    protein: Annotated[float, Field(ge=0)] = 0
    fat: Annotated[float, Field(ge=0)] = 0
    carbs: Annotated[float, Field(ge=0)] = 0


class DietProductCreate(MealieModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    brand: str | None = None
    barcode: Annotated[str | None, Field(max_length=32)] = None
    unit: DietProductUnit = DietProductUnit.g
    # per 100 g / 100 ml
    kcal: Annotated[float, Field(ge=0, le=1000)]
    protein: Annotated[float, Field(ge=0, le=100)] = 0
    fat: Annotated[float, Field(ge=0, le=100)] = 0
    carbs: Annotated[float, Field(ge=0, le=100)] = 0
    portion_name: Annotated[str | None, Field(max_length=100)] = None
    portion_grams: Annotated[float | None, Field(gt=0, le=10000)] = None

    @field_validator("barcode", "brand", "portion_name")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value else None


class DietProductSave(DietProductCreate):
    group_id: UUID4
    household_id: UUID4
    source: DietProductSource = DietProductSource.custom
    off_code: str | None = None


class DietProductOut(DietProductSave):
    id: UUID4
    model_config = ConfigDict(from_attributes=True)


class DietOffProduct(MealieModel):
    """A product found in Open Food Facts, not saved yet."""

    code: str
    name: str
    brand: str | None = None
    quantity: str | None = None
    unit: DietProductUnit = DietProductUnit.g
    kcal: float
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    portion_name: str | None = None
    portion_grams: float | None = None


class DietProductSearch(MealieModel):
    local: list[DietProductOut] = []
    off: list[DietOffProduct] = []
    off_unavailable: bool = False


# ================================================================
# Freezer


class DietModificationKind(StrEnum):
    add = "add"
    remove = "remove"
    swap = "swap"


class DietModification(MealieModel):
    kind: DietModificationKind
    product_id: UUID4
    grams: Annotated[float, Field(gt=0, le=100000)]
    replaced_product_id: UUID4 | None = None
    replaced_grams: Annotated[float | None, Field(gt=0, le=100000)] = None

    @model_validator(mode="after")
    def swap_needs_replaced(self):
        if self.kind is DietModificationKind.swap and (self.replaced_product_id is None or self.replaced_grams is None):
            raise ValueError("a swap needs the replaced product and its amount")
        return self


class DietMold(MealieModel):
    capacity_ml: Annotated[float, Field(gt=0, le=10000)]
    count: Annotated[int, Field(ge=1, le=500)]


class DietFreezerRequest(MealieModel):
    recipe_id: UUID4
    frozen_on: date
    servings: Annotated[float, Field(gt=0, le=1000)]
    modifications: list[DietModification] = []
    override: DietMacros | None = None
    molds: Annotated[list[DietMold], Field(min_length=1, max_length=10)]
    note: Annotated[str, Field(max_length=500)] = ""


class DietFreezerModificationOut(DietModification):
    product_name: str
    replaced_name: str | None = None
    delta_kcal: float
    delta_protein: float
    delta_fat: float
    delta_carbs: float


class DietFreezerMoldOut(DietMold):
    left: float
    kcal: float
    protein: float
    fat: float
    carbs: float


class DietFreezerPreview(MealieModel):
    recipe_name: str
    servings: float
    base: DietMacros
    modifications: list[DietFreezerModificationOut]
    override: DietMacros | None = None
    total: DietMacros
    molds: list[DietFreezerMoldOut]


class DietFreezerBatchOut(DietFreezerPreview):
    id: UUID4
    recipe_id: UUID4 | None = None
    frozen_on: date
    note: str = ""
    molds_left: float = 0
    molds_total: int = 0


class DietFreezerAdjust(MealieModel):
    mold_index: Annotated[int, Field(ge=0)]
    delta: Annotated[float, Field(ge=-500, le=500)]


# ================================================================
# Diary


class DietDiaryKind(StrEnum):
    product = "product"
    recipe = "recipe"
    freezer = "freezer"
    quick = "quick"


class DietAmountUnit(StrEnum):
    grams = "g"
    portion = "portion"
    mold = "mold"


class DietDiaryCreate(MealieModel):
    person_id: Annotated[str, Field(min_length=1)]
    date: date
    meal_type: MealType
    kind: DietDiaryKind
    amount: Annotated[float, Field(gt=0, le=100000)] = 1
    amount_unit: DietAmountUnit = DietAmountUnit.portion
    product_id: UUID4 | None = None
    recipe_id: UUID4 | None = None
    batch_id: UUID4 | None = None
    mold_index: Annotated[int | None, Field(ge=0)] = None
    # quick entries
    name: Annotated[str | None, Field(max_length=200)] = None
    kcal: Annotated[float | None, Field(ge=0, le=20000)] = None
    protein: Annotated[float | None, Field(ge=0, le=2000)] = None
    fat: Annotated[float | None, Field(ge=0, le=2000)] = None
    carbs: Annotated[float | None, Field(ge=0, le=2000)] = None


class DietDiaryEntryOut(MealieModel):
    id: UUID4
    person_id: str
    date: date
    meal_type: MealType
    kind: DietDiaryKind
    amount: float
    amount_unit: DietAmountUnit
    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    product_id: UUID4 | None = None
    recipe_id: UUID4 | None = None
    batch_id: UUID4 | None = None
    mold_index: int | None = None
    plan_entry_id: int | None = None
    model_config = ConfigDict(from_attributes=True)


class DietDiaryDay(MealieModel):
    person_id: str
    date: date
    entries: list[DietDiaryEntryOut]
    totals: DietMacros
    target: DietMacros | None = None


class DietDiaryFromPlan(MealieModel):
    person_id: Annotated[str, Field(min_length=1)]
    date: date


class DietDiaryFromPlanResult(MealieModel):
    created: int
    skipped: int


class DietRecipeOption(MealieModel):
    id: UUID4
    name: str
    slug: str
    servings: float
    kcal: float
    protein: float
    fat: float
    carbs: float
