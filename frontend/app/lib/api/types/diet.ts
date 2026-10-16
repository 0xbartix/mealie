/* tslint:disable */

/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type DietDiaryKind = "product" | "recipe" | "freezer" | "quick";
export type DietAmountUnit = "g" | "portion" | "mold";
export type DietModificationKind = "add" | "remove" | "swap";
export type DietImportStatus = "created" | "updated" | "error";
export type DietProductUnit = "g" | "ml";
export type DietProductSource = "custom" | "off";
export type DietShoppingListMode = "period" | "batch" | "none";

export interface DietDiaryCreate {
  personId: string;
  date: string;
  mealType: MealType;
  kind: DietDiaryKind;
  amount?: number;
  amountUnit?: DietAmountUnit;
  productId?: string | null;
  recipeId?: string | null;
  batchId?: string | null;
  moldIndex?: number | null;
  name?: string | null;
  kcal?: number | null;
  protein?: number | null;
  fat?: number | null;
  carbs?: number | null;
}
export interface DietDiaryDay {
  personId: string;
  date: string;
  entries: DietDiaryEntryOut[];
  totals: DietMacros;
  target?: DietMacros | null;
}
export interface DietDiaryEntryOut {
  id: string;
  personId: string;
  date: string;
  mealType: MealType;
  kind: DietDiaryKind;
  amount: number;
  amountUnit: DietAmountUnit;
  name: string;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
  productId?: string | null;
  recipeId?: string | null;
  batchId?: string | null;
  moldIndex?: number | null;
  planEntryId?: number | null;
}
export interface DietMacros {
  kcal?: number;
  protein?: number;
  fat?: number;
  carbs?: number;
}
export interface DietDiaryFromPlan {
  personId: string;
  date: string;
}
export interface DietDiaryFromPlanResult {
  created: number;
  skipped: number;
}
export interface DietFreezerAdjust {
  moldIndex: number;
  delta: number;
}
export interface DietFreezerBatchOut {
  recipeName: string;
  servings: number;
  base: DietMacros;
  modifications: DietFreezerModificationOut[];
  override?: DietMacros | null;
  total: DietMacros;
  molds: DietFreezerMoldOut[];
  id: string;
  recipeId?: string | null;
  frozenOn: string;
  note?: string;
  moldsLeft?: number;
  moldsTotal?: number;
}
export interface DietFreezerModificationOut {
  kind: DietModificationKind;
  productId: string;
  grams: number;
  replacedProductId?: string | null;
  replacedGrams?: number | null;
  productName: string;
  replacedName?: string | null;
  deltaKcal: number;
  deltaProtein: number;
  deltaFat: number;
  deltaCarbs: number;
}
export interface DietFreezerMoldOut {
  capacityMl: number;
  count: number;
  left: number;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}
export interface DietFreezerPreview {
  recipeName: string;
  servings: number;
  base: DietMacros;
  modifications: DietFreezerModificationOut[];
  override?: DietMacros | null;
  total: DietMacros;
  molds: DietFreezerMoldOut[];
}
export interface DietFreezerRequest {
  recipeId: string;
  frozenOn: string;
  servings: number;
  modifications?: DietModification[];
  override?: DietMacros | null;
  molds:
    | [DietMold]
    | [DietMold, DietMold]
    | [DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold]
    | [DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold, DietMold];
  note?: string;
}
export interface DietModification {
  kind: DietModificationKind;
  productId: string;
  grams: number;
  replacedProductId?: string | null;
  replacedGrams?: number | null;
}
export interface DietMold {
  capacityMl: number;
  count: number;
}
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
export interface DietOffProduct {
  code: string;
  name: string;
  brand?: string | null;
  quantity?: string | null;
  unit?: DietProductUnit;
  kcal: number;
  protein?: number;
  fat?: number;
  carbs?: number;
  portionName?: string | null;
  portionGrams?: number | null;
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
  cookDate: string;
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
  shoppingLists?: DietShoppingListRef[];
}
export interface DietShoppingListRef {
  id: string;
  name: string;
}
export interface DietProductCreate {
  name: string;
  brand?: string | null;
  barcode?: string | null;
  unit?: DietProductUnit;
  kcal: number;
  protein?: number;
  fat?: number;
  carbs?: number;
  portionName?: string | null;
  portionGrams?: number | null;
}
export interface DietProductOut {
  name: string;
  brand?: string | null;
  barcode?: string | null;
  unit?: DietProductUnit;
  kcal: number;
  protein?: number;
  fat?: number;
  carbs?: number;
  portionName?: string | null;
  portionGrams?: number | null;
  groupId: string;
  householdId: string;
  source?: DietProductSource;
  offCode?: string | null;
  id: string;
}
export interface DietProductSave {
  name: string;
  brand?: string | null;
  barcode?: string | null;
  unit?: DietProductUnit;
  kcal: number;
  protein?: number;
  fat?: number;
  carbs?: number;
  portionName?: string | null;
  portionGrams?: number | null;
  groupId: string;
  householdId: string;
  source?: DietProductSource;
  offCode?: string | null;
}
export interface DietProductSearch {
  local?: DietProductOut[];
  off?: DietOffProduct[];
  offUnavailable?: boolean;
}
export interface DietRecipeOption {
  id: string;
  name: string;
  slug: string;
  servings: number;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}
export interface DietSettingsOut {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
  eatNextDay?: boolean;
  shoppingList?: DietShoppingListMode;
  groupId: string;
  householdId: string;
  id: string;
}
export interface DietSettingsSave {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
  eatNextDay?: boolean;
  shoppingList?: DietShoppingListMode;
  groupId: string;
  householdId: string;
}
export interface DietSettingsUpdate {
  persons?: DietPerson[];
  cookingDays?: number[];
  mealSlots?: DietMealSlot[];
  eatNextDay?: boolean;
  shoppingList?: DietShoppingListMode;
}
