from datetime import date
from functools import cached_property
from uuid import UUID

from fastapi import HTTPException, status

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.routes._base.routers import UserAPIRouter
from mealie.schema.diet.tracking import (
    DietDiaryCreate,
    DietDiaryDay,
    DietDiaryEntryOut,
    DietDiaryFromPlan,
    DietDiaryFromPlanResult,
    DietFreezerAdjust,
    DietFreezerBatchOut,
    DietFreezerPreview,
    DietFreezerRequest,
    DietProductCreate,
    DietProductOut,
    DietProductSearch,
    DietRecipeOption,
)
from mealie.schema.response.responses import ErrorResponse
from mealie.services.diet import off_client
from mealie.services.diet.diet_service import DietService
from mealie.services.diet.tracking_service import DietNotFound, DietTrackingService

router = UserAPIRouter(prefix="/households/diet", tags=["Households: Diet Tracking"])


@controller(router)
class DietTrackingController(BaseUserController):
    @cached_property
    def service(self) -> DietTrackingService:
        diet = DietService(self.repos, self.user, self.household, self.translator)
        return DietTrackingService(self.repos, self.household, diet, off_client.get_off_client())

    def _run(self, fn, *args):
        try:
            return fn(*args)
        except DietNotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ErrorResponse.respond(message="not-found")) from e
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ErrorResponse.respond(message=str(e))) from e

    # ---------------------------------------------------------------- products

    @router.get("/products", response_model=list[DietProductOut])
    def list_products(self, search: str | None = None):
        return self.service.list_products(search)

    @router.post("/products", response_model=DietProductOut, status_code=201)
    def create_product(self, data: DietProductCreate):
        return self.service.create_product(data)

    @router.get("/products/search", response_model=DietProductSearch)
    def search_products(self, q: str):
        return self._run(self.service.search_products, q)

    @router.get("/products/barcode/{code}", response_model=DietProductOut)
    def product_by_barcode(self, code: str):
        return self._run(self.service.product_by_barcode, code)

    @router.post("/products/off/{code}", response_model=DietProductOut, status_code=201)
    def save_off_product(self, code: str):
        return self._run(self.service.save_off_product, code)

    @router.put("/products/{product_id}", response_model=DietProductOut)
    def update_product(self, product_id: UUID, data: DietProductCreate):
        return self._run(self.service.update_product, product_id, data)

    @router.delete("/products/{product_id}", status_code=204)
    def delete_product(self, product_id: UUID):
        self._run(self.service.delete_product, product_id)

    @router.get("/recipes", response_model=list[DietRecipeOption])
    def recipe_options(self):
        return self.service.recipe_options()

    # ---------------------------------------------------------------- freezer

    @router.get("/freezer", response_model=list[DietFreezerBatchOut])
    def list_freezer(self, include_empty: bool = False):
        return self.service.list_freezer(include_empty)

    @router.post("/freezer/preview", response_model=DietFreezerPreview)
    def preview_freezer(self, data: DietFreezerRequest):
        return self._run(self.service.preview_freezer, data)

    @router.post("/freezer", response_model=DietFreezerBatchOut, status_code=201)
    def create_freezer_batch(self, data: DietFreezerRequest):
        return self._run(self.service.create_freezer_batch, data)

    @router.post("/freezer/{batch_id}/adjust", response_model=DietFreezerBatchOut)
    def adjust_freezer(self, batch_id: UUID, data: DietFreezerAdjust):
        return self._run(self.service.adjust_freezer, batch_id, data)

    @router.delete("/freezer/{batch_id}", status_code=204)
    def delete_freezer_batch(self, batch_id: UUID):
        self._run(self.service.delete_freezer_batch, batch_id)

    # ---------------------------------------------------------------- diary

    @router.get("/diary", response_model=DietDiaryDay)
    def diary_day(self, person_id: str, date: date):
        return self._run(self.service.diary_day, person_id, date)

    @router.post("/diary", response_model=DietDiaryEntryOut, status_code=201)
    def add_diary_entry(self, data: DietDiaryCreate):
        return self._run(self.service.add_diary_entry, data)

    @router.post("/diary/from-plan", response_model=DietDiaryFromPlanResult)
    def diary_from_plan(self, data: DietDiaryFromPlan):
        return self._run(self.service.diary_from_plan, data)

    @router.delete("/diary/{entry_id}", status_code=204)
    def delete_diary_entry(self, entry_id: UUID):
        self._run(self.service.delete_diary_entry, entry_id)
