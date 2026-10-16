import { BaseAPI } from "../base/base-clients";
import type {
  DietDiaryCreate,
  DietDiaryDay,
  DietDiaryEntryOut,
  DietDiaryFromPlanResult,
  DietFreezerBatchOut,
  DietFreezerPreview,
  DietFreezerRequest,
  DietImportReport,
  DietPlanPreview,
  DietPlanRequest,
  DietPlanSaveResult,
  DietProductCreate,
  DietProductOut,
  DietProductSearch,
  DietRecipeIngredient,
  DietRecipeOption,
  DietSettingsOut,
  DietSettingsUpdate,
} from "~/lib/api/types/diet";

const prefix = "/api/households/diet";

const routes = {
  settings: `${prefix}/settings`,
  preview: `${prefix}/plan/preview`,
  save: `${prefix}/plan/save`,
  import: `${prefix}/import`,
  products: `${prefix}/products`,
  product: (id: string) => `${prefix}/products/${id}`,
  productSearch: `${prefix}/products/search`,
  barcode: (code: string) => `${prefix}/products/barcode/${encodeURIComponent(code)}`,
  offProduct: (code: string) => `${prefix}/products/off/${encodeURIComponent(code)}`,
  recipes: `${prefix}/recipes`,
  recipeIngredients: (id: string) => `${prefix}/recipes/${id}/ingredients`,
  freezer: `${prefix}/freezer`,
  freezerPreview: `${prefix}/freezer/preview`,
  freezerBatch: (id: string) => `${prefix}/freezer/${id}`,
  freezerAdjust: (id: string) => `${prefix}/freezer/${id}/adjust`,
  diary: `${prefix}/diary`,
  diaryEntry: (id: string) => `${prefix}/diary/${id}`,
  diaryFromPlan: `${prefix}/diary/from-plan`,
};

export class DietAPI extends BaseAPI {
  async getSettings() {
    return await this.requests.get<DietSettingsOut>(routes.settings);
  }

  async updateSettings(payload: DietSettingsUpdate) {
    return await this.requests.put<DietSettingsOut, DietSettingsUpdate>(routes.settings, payload);
  }

  async preview(payload: DietPlanRequest) {
    return await this.requests.post<DietPlanPreview>(routes.preview, payload);
  }

  async save(payload: DietPlanRequest) {
    return await this.requests.post<DietPlanSaveResult>(routes.save, payload);
  }

  // products
  async listProducts(search?: string) {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    return await this.requests.get<DietProductOut[]>(routes.products + query);
  }

  async createProduct(payload: DietProductCreate) {
    return await this.requests.post<DietProductOut>(routes.products, payload);
  }

  async updateProduct(id: string, payload: DietProductCreate) {
    return await this.requests.put<DietProductOut, DietProductCreate>(routes.product(id), payload);
  }

  async deleteProduct(id: string) {
    return await this.requests.delete(routes.product(id));
  }

  async searchProducts(q: string) {
    return await this.requests.get<DietProductSearch>(`${routes.productSearch}?q=${encodeURIComponent(q)}`);
  }

  async productByBarcode(code: string) {
    return await this.requests.get<DietProductOut>(routes.barcode(code));
  }

  async saveOffProduct(code: string) {
    return await this.requests.post<DietProductOut>(routes.offProduct(code), {});
  }

  async recipeOptions() {
    return await this.requests.get<DietRecipeOption[]>(routes.recipes);
  }

  async recipeIngredients(recipeId: string) {
    return await this.requests.get<DietRecipeIngredient[]>(routes.recipeIngredients(recipeId));
  }

  // freezer
  async listFreezer(includeEmpty = false) {
    return await this.requests.get<DietFreezerBatchOut[]>(`${routes.freezer}?include_empty=${includeEmpty}`);
  }

  async previewFreezer(payload: DietFreezerRequest) {
    return await this.requests.post<DietFreezerPreview>(routes.freezerPreview, payload);
  }

  async createFreezerBatch(payload: DietFreezerRequest) {
    return await this.requests.post<DietFreezerBatchOut>(routes.freezer, payload);
  }

  async adjustFreezer(id: string, moldIndex: number, delta: number) {
    return await this.requests.post<DietFreezerBatchOut>(routes.freezerAdjust(id), { moldIndex, delta });
  }

  async deleteFreezerBatch(id: string) {
    return await this.requests.delete(routes.freezerBatch(id));
  }

  // diary
  async diaryDay(personId: string, date: string) {
    return await this.requests.get<DietDiaryDay>(
      `${routes.diary}?person_id=${encodeURIComponent(personId)}&date=${date}`,
    );
  }

  async addDiaryEntry(payload: DietDiaryCreate) {
    return await this.requests.post<DietDiaryEntryOut>(routes.diary, payload);
  }

  async deleteDiaryEntry(id: string) {
    return await this.requests.delete(routes.diaryEntry(id));
  }

  async diaryFromPlan(personId: string, date: string) {
    return await this.requests.post<DietDiaryFromPlanResult>(routes.diaryFromPlan, { personId, date });
  }

  async importFiles(files: File[]) {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    const { $axios } = useNuxtApp();
    return await $axios.post<DietImportReport>(routes.import, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
}
