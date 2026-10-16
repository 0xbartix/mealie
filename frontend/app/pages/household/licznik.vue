<template>
  <v-container class="narrow-container">
    <BasePageTitle class="mb-3">
      <template #title>
        {{ $t("diet.counter") }}
      </template>
      {{ $t("diet.counter-description") }}
    </BasePageTitle>

    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab value="day">
        {{ $t("diet.diary") }}
      </v-tab>
      <v-tab value="products">
        {{ $t("diet.my-products") }}
      </v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <v-window-item value="day">
        <v-alert v-if="settings && !persons.length" type="info" variant="tonal" class="mb-4">
          {{ $t("diet.no-persons") }}
          <router-link to="/household/diet" class="text-primary">
            {{ $t("diet.diet-plan") }}
          </router-link>
        </v-alert>

        <template v-if="persons.length">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-chip-group v-model="personId" mandatory selected-class="text-primary">
              <v-chip v-for="person in persons" :key="person.id" :value="person.id" filter variant="outlined">
                {{ person.name }}
              </v-chip>
            </v-chip-group>
            <v-spacer />
            <v-btn icon variant="text" size="small" @click="shift(-1)">
              <v-icon>{{ $globals.icons.chevronLeft }}</v-icon>
            </v-btn>
            <v-btn variant="text" size="small" @click="date = today()">
              {{ dayLabel }}
            </v-btn>
            <v-btn icon variant="text" size="small" @click="shift(1)">
              <v-icon>{{ $globals.icons.chevronRight }}</v-icon>
            </v-btn>
          </div>

          <v-card variant="outlined" class="mb-4">
            <v-card-text>
              <div class="d-flex align-baseline mb-1">
                <span class="text-h5 font-weight-medium">{{ Math.round(day?.totals.kcal ?? 0) }}</span>
                <span class="text-medium-emphasis ml-1">/ {{ Math.round(day?.target?.kcal ?? 0) }} kcal</span>
                <v-spacer />
                <span class="text-caption" :class="kcalLeft < 0 ? 'text-error' : 'text-medium-emphasis'">
                  {{ kcalLeft >= 0 ? $t("diet.kcal-left", { kcal: kcalLeft }) : $t("diet.kcal-over", { kcal: -kcalLeft }) }}
                </span>
              </div>
              <v-progress-linear :model-value="percent('kcal')" :color="barColor('kcal')" height="10" rounded class="mb-3" />
              <v-row density="compact">
                <v-col v-for="macro in macroBars" :key="macro.key" cols="4">
                  <div class="text-caption">
                    {{ macro.label }} {{ Math.round(macro.value) }} / {{ Math.round(macro.target) }} g
                  </div>
                  <v-progress-linear :model-value="percent(macro.key)" :color="barColor(macro.key)" height="6" rounded />
                </v-col>
              </v-row>
            </v-card-text>
            <v-card-actions>
              <BaseButton secondary :icon="$globals.icons.calendarMultiselect" :loading="fromPlanLoading" @click="fromPlan">
                {{ $t("diet.add-from-plan") }}
              </BaseButton>
            </v-card-actions>
          </v-card>

          <v-card v-for="meal in meals" :key="meal" variant="outlined" class="mb-3">
            <div class="d-flex align-center py-2 px-4">
              <span class="text-subtitle-1 font-weight-medium">{{ $t(`meal-plan.${meal}`) }}</span>
              <span class="text-caption text-medium-emphasis ml-2">{{ Math.round(mealKcal(meal)) }} kcal</span>
              <v-spacer />
              <v-btn variant="text" size="small" color="primary" :prepend-icon="$globals.icons.createAlt" @click="openAdd(meal)">
                {{ $t("diet.add") }}
              </v-btn>
            </div>
            <v-list v-if="entriesFor(meal).length" density="compact" class="py-0">
              <v-list-item v-for="entry in entriesFor(meal)" :key="entry.id">
                <v-list-item-title>{{ entry.name }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ amountText(entry) }} · B {{ entry.protein }} · T {{ entry.fat }} · W {{ entry.carbs }}
                </v-list-item-subtitle>
                <template #append>
                  <span class="text-body-2 mr-2">{{ Math.round(entry.kcal) }} kcal</span>
                  <v-btn icon variant="text" size="x-small" color="error" @click="remove(entry.id)">
                    <v-icon>{{ $globals.icons.delete }}</v-icon>
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>
          </v-card>
        </template>
      </v-window-item>

      <v-window-item value="products">
        <div class="d-flex ga-2 mb-2">
          <v-text-field
            v-model="productSearch"
            :prepend-inner-icon="$globals.icons.search"
            :label="$t('diet.search-product')"
            density="compact"
            hide-details
            clearable
          />
          <BaseButton create @click="editProduct(null)">
            {{ $t("diet.new-product") }}
          </BaseButton>
        </div>
        <p class="text-caption text-medium-emphasis mb-2">
          {{ $t("diet.my-products-hint") }}
        </p>
        <v-list density="compact">
          <v-list-item v-for="product in filteredProducts" :key="product.id" :title="product.name" :subtitle="productLine(product)">
            <template #append>
              <v-btn icon variant="text" size="x-small" @click="editProduct(product)">
                <v-icon>{{ $globals.icons.edit }}</v-icon>
              </v-btn>
              <v-btn icon variant="text" size="x-small" color="error" @click="deleteProduct(product.id)">
                <v-icon>{{ $globals.icons.delete }}</v-icon>
              </v-btn>
            </template>
          </v-list-item>
        </v-list>
      </v-window-item>
    </v-window>

    <DietDiaryAddDialog
      v-if="personId"
      v-model="addOpen"
      :person-id="personId"
      :date="date"
      :meal-type="addMeal"
      @added="load"
    />
    <DietProductForm v-model="productFormOpen" :product="productToEdit" @saved="loadProducts" />
  </v-container>
</template>

<script setup lang="ts">
import DietDiaryAddDialog from "~/components/Domain/Diet/DietDiaryAddDialog.vue";
import DietProductForm from "~/components/Domain/Diet/DietProductForm.vue";
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { DietDiaryDay, DietDiaryEntryOut, DietProductOut, DietSettingsOut, MealType } from "~/lib/api/types/diet";

definePageMeta({
  middleware: ["auth"],
});

const api = useUserApi();
const i18n = useI18n();
useSeoMeta({ title: i18n.t("diet.counter") });

function today() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const tab = ref("day");
const settings = ref<DietSettingsOut | null>(null);
const personId = ref<string | null>(null);
const date = ref(today());
const day = ref<DietDiaryDay | null>(null);
const addOpen = ref(false);
const addMeal = ref<MealType>("breakfast");
const fromPlanLoading = ref(false);

const meals: MealType[] = ["breakfast", "lunch", "snack", "dinner"];
const persons = computed(() => (settings.value?.persons ?? []).filter(p => p.active !== false));

const dayLabel = computed(() => {
  if (date.value === today()) {
    return i18n.t("diet.today");
  }
  return new Date(`${date.value}T12:00:00`).toLocaleDateString(i18n.locale.value, { weekday: "short", day: "numeric", month: "numeric" });
});

function shift(days: number) {
  const d = new Date(`${date.value}T12:00:00`);
  d.setDate(d.getDate() + days);
  date.value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const kcalLeft = computed(() => Math.round((day.value?.target?.kcal ?? 0) - (day.value?.totals.kcal ?? 0)));

type MacroKey = "kcal" | "protein" | "fat" | "carbs";
const macroBars = computed(() => [
  { key: "protein" as const, label: "B", value: day.value?.totals.protein ?? 0, target: day.value?.target?.protein ?? 0 },
  { key: "fat" as const, label: "T", value: day.value?.totals.fat ?? 0, target: day.value?.target?.fat ?? 0 },
  { key: "carbs" as const, label: "W", value: day.value?.totals.carbs ?? 0, target: day.value?.target?.carbs ?? 0 },
]);

function ratio(key: MacroKey) {
  const target = day.value?.target?.[key] ?? 0;
  return target ? (day.value?.totals[key] ?? 0) / target : 0;
}
function percent(key: MacroKey) {
  return Math.min(100, ratio(key) * 100);
}
function barColor(key: MacroKey) {
  const r = ratio(key);
  return r > 1.1 ? "error" : r >= 0.9 ? "success" : "primary";
}

function entriesFor(meal: MealType) {
  return (day.value?.entries ?? []).filter(e => e.mealType === meal);
}
function mealKcal(meal: MealType) {
  return entriesFor(meal).reduce((sum, e) => sum + e.kcal, 0);
}

function fraction(value: number) {
  const whole = Math.floor(value);
  const rest = Math.round((value - whole) * 100) / 100;
  const symbol = ({ 0.25: "¼", 0.5: "½", 0.75: "¾" } as Record<number, string>)[rest];
  return symbol ? `${whole || ""}${symbol}` : `${Math.round(value * 100) / 100}`;
}

function amountText(entry: DietDiaryEntryOut) {
  if (entry.kind === "quick") {
    return i18n.t("diet.tab-quick");
  }
  if (entry.amountUnit === "g" || entry.amountUnit === "ml") {
    return `${entry.amount} ${entry.amountUnit}`;
  }
  if (entry.kind === "product") {
    return `${fraction(entry.amount)} ×`;
  }
  return counted(entry.amountUnit === "mold" ? "molds" : "portions", entry.amount);
}

// Polish needs one / few / many / fraction forms ("1 porcja", "2 porcje", "5 porcji", "1½ porcji")
function counted(base: string, value: number) {
  const category = new Intl.PluralRules(i18n.locale.value).select(value);
  const key = i18n.te(`diet.${base}-${category}`) ? `diet.${base}-${category}` : `diet.${base}-other`;
  return i18n.t(key, { count: fraction(value) });
}

async function loadSettings() {
  const { data } = await api.diet.getSettings();
  settings.value = data;
  if (!personId.value && persons.value.length) {
    personId.value = persons.value[0]!.id ?? null;
  }
}

async function load() {
  if (!personId.value) {
    return;
  }
  const { data } = await api.diet.diaryDay(personId.value, date.value);
  day.value = data;
}

function openAdd(meal: MealType) {
  addMeal.value = meal;
  addOpen.value = true;
}

async function remove(id: string) {
  await api.diet.deleteDiaryEntry(id);
  await load();
}

async function fromPlan() {
  if (!personId.value) {
    return;
  }
  fromPlanLoading.value = true;
  const { data } = await api.diet.diaryFromPlan(personId.value, date.value);
  fromPlanLoading.value = false;
  if (!data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  if (data.created) {
    alert.success(i18n.t("diet.added-from-plan", { count: data.created }));
  }
  else {
    alert.info(i18n.t("diet.nothing-from-plan"));
  }
  await load();
}

// products tab
const products = ref<DietProductOut[]>([]);
const productSearch = ref("");
const productFormOpen = ref(false);
const productToEdit = ref<DietProductOut | null>(null);

function fold(text: string) {
  return text.toLowerCase().replaceAll("ł", "l").normalize("NFKD").replace(/[̀-ͯ]/g, "");
}
const filteredProducts = computed(() => {
  const words = fold(productSearch.value || "").split(/\s+/).filter(Boolean);
  return products.value.filter(p => words.every(w => fold(`${p.name} ${p.brand ?? ""}`).includes(w)));
});
function productLine(p: DietProductOut) {
  return `${p.brand ? `${p.brand} · ` : ""}${Math.round(p.kcal)} kcal / 100 ${p.unit} · B ${p.protein} · T ${p.fat} · W ${p.carbs}`;
}
async function loadProducts() {
  const { data } = await api.diet.listProducts();
  products.value = data ?? [];
}
function editProduct(product: DietProductOut | null) {
  productToEdit.value = product;
  productFormOpen.value = true;
}
async function deleteProduct(id: string) {
  await api.diet.deleteProduct(id);
  await loadProducts();
}

watch([personId, date], load);
watch(tab, (value) => {
  if (value === "products") {
    loadProducts();
  }
});

onMounted(async () => {
  await loadSettings();
  await load();
});
</script>
