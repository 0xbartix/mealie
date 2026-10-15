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

    @auto_init()
    def __init__(self, **_) -> None:
        pass
