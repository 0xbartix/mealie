<template>
  <v-dialog v-model="open" max-width="760" scrollable>
    <v-card>
      <v-card-title>{{ $t("diet.freeze-recipe") }}</v-card-title>
      <v-divider />
      <v-card-text>
        <v-row density="compact">
          <v-col cols="12" sm="7">
            <v-autocomplete
              v-model="recipeId"
              :items="recipes"
              item-title="name"
              item-value="id"
              :label="$t('diet.recipe')"
              density="compact"
              auto-select-first
              :custom-filter="foldFilter"
            />
          </v-col>
          <v-col cols="6" sm="3">
            <v-text-field v-model="frozenOn" type="date" :label="$t('diet.frozen-on')" density="compact" />
          </v-col>
          <v-col cols="6" sm="2">
            <v-text-field
              v-model.number="servings"
              type="number"
              min="0.25"
              step="0.25"
              :label="$t('diet.servings-cooked')"
              density="compact"
            />
          </v-col>
        </v-row>

        <BaseCardSectionTitle :title="$t('diet.changes')" size="small">
          {{ $t("diet.changes-description") }}
        </BaseCardSectionTitle>
        <div v-if="ingredients.length" class="mb-3">
          <div class="text-caption text-medium-emphasis mb-1">
            {{ $t("diet.recipe-ingredients-hint") }}
          </div>
          <div class="d-flex flex-wrap ga-1">
            <v-menu v-for="(ingredient, i) in ingredients" :key="i">
              <template #activator="{ props: menuProps }">
                <v-chip v-bind="menuProps" size="small" variant="outlined">
                  {{ ingredient.text }}
                </v-chip>
              </template>
              <v-list density="compact">
                <v-list-item :title="$t('diet.ingredient-skipped')" @click="fromIngredient(ingredient, 'skipped')" />
                <v-list-item :title="$t('diet.ingredient-less')" @click="fromIngredient(ingredient, 'less')" />
                <v-list-item :title="$t('diet.ingredient-swapped')" @click="fromIngredient(ingredient, 'swapped')" />
              </v-list>
            </v-menu>
          </div>
        </div>
        <div v-for="(change, index) in changes" :key="index" class="d-flex flex-wrap align-center ga-2 mb-2">
          <span v-if="change.ingredient" class="text-caption text-medium-emphasis w-100">
            {{ $t(change.less ? "diet.from-recipe-less" : "diet.from-recipe", { text: change.ingredient }) }}
          </span>
          <v-select
            :model-value="change.kind"
            :items="kinds"
            density="compact"
            hide-details
            style="max-width: 190px"
            @update:model-value="changeKind(change, $event)"
          />
          <template v-if="change.kind === 'swap'">
            <v-btn variant="outlined" size="small" @click="pick(index, 'replaced')">
              {{ change.replacedName || $t("diet.pick-product") }}
            </v-btn>
            <v-text-field
              v-model.number="change.replacedGrams"
              type="number"
              min="0"
              suffix="g"
              density="compact"
              hide-details
              style="max-width: 100px"
            />
            <span class="text-medium-emphasis">→</span>
          </template>
          <v-btn variant="outlined" size="small" @click="pick(index, 'product')">
            {{ change.productName || $t("diet.pick-product") }}
          </v-btn>
          <v-text-field
            v-model.number="change.grams"
            type="number"
            min="0"
            suffix="g"
            density="compact"
            hide-details
            style="max-width: 100px"
          />
          <span v-if="preview?.modifications[index]" class="text-caption" :class="preview.modifications[index]!.deltaKcal >= 0 ? 'text-success' : 'text-error'">
            {{ signed(preview.modifications[index]!.deltaKcal) }} kcal
          </span>
          <v-btn icon variant="text" size="x-small" color="error" @click="changes.splice(index, 1)">
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>
        <v-btn variant="text" size="small" class="mb-4" :prepend-icon="$globals.icons.createAlt" @click="addChange">
          {{ $t("diet.add-change") }}
        </v-btn>

        <BaseCardSectionTitle :title="$t('diet.molds')" size="small">
          {{ $t("diet.molds-description") }}
        </BaseCardSectionTitle>
        <div v-for="(mold, index) in molds" :key="`m${index}`" class="d-flex flex-wrap align-center ga-2 mb-2">
          <v-combobox
            v-model.number="mold.capacityMl"
            :items="capacityPresets"
            :label="$t('diet.mold-capacity')"
            suffix="ml"
            density="compact"
            hide-details
            style="max-width: 170px"
          />
          <span>×</span>
          <v-text-field
            v-model.number="mold.count"
            type="number"
            min="1"
            :label="$t('diet.mold-count')"
            density="compact"
            hide-details
            style="max-width: 110px"
          />
          <span v-if="preview?.molds[index]" class="text-caption text-medium-emphasis">
            {{ $t("diet.per-mold") }}: {{ Math.round(preview.molds[index]!.kcal) }} kcal · B {{ preview.molds[index]!.protein }} · T {{ preview.molds[index]!.fat }} · W {{ preview.molds[index]!.carbs }}
          </span>
          <v-btn
            v-if="molds.length > 1"
            icon
            variant="text"
            size="x-small"
            color="error"
            @click="molds.splice(index, 1)"
          >
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>
        <v-btn variant="text" size="small" :prepend-icon="$globals.icons.createAlt" @click="molds.push({ capacityMl: 250, count: 1 })">
          {{ $t("diet.add-mold-size") }}
        </v-btn>

        <v-card v-if="preview" variant="tonal" class="mt-4">
          <v-card-text>
            <div class="text-caption text-medium-emphasis">
              {{ $t("diet.batch-base", { servings: preview.servings }) }}
            </div>
            <DietMacroLine :macros="preview.base" class="mb-2" />
            <div class="text-caption text-medium-emphasis">
              {{ $t("diet.batch-total") }}
            </div>
            <DietMacroLine :macros="preview.total" />
            <v-switch
              v-model="manual"
              :label="$t('diet.manual-total')"
              color="primary"
              density="compact"
              hide-details
              class="mt-2"
            />
            <v-row v-if="manual" density="compact">
              <v-col cols="6" sm="3">
                <v-text-field
                  v-model.number="override.kcal"
                  type="number"
                  min="0"
                  label="kcal"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field
                  v-model.number="override.protein"
                  type="number"
                  min="0"
                  :label="$t('diet.protein')"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field
                  v-model.number="override.fat"
                  type="number"
                  min="0"
                  :label="$t('diet.fat')"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field
                  v-model.number="override.carbs"
                  type="number"
                  min="0"
                  :label="$t('diet.carbs')"
                  density="compact"
                  hide-details
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <v-text-field v-model="note" :label="$t('diet.note')" density="compact" class="mt-4" hide-details />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <BaseButton cancel @click="open = false" />
        <BaseButton save :disabled="!request" :loading="saving" @click="save">
          {{ $t("diet.put-in-freezer") }}
        </BaseButton>
      </v-card-actions>
    </v-card>

    <v-dialog v-model="pickerOpen" max-width="560">
      <v-card>
        <v-card-title>{{ $t("diet.pick-product") }}</v-card-title>
        <v-card-text>
          <DietProductPicker v-if="pickerOpen" :initial-query="pickQuery" @select="picked" />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup lang="ts">
import DietMacroLine from "./DietMacroLine.vue";
import DietProductPicker from "./DietProductPicker.vue";
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type {
  DietFreezerPreview,
  DietFreezerRequest,
  DietMacros,
  DietModificationKind,
  DietProductOut,
  DietRecipeIngredient,
  DietRecipeOption,
} from "~/lib/api/types/diet";

const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ saved: [] }>();

const api = useUserApi();
const i18n = useI18n();

interface ChangeRow {
  kind: DietModificationKind;
  productId: string | null;
  productName: string;
  grams: number | null;
  replacedProductId: string | null;
  replacedName: string;
  replacedGrams: number | null;
  ingredient?: string; // the recipe line this change is about
  less?: boolean; // "used less": the grams are how much less
  pieces?: number | null; // e.g. "2 szt" – turned into grams once a product with a portion weight is picked
}

function today() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const recipes = ref<DietRecipeOption[]>([]);
const ingredients = ref<DietRecipeIngredient[]>([]);
const recipeId = ref<string | null>(null);
const frozenOn = ref(today());
const servings = ref<number>(4);
const changes = ref<ChangeRow[]>([]);
const molds = ref([{ capacityMl: 500 as number, count: 4 as number }]);
const manual = ref(false);
const override = ref<DietMacros>({ kcal: 0, protein: 0, fat: 0, carbs: 0 });
const note = ref("");
const preview = ref<DietFreezerPreview | null>(null);
const saving = ref(false);

const capacityPresets = [15, 125, 250, 500, 1000];
const kinds = computed(() => [
  { value: "add", title: i18n.t("diet.change-add") },
  { value: "remove", title: i18n.t("diet.change-remove") },
  { value: "swap", title: i18n.t("diet.change-swap") },
]);

// a cleared number field gives "" – treat it as empty, not as 0
function num(value: unknown): number | null {
  return value === "" || value === null || value === undefined || Number.isNaN(Number(value)) ? null : Number(value);
}

function fold(text: string) {
  return text.toLowerCase().replaceAll("ł", "l").normalize("NFKD").replace(/[̀-ͯ]/g, "");
}
function foldFilter(value: string, query: string) {
  return fold(value).includes(fold(query));
}
function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${Math.round(value)}`;
}

function addChange() {
  changes.value.push({ kind: "add", productId: null, productName: "", grams: null, replacedProductId: null, replacedName: "", replacedGrams: null });
}

// product picker for a change row
const pickerOpen = ref(false);
const pickQuery = ref("");
const pickTarget = ref<{ index: number; field: "product" | "replaced" } | null>(null);
function pick(index: number, field: "product" | "replaced", query = "") {
  pickTarget.value = { index, field };
  pickQuery.value = query;
  pickerOpen.value = true;
}

// a change that starts from a recipe ingredient: amounts are for the servings cooked, not the recipe's
function fromIngredient(ingredient: DietRecipeIngredient, mode: "skipped" | "less" | "swapped") {
  const recipe = recipes.value.find(r => r.id === recipeId.value);
  const scale = recipe?.servings ? (num(servings.value) ?? recipe.servings) / recipe.servings : 1;
  const grams = ingredient.grams ? Math.round(ingredient.grams * scale) : null;
  changes.value.push({
    kind: mode === "swapped" ? "swap" : "remove",
    productId: null,
    productName: "",
    grams: mode === "less" ? null : grams,
    replacedProductId: null,
    replacedName: "",
    replacedGrams: mode === "swapped" ? grams : null,
    ingredient: ingredient.text,
    less: mode === "less",
    pieces: !ingredient.grams && ingredient.quantity ? ingredient.quantity * scale : null,
  });
  pick(changes.value.length - 1, mode === "swapped" ? "replaced" : "product", ingredient.name);
}

// switching to "swapped" keeps what was picked as the replaced product, and back again
function changeKind(row: ChangeRow, kind: DietModificationKind) {
  if (kind === "swap" && row.kind !== "swap" && !row.replacedProductId) {
    row.replacedProductId = row.productId;
    row.replacedName = row.productName;
    row.replacedGrams = row.grams;
    row.productId = null;
    row.productName = "";
  }
  else if (kind !== "swap" && row.kind === "swap" && !row.productId) {
    row.productId = row.replacedProductId;
    row.productName = row.replacedName;
    row.grams = row.replacedGrams;
  }
  row.kind = kind;
  row.less = false;
}
function picked(product: DietProductOut) {
  const target = pickTarget.value;
  const row = target ? changes.value[target.index] : undefined;
  if (target && row) {
    const fromPieces = row.pieces && product.portionGrams ? Math.round(row.pieces * product.portionGrams) : null;
    if (target.field === "product") {
      row.productId = product.id;
      row.productName = product.name;
      if (row.grams === null && !row.less) {
        row.grams = fromPieces;
      }
    }
    else {
      row.replacedProductId = product.id;
      row.replacedName = product.name;
      if (row.replacedGrams === null) {
        row.replacedGrams = fromPieces;
      }
      if (row.grams === null) {
        row.grams = row.replacedGrams;
      }
    }
  }
  pickerOpen.value = false;
}

const request = computed<DietFreezerRequest | null>(() => {
  if (!recipeId.value || !(servings.value > 0) || !frozenOn.value) {
    return null;
  }
  const validMolds = molds.value.filter(m => Number(m.capacityMl) > 0 && Number(m.count) >= 1);
  if (!validMolds.length || validMolds.length !== molds.value.length) {
    return null;
  }
  const modifications = [];
  for (const c of changes.value) {
    if (!c.productId || !(Number(c.grams) > 0)) {
      return null;
    }
    if (c.kind === "swap" && (!c.replacedProductId || !(Number(c.replacedGrams) > 0))) {
      return null;
    }
    modifications.push({
      kind: c.kind,
      productId: c.productId,
      grams: Number(c.grams),
      replacedProductId: c.kind === "swap" ? c.replacedProductId : null,
      replacedGrams: c.kind === "swap" ? Number(c.replacedGrams) : null,
    });
  }
  const corrected = override.value;
  if (manual.value && num(corrected.kcal) === null) {
    return null;
  }
  return {
    recipeId: recipeId.value,
    frozenOn: frozenOn.value,
    servings: Number(servings.value),
    modifications,
    override: manual.value
      ? {
          kcal: num(corrected.kcal) ?? 0,
          protein: num(corrected.protein) ?? 0,
          fat: num(corrected.fat) ?? 0,
          carbs: num(corrected.carbs) ?? 0,
        }
      : null,
    molds: validMolds.map(m => ({ capacityMl: Number(m.capacityMl), count: Math.round(Number(m.count)) })),
    note: note.value,
  };
});

let previewTimer: ReturnType<typeof setTimeout> | null = null;
watch(request, (value) => {
  if (previewTimer) {
    clearTimeout(previewTimer);
  }
  if (!value) {
    return;
  }
  previewTimer = setTimeout(async () => {
    const { data } = await api.diet.previewFreezer(value);
    if (data) {
      preview.value = data;
    }
  }, 300);
}, { deep: true });

watch(manual, (value) => {
  if (value && preview.value) {
    override.value = { ...preview.value.total };
  }
});

watch(recipeId, async (id) => {
  ingredients.value = [];
  const recipe = recipes.value.find(r => r.id === id);
  if (!recipe) {
    return;
  }
  servings.value = recipe.servings;
  const { data } = await api.diet.recipeIngredients(recipe.id);
  if (recipeId.value === id) {
    ingredients.value = data ?? [];
  }
});

async function save() {
  if (!request.value) {
    return;
  }
  saving.value = true;
  const { error } = await api.diet.createFreezerBatch(request.value);
  saving.value = false;
  if (error) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  alert.success(i18n.t("diet.frozen"));
  emit("saved");
  open.value = false;
}

watch(open, async (value) => {
  if (!value) {
    return;
  }
  recipeId.value = null;
  frozenOn.value = today();
  changes.value = [];
  molds.value = [{ capacityMl: 500, count: 4 }];
  manual.value = false;
  note.value = "";
  preview.value = null;
  const { data } = await api.diet.recipeOptions();
  recipes.value = data ?? [];
});
</script>
