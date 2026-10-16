<template>
  <v-dialog v-model="open" max-width="560">
    <v-card>
      <v-card-title>{{ editing ? $t("diet.edit-product") : $t("diet.new-product") }}</v-card-title>
      <v-card-text>
        <v-row density="compact">
          <v-col cols="12" sm="8">
            <v-text-field v-model="form.name" :label="$t('diet.product-name')" density="compact" />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field v-model="form.brand" :label="$t('diet.brand')" density="compact" />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.barcode" :label="$t('diet.barcode')" inputmode="numeric" density="compact" />
          </v-col>
          <v-col cols="12" sm="6">
            <v-btn-toggle v-model="form.unit" mandatory density="compact" variant="outlined" divided>
              <v-btn value="g">
                {{ $t("diet.per-100g") }}
              </v-btn>
              <v-btn value="ml">
                {{ $t("diet.per-100ml") }}
              </v-btn>
            </v-btn-toggle>
          </v-col>
          <v-col cols="6" sm="3">
            <v-text-field v-model.number="form.kcal" type="number" min="0" label="kcal" density="compact" />
          </v-col>
          <v-col cols="6" sm="3">
            <v-text-field v-model.number="form.protein" type="number" min="0" :label="$t('diet.protein')" density="compact" />
          </v-col>
          <v-col cols="6" sm="3">
            <v-text-field v-model.number="form.fat" type="number" min="0" :label="$t('diet.fat')" density="compact" />
          </v-col>
          <v-col cols="6" sm="3">
            <v-text-field v-model.number="form.carbs" type="number" min="0" :label="$t('diet.carbs')" density="compact" />
          </v-col>
          <v-col cols="7">
            <v-text-field v-model="form.portionName" :label="$t('diet.portion-name')" :placeholder="$t('diet.portion-placeholder')" density="compact" />
          </v-col>
          <v-col cols="5">
            <v-text-field
              v-model.number="form.portionGrams"
              type="number"
              min="0"
              :label="$t('diet.portion-grams')"
              :suffix="form.unit"
              density="compact"
            />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <BaseButton cancel @click="open = false" />
        <BaseButton save :disabled="!valid" :loading="saving" @click="save" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { DietProductCreate, DietProductOut } from "~/lib/api/types/diet";

const open = defineModel<boolean>({ default: false });
const props = defineProps<{ product?: DietProductOut | null; initialName?: string; initialBarcode?: string }>();
const emit = defineEmits<{ saved: [product: DietProductOut] }>();

const api = useUserApi();
const i18n = useI18n();
const saving = ref(false);
const editing = computed(() => !!props.product);

function blank(): DietProductCreate {
  return { name: "", brand: "", barcode: "", unit: "g", kcal: 0, protein: 0, fat: 0, carbs: 0, portionName: "", portionGrams: null };
}

const form = ref<DietProductCreate>(blank());

watch(open, (value) => {
  if (!value) {
    return;
  }
  form.value = props.product
    ? { ...props.product }
    : { ...blank(), name: props.initialName ?? "", barcode: props.initialBarcode ?? "" };
});

// a cleared number field gives "" – treat it as empty, not as 0
function num(value: unknown): number | null {
  return value === "" || value === null || value === undefined || Number.isNaN(Number(value)) ? null : Number(value);
}

const valid = computed(() => {
  const kcal = num(form.value.kcal);
  return !!form.value.name?.trim() && kcal !== null && kcal >= 0 && kcal <= 1000;
});

async function save() {
  saving.value = true;
  const payload: DietProductCreate = {
    ...form.value,
    kcal: num(form.value.kcal) ?? 0,
    protein: num(form.value.protein) ?? 0,
    fat: num(form.value.fat) ?? 0,
    carbs: num(form.value.carbs) ?? 0,
    portionGrams: num(form.value.portionGrams) || null,
  };
  const { data, error } = props.product
    ? await api.diet.updateProduct(props.product.id, payload)
    : await api.diet.createProduct(payload);
  saving.value = false;
  if (error || !data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  emit("saved", data);
  open.value = false;
}
</script>
