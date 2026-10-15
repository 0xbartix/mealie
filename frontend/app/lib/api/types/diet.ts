/* tslint:disable */

/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type DietImportStatus = "created" | "updated" | "error";
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export interface DietImportReport {
  results: DietImportResult[];
}
export interface DietImportResult {
  fileName: string;
  status: DietImportStatus;
  recipeName?: string | null;
  recipeSlug?: string | null;
  errors?: string[];
  warnings?: string[];
}
export interface DietMealSlot {
  mealType: MealType;
  share: number;
}
export interface DietPerson {
  id?: string;
  name: string;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
  active?: boolean;
}
export interface DietPlanBatch {
  index: number;
  startDate: string;
  endDate: string;
  days: number;
  slots: DietPlanSlot[];
  totals: DietPlanTotals[];
}
export interface DietPlanSlot {
  slotIndex: number;
  mealType: MealType;
  recipe?: DietPlanRecipe | null;
  portions?: DietPlanPortion[];
  portionsPerDay?: number;
  portionsPerBatch?: number;
  candidatesCount?: number;
}
export interface DietPlanRecipe {
  id: string;
  name: string;
  slug: string;
  servings: number;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}
export interface DietPlanPortion {
  personId: string;
  portions: number;
  kcal: number;
}
export interface DietPlanTotals {
  personId: string;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}
export interface DietPlanPreview {
  seed: number;
  batches: DietPlanBatch[];
  warnings?: string[];
}
export interface DietPlanRequest {
  startDate: string;
  endDate: string;
  seed?: number | null;
  locked?: {
    [k: string]: {
      [k: string]: string;
    };
  };
  excluded?: {
    [k: string]: {
      [k: string]: string[];
    };
  };
}
export interface DietPlanSaveResult {
  created: number;
  removed: number;
}
export interface DietSettingsOut {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
  groupId: string;
  householdId: string;
  id: string;
}
export interface DietSettingsSave {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
  groupId: string;
  householdId: string;
}
export interface DietSettingsUpdate {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
}
