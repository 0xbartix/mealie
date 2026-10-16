<template>
  <v-dialog v-model="open" max-width="620" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        {{ $t("diet.add-to", { meal: $t(`meal-plan.${mealType}`) }) }}
      </v-card-title>
      <v-tabs v-model="tab" color="primary" density="compact" grow>
        <v-tab value="product">
          {{ $t("diet.tab-product") }}
        </v-tab>
        <v-tab value="recipe">
          {{ $t("diet.tab-recipe") }}
        </v-tab>
        <v-tab value="freezer">
          {{ $t("diet.tab-freezer") }}
        </v-tab>
        <v-tab value="quick">
          {{ $t("diet.tab-quick") }}
        </v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text style="min-height: 360px">
        <v-window v-model="tab">
          <!-- product -->
          <v-window-item value="product">
            <DietProductPicker v-if="!product" @select="selectProduct" />
            <div v-else>
              <div class="d-flex align-center mb-3">
                <div class="flex-grow-1">
                  <div class="font-weight-medium">
                    {{ product.name }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ product.brand }} {{ Math.round(product.kcal) }} kcal / 100 {{ product.unit }}
                  </div>
                </div>
                <v-btn variant="text" size="small" @click="product = null">
                  {{ $t("diet.change") }}
                </v-btn>
              </div>
              <div class="d-flex ga-2 align-center">
                <v-text-field
                  v-model.number="productAmount"
                  type="number"
                  min="0"
                  step="any"
                  :label="$t('diet.amount')"
                  density="compact"
                  hide-details
                  style="max-width: 160px"
                  autofocus
                />
                <v-btn-toggle v-model="productUnit" mandatory density="compact" variant="outlined" divided>
                  <v-btn value="g">
                    {{ product.unit }}
                  </v-btn>
                  <v-btn v-if="product.portionGrams" value="portion">
                    {{ portionLabel(product) }}
                  </v-btn>
                </v-btn-toggle>
              </div>
              <DietMacroLine class="mt-3" :macros="productMacros" />
            </div>
          </v-window-item>

          <!-- recipe -->
          <v-window-item value="recipe">
            <v-autocomplete
              v-model="recipeId"
              :items="recipes"
              item-title="name"
              item-value="id"
              :label="$t('diet.recipe')"
              density="compact"
              auto-select-first
              :custom-filter="foldFilter"
            >
              <!-- in Vuetify 4 the slot's item is the recipe itself (no .raw) -->
              <template #item="{ props: itemProps, item }">
                <v-list-item v-bind="itemProps" :subtitle="`${Math.round(item.kcal)} kcal / ${$t('diet.portion')}`" />
              </template>
            </v-autocomplete>
            <v-text-field
              v-model.number="recipePortions"
              type="number"
              min="0.25"
              step="0.25"
              :label="$t('diet.portions-eaten')"
              density="compact"
              style="max-width: 200px"
            />
            <DietMacroLine v-if="recipe" :macros="recipeMacros" />
          </v-window-item>

          <!-- freezer -->
          <v-window-item value="freezer">
            <p v-if="!freezerOptions.length" class="text-medium-emphasis">
              {{ $t("diet.freezer-empty") }}
            </p>
            <v-list v-else density="compact" class="py-0">
              <v-list-item
                v-for="option in freezerOptions"
                :key="option.key"
                :active="freezerKey === option.key"
                color="primary"
                :title="option.name"
                :subtitle="option.subtitle"
                @click="freezerKey = option.key"
              />
            </v-list>
            <div v-if="freezerChoice" class="mt-3">
              <v-text-field
                v-model.number="freezerMolds"
                type="number"
                min="0.5"
                step="0.5"
                :max="freezerChoice.left"
                :label="$t('diet.molds-eaten')"
                density="compact"
                style="max-width: 200px"
                :hint="$t('diet.molds-left', { left: fraction(freezerChoice.left) })"
                persistent-hint
              />
              <DietMacroLine class="mt-2" :macros="freezerMacros" />
            </div>
          </v-window-item>

          <!-- quick -->
          <v-window-item value="quick">
            <v-text-field v-model="quick.name" :label="$t('diet.quick-name')" density="compact" />
            <v-row density="compact">
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="quick.kcal" type="number" min="0" label="kcal" density="compact" />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="quick.protein" type="number" min="0" :label="$t('diet.protein')" density="compact" />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="quick.fat" type="number" min="0" :label="$t('diet.fat')" density="compact" />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="quick.carbs" type="number" min="0" :label="$t('diet.carbs')" density="compact" />
              </v-col>
            </v-row>
          </v-window-item>
        </v-window>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <BaseButton cancel @click="open = false" />
        <BaseButton create :disabled="!canAdd" :loading="saving" @click="add">
          {{ $t("diet.add") }}
        </BaseButton>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import DietMacroLine from "./DietMacroLine.vue";
import DietProductPicker from "./DietProductPicker.vue";
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type {
  DietDiaryCreate,
  DietFreezerBatchOut,
  DietMacros,
  DietProductOut,
  DietRecipeOption,
  MealType,
} from "~/lib/api/types/diet";

const open = defineModel<boolean>({ default: false });
const props = defineProps<{ personId: string; date: string; mealType: MealType }>();
const emit = defineEmits<{ added: [] }>();

const api = useUserApi();
const i18n = useI18n();

const tab = ref("product");
const saving = ref(false);

const product = ref<DietProductOut | null>(null);
const productAmount = ref<number>(100);
const productUnit = ref<"g" | "portion">("g");

const recipes = ref<DietRecipeOption[]>([]);
const recipeId = ref<string | null>(null);
const recipePortions = ref(1);

const batches = ref<DietFreezerBatchOut[]>([]);
const freezerKey = ref<string | null>(null);
const freezerMolds = ref(1);

const quick = ref({ name: "", kcal: null as number | null, protein: null as number | null, fat: null as number | null, carbs: null as number | null });

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

function fraction(value: number) {
  const whole = Math.floor(value);
  return value - whole >= 0.5 ? `${whole || ""}½` : `${whole}`;
}

function scale(m: { kcal: number; protein: number; fat: number; carbs: number }, factor: number): DietMacros {
  return { kcal: m.kcal * factor, protein: m.protein * factor, fat: m.fat * factor, carbs: m.carbs * factor };
}

function portionLabel(p: DietProductOut) {
  const name = p.portionName || i18n.t("diet.portion");
  // names from Open Food Facts usually carry the weight already, e.g. "1 szklanka (250 ml)"
  return /\d\s*(?:g|ml)\b/i.test(name) ? name : `${name} (${p.portionGrams} ${p.unit})`;
}

function selectProduct(selected: DietProductOut) {
  product.value = selected;
  productUnit.value = "g";
  productAmount.value = 100;
}

watch(productUnit, (unit) => {
  productAmount.value = unit === "portion" ? 1 : 100;
});

const productMacros = computed(() => {
  if (!product.value) {
    return null;
  }
  const grams = productUnit.value === "portion" ? (productAmount.value || 0) * (product.value.portionGrams || 0) : productAmount.value || 0;
  return scale(product.value, grams / 100);
});

const recipe = computed(() => recipes.value.find(r => r.id === recipeId.value) ?? null);
const recipeMacros = computed(() => (recipe.value ? scale(recipe.value, recipePortions.value || 0) : null));

const freezerOptions = computed(() =>
  batches.value.flatMap(batch =>
    batch.molds
      .map((mold, index) => ({ batch, mold, index }))
      .filter(({ mold }) => mold.left > 0)
      .map(({ batch, mold, index }) => ({
        key: `${batch.id}:${index}`,
        batchId: batch.id,
        moldIndex: index,
        left: mold.left,
        mold,
        name: `${batch.recipeName} · ${mold.capacityMl} ml`,
        subtitle: i18n.t("diet.freezer-option", {
          left: fraction(mold.left),
          kcal: Math.round(mold.kcal),
          date: new Date(`${batch.frozenOn}T12:00:00`).toLocaleDateString(i18n.locale.value),
        }),
      })),
  ),
);
const freezerChoice = computed(() => freezerOptions.value.find(o => o.key === freezerKey.value) ?? null);
const freezerMacros = computed(() => (freezerChoice.value ? scale(freezerChoice.value.mold, freezerMolds.value || 0) : null));

const canAdd = computed(() => {
  if (tab.value === "product") {
    return !!product.value && (num(productAmount.value) ?? 0) > 0;
  }
  if (tab.value === "recipe") {
    return !!recipe.value && (num(recipePortions.value) ?? 0) > 0;
  }
  if (tab.value === "freezer") {
    const molds = freezerMolds.value;
    return !!freezerChoice.value && molds > 0 && molds * 2 === Math.round(molds * 2) && molds <= freezerChoice.value.left;
  }
  const kcal = num(quick.value.kcal);
  return !!quick.value.name.trim() && kcal !== null && kcal >= 0;
});

async function add() {
  const base = { personId: props.personId, date: props.date, mealType: props.mealType };
  let payload: DietDiaryCreate;
  if (tab.value === "product" && product.value) {
    payload = { ...base, kind: "product", productId: product.value.id, amount: productAmount.value, amountUnit: productUnit.value };
  }
  else if (tab.value === "recipe" && recipe.value) {
    payload = { ...base, kind: "recipe", recipeId: recipe.value.id, amount: recipePortions.value, amountUnit: "portion" };
  }
  else if (tab.value === "freezer" && freezerChoice.value) {
    payload = {
      ...base,
      kind: "freezer",
      batchId: freezerChoice.value.batchId,
      moldIndex: freezerChoice.value.moldIndex,
      amount: freezerMolds.value,
      amountUnit: "mold",
    };
  }
  else {
    payload = {
      ...base,
      kind: "quick",
      name: quick.value.name.trim(),
      kcal: num(quick.value.kcal) ?? 0,
      protein: num(quick.value.protein),
      fat: num(quick.value.fat),
      carbs: num(quick.value.carbs),
    };
  }
  saving.value = true;
  const { error } = await api.diet.addDiaryEntry(payload);
  saving.value = false;
  if (error) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  emit("added");
  open.value = false;
}

watch(open, async (value) => {
  if (!value) {
    return;
  }
  tab.value = "product";
  product.value = null;
  recipeId.value = null;
  recipePortions.value = 1;
  freezerKey.value = null;
  freezerMolds.value = 1;
  quick.value = { name: "", kcal: null, protein: null, fat: null, carbs: null };
  const [recipeResponse, freezerResponse] = await Promise.all([api.diet.recipeOptions(), api.diet.listFreezer()]);
  recipes.value = recipeResponse.data ?? [];
  batches.value = freezerResponse.data ?? [];
});
</script>
