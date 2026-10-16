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
        <div v-for="(change, index) in changes" :key="index" class="d-flex flex-wrap align-center ga-2 mb-2">
          <v-select v-model="change.kind" :items="kinds" density="compact" hide-details style="max-width: 170px" />
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
          <DietProductPicker v-if="pickerOpen" @select="picked" />
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
}

function today() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const recipes = ref<DietRecipeOption[]>([]);
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
const pickTarget = ref<{ index: number; field: "product" | "replaced" } | null>(null);
function pick(index: number, field: "product" | "replaced") {
  pickTarget.value = { index, field };
  pickerOpen.value = true;
}
function picked(product: DietProductOut) {
  const target = pickTarget.value;
  const row = target ? changes.value[target.index] : undefined;
  if (target && row) {
    if (target.field === "product") {
      row.productId = product.id;
      row.productName = product.name;
    }
    else {
      row.replacedProductId = product.id;
      row.replacedName = product.name;
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
  return {
    recipeId: recipeId.value,
    frozenOn: frozenOn.value,
    servings: Number(servings.value),
    modifications,
    override: manual.value ? { ...override.value } : null,
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

watch(recipeId, (id) => {
  const recipe = recipes.value.find(r => r.id === id);
  if (recipe) {
    servings.value = recipe.servings;
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
