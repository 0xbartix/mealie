from functools import cached_property

from fastapi import File, HTTPException, UploadFile, status

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.routes._base.routers import UserAPIRouter
from mealie.schema.diet.diet import (
    DietImportReport,
    DietPlanPreview,
    DietPlanRequest,
    DietPlanSaveResult,
    DietSettingsOut,
    DietSettingsUpdate,
)
from mealie.schema.response.responses import ErrorResponse
from mealie.services.diet.diet_service import DietService

router = UserAPIRouter(prefix="/households/diet", tags=["Households: Diet Plan"])


@controller(router)
class DietController(BaseUserController):
    @cached_property
    def service(self) -> DietService:
        return DietService(self.repos, self.user, self.household, self.translator)

    @router.get("/settings", response_model=DietSettingsOut)
    def get_settings(self):
        return self.service.get_settings()

    @router.put("/settings", response_model=DietSettingsOut)
    def update_settings(self, data: DietSettingsUpdate):
        return self.service.update_settings(data)

    @router.post("/plan/preview", response_model=DietPlanPreview)
    def preview_plan(self, data: DietPlanRequest):
        try:
            return self.service.preview(data)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ErrorResponse.respond(message=str(e))) from e

    @router.post("/plan/save", response_model=DietPlanSaveResult)
    def save_plan(self, data: DietPlanRequest):
        try:
            return self.service.save(data)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ErrorResponse.respond(message=str(e))) from e

    @router.post("/import", response_model=DietImportReport)
    def import_recipe_files(self, files: list[UploadFile] = File(...)):
        contents = [(f.filename or "plik", f.file.read()) for f in files]
        try:
            return self.service.import_files(contents)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ErrorResponse.respond(message=str(e))) from e
