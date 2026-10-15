from datetime import date
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import UUID4, ConfigDict, Field, field_validator, model_validator

from mealie.schema._mealie import MealieModel
from mealie.services.diet.recipe_file import MealType

MAX_PLAN_DAYS = 62


class DietMealSlot(MealieModel):
    meal_type: MealType
    share: Annotated[float, Field(gt=0, le=100)]  # percent of the daily kcal


class DietPerson(MealieModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: Annotated[str, Field(min_length=1, max_length=50)]
    kcal: Annotated[float, Field(gt=0, le=10000)]
    protein: Annotated[float, Field(ge=0, le=1000)]
    fat: Annotated[float, Field(ge=0, le=1000)]
    carbs: Annotated[float, Field(ge=0, le=2000)]
    active: bool = True


def default_meal_slots() -> list[DietMealSlot]:
    return [
        DietMealSlot(meal_type=MealType.breakfast, share=30),
        DietMealSlot(meal_type=MealType.lunch, share=40),
        DietMealSlot(meal_type=MealType.dinner, share=30),
    ]


class DietSettingsUpdate(MealieModel):
    persons: list[DietPerson] = []
    cooking_days: list[int] = [6]  # 0 = Monday ... 6 = Sunday
    meal_slots: list[DietMealSlot] = Field(default_factory=default_meal_slots)

    @field_validator("cooking_days")
    @classmethod
    def validate_cooking_days(cls, value: list[int]) -> list[int]:
        days = sorted(set(value))
        if not days:
            raise ValueError("at least one cooking day is required")
        if any(d < 0 or d > 6 for d in days):
            raise ValueError("cooking days must be between 0 (Monday) and 6 (Sunday)")
        return days

    @field_validator("meal_slots")
    @classmethod
    def validate_meal_slots(cls, value: list[DietMealSlot]) -> list[DietMealSlot]:
        if not 1 <= len(value) <= 6:
            raise ValueError("between 1 and 6 meals per day are supported")
        if abs(sum(s.share for s in value) - 100) > 0.5:
            raise ValueError("meal shares must add up to 100%")
        return value


class DietSettingsSave(DietSettingsUpdate):
    group_id: UUID4
    household_id: UUID4


class DietSettingsOut(DietSettingsSave):
    id: UUID4
    model_config = ConfigDict(from_attributes=True)


class DietPlanRequest(MealieModel):
    start_date: date
    end_date: date
    seed: int | None = None
    locked: dict[int, dict[int, UUID4]] = {}
    excluded: dict[int, dict[int, list[UUID4]]] = {}

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date < self.start_date:
            raise ValueError("end date must not be before start date")
        if (self.end_date - self.start_date).days + 1 > MAX_PLAN_DAYS:
            raise ValueError(f"a plan can cover at most {MAX_PLAN_DAYS} days")
        return self


class DietPlanRecipe(MealieModel):
    id: UUID4
    name: str
    slug: str
    servings: float
    kcal: float
    protein: float
    fat: float
    carbs: float


class DietPlanPortion(MealieModel):
    person_id: str
    portions: float
    kcal: float


class DietPlanSlot(MealieModel):
    slot_index: int
    meal_type: MealType
    recipe: DietPlanRecipe | None = None
    portions: list[DietPlanPortion] = []
    portions_per_day: float = 0
    portions_per_batch: float = 0
    candidates_count: int = 0


class DietPlanTotals(MealieModel):
    person_id: str
    kcal: float
    protein: float
    fat: float
    carbs: float


class DietPlanBatch(MealieModel):
    index: int
    start_date: date
    end_date: date
    days: int
    slots: list[DietPlanSlot]
    totals: list[DietPlanTotals]


class DietPlanPreview(MealieModel):
    seed: int
    batches: list[DietPlanBatch]
    warnings: list[str] = []


class DietPlanSaveResult(MealieModel):
    created: int
    removed: int


class DietImportStatus(StrEnum):
    created = "created"
    updated = "updated"
    error = "error"


class DietImportResult(MealieModel):
    file_name: str
    status: DietImportStatus
    recipe_name: str | None = None
    recipe_slug: str | None = None
    errors: list[str] = []
    warnings: list[str] = []


class DietImportReport(MealieModel):
    results: list[DietImportResult]
