import { BaseAPI } from "../base/base-clients";
import type {
  DietImportReport,
  DietPlanPreview,
  DietPlanRequest,
  DietPlanSaveResult,
  DietSettingsOut,
  DietSettingsUpdate,
} from "~/lib/api/types/diet";

const prefix = "/api/households/diet";

const routes = {
  settings: `${prefix}/settings`,
  preview: `${prefix}/plan/preview`,
  save: `${prefix}/plan/save`,
  import: `${prefix}/import`,
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

  async importFiles(files: File[]) {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    const { $axios } = useNuxtApp();
    return await $axios.post<DietImportReport>(routes.import, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
}
