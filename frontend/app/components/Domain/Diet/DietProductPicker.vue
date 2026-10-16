<template>
  <div>
    <div class="d-flex ga-2 align-center">
      <v-text-field
        v-model="query"
        :label="$t('diet.search-product')"
        :prepend-inner-icon="$globals.icons.search"
        :hint="$t('diet.search-hint')"
        persistent-hint
        density="compact"
        clearable
        autofocus
        :loading="searching"
        @keydown.enter.prevent="searchNow"
      />
      <v-btn icon variant="tonal" color="primary" :title="$t('diet.scan-barcode')" @click="scanner = true">
        <v-icon>{{ mdiBarcodeScan }}</v-icon>
      </v-btn>
    </div>

    <v-list density="compact" class="py-1 picker-list">
      <v-list-item
        v-for="product in localResults"
        :key="product.id"
        :title="product.name"
        :subtitle="describe(product)"
        @click="emit('select', product)"
      >
        <template #append>
          <v-chip v-if="product.source === 'off'" size="x-small" variant="tonal">
            OFF
          </v-chip>
        </template>
      </v-list-item>

      <v-list-subheader v-if="offResults.length">
        {{ $t("diet.from-open-food-facts") }}
      </v-list-subheader>
      <v-list-item
        v-for="found in offResults"
        :key="found.code"
        :title="found.name"
        :subtitle="describe(found)"
        :disabled="saving === found.code"
        @click="pickOff(found.code)"
      >
        <template #append>
          <v-progress-circular v-if="saving === found.code" size="16" width="2" indeterminate />
        </template>
      </v-list-item>
    </v-list>

    <div class="d-flex flex-wrap ga-2 align-center">
      <span v-if="searching" class="text-caption text-medium-emphasis">{{ $t("diet.searching") }}</span>
      <v-btn variant="text" size="small" :prepend-icon="$globals.icons.createAlt" @click="openForm()">
        {{ $t("diet.new-product") }}
      </v-btn>
      <span v-if="offUnavailable" class="text-caption text-warning">{{ $t("diet.off-unavailable") }}</span>
      <span v-else-if="searched && !offResults.length && !searching" class="text-caption text-medium-emphasis">{{ $t("diet.off-nothing") }}</span>
    </div>

    <DietBarcodeScanner v-model="scanner" @detected="byBarcode" />
    <DietProductForm v-model="form" :initial-name="formName" :initial-barcode="formBarcode" @saved="created" />
  </div>
</template>

<script setup lang="ts">
import { mdiBarcodeScan } from "@mdi/js";
import DietBarcodeScanner from "./DietBarcodeScanner.vue";
import DietProductForm from "./DietProductForm.vue";
import { useUserApi } from "~/composables/api";
import { useDietProductSearch } from "~/composables/use-diet-product-search";
import { alert } from "~/composables/use-toast";
import type { DietOffProduct, DietProductOut } from "~/lib/api/types/diet";

const props = defineProps<{ initialQuery?: string }>();
const emit = defineEmits<{ select: [product: DietProductOut] }>();

const api = useUserApi();
const i18n = useI18n();

const query = ref("");
const products = ref<DietProductOut[]>([]);
const { results: offResults, unavailable: offUnavailable, searching, searched, searchNow } = useDietProductSearch(query);
const saving = ref<string | null>(null);
const scanner = ref(false);
const form = ref(false);
const formName = ref("");
const formBarcode = ref("");

function fold(text: string) {
  return text.toLowerCase().replaceAll("ł", "l").normalize("NFKD").replace(/[̀-ͯ]/g, "");
}

const localResults = computed(() => {
  const words = fold(query.value || "").split(/\s+/).filter(Boolean);
  return products.value
    .filter(p => words.every(w => fold(`${p.name} ${p.brand ?? ""} ${p.barcode ?? ""}`).includes(w)))
    .slice(0, 30);
});

function describe(product: DietProductOut | DietOffProduct) {
  const brand = product.brand ? `${product.brand} · ` : "";
  const unit = product.unit === "ml" ? "100 ml" : "100 g";
  return `${brand}${Math.round(product.kcal)} kcal / ${unit} · B ${product.protein} · T ${product.fat} · W ${product.carbs}`;
}

async function loadLocal() {
  const { data } = await api.diet.listProducts();
  products.value = data ?? [];
}

async function pickOff(code: string) {
  saving.value = code;
  const { data } = await api.diet.saveOffProduct(code);
  saving.value = null;
  if (!data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  products.value.push(data);
  emit("select", data);
}

async function byBarcode(code: string) {
  const { data, error } = await api.diet.productByBarcode(code);
  if (data) {
    if (!products.value.some(p => p.id === data.id)) {
      products.value.push(data);
    }
    emit("select", data);
    return;
  }
  if (error?.response?.status === 404) {
    alert.info(i18n.t("diet.barcode-not-found"));
    openForm("", code);
  }
  else {
    alert.error(i18n.t("diet.off-unavailable"));
  }
}

function openForm(name = query.value || "", barcode = "") {
  formName.value = name;
  formBarcode.value = barcode;
  form.value = true;
}

function created(product: DietProductOut) {
  products.value.push(product);
  emit("select", product);
}

onMounted(() => {
  loadLocal();
  if (props.initialQuery) {
    query.value = props.initialQuery; // searches right away, e.g. for a recipe ingredient
  }
});
</script>

<style scoped>
.picker-list {
  max-height: 320px;
  overflow-y: auto;
}
</style>
