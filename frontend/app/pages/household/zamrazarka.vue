<template>
  <v-container class="narrow-container">
    <BasePageTitle class="mb-3">
      <template #title>
        {{ $t("diet.freezer") }}
      </template>
      {{ $t("diet.freezer-description") }}
    </BasePageTitle>

    <div class="d-flex flex-wrap align-center ga-2 mb-4">
      <BaseButton create @click="dialog = true">
        {{ $t("diet.freeze-recipe") }}
      </BaseButton>
      <v-spacer />
      <v-switch v-model="showEmpty" :label="$t('diet.show-empty')" color="primary" density="compact" hide-details />
    </div>

    <p v-if="loaded && !batches.length" class="text-medium-emphasis">
      {{ $t("diet.freezer-empty") }}
    </p>

    <v-card v-for="batch in batches" :key="batch.id" variant="outlined" class="mb-3" :class="{ 'opacity-60': !batch.moldsLeft }">
      <v-card-title class="d-flex flex-wrap align-center ga-2 py-2">
        <router-link v-if="slugs[batch.recipeId ?? '']" :to="`/g/${groupSlug}/r/${slugs[batch.recipeId ?? '']}`" class="text-primary">
          {{ batch.recipeName }}
        </router-link>
        <span v-else>{{ batch.recipeName }}</span>
        <span class="text-caption text-medium-emphasis">{{ daysAgo(batch.frozenOn)
          ? $t("diet.frozen-ago", { date: formatDate(batch.frozenOn), days: daysAgo(batch.frozenOn) })
          : $t("diet.frozen-today") }}</span>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          size="x-small"
          color="error"
          :title="$t('general.delete')"
          @click="remove(batch.id)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="pt-0">
        <div v-for="(mold, index) in batch.molds" :key="index" class="d-flex flex-wrap align-center ga-2 mb-1">
          <v-chip size="small" label :color="mold.left ? 'primary' : undefined" variant="tonal">
            {{ $t("diet.molds-of", { left: fraction(mold.left), count: mold.count, capacity: mold.capacityMl }) }}
          </v-chip>
          <span class="text-caption text-medium-emphasis">
            {{ $t("diet.per-mold") }}: {{ Math.round(mold.kcal) }} kcal · B {{ mold.protein }} · T {{ mold.fat }} · W {{ mold.carbs }}
          </span>
          <v-spacer />
          <v-btn variant="text" size="x-small" :disabled="mold.left <= 0" @click="adjust(batch.id, index, -Math.min(1, mold.left))">
            {{ $t("diet.take-out") }}
          </v-btn>
          <v-btn variant="text" size="x-small" :disabled="mold.left >= mold.count" @click="adjust(batch.id, index, Math.min(1, mold.count - mold.left))">
            {{ $t("diet.put-back") }}
          </v-btn>
        </div>
        <div v-if="batch.modifications.length || batch.override || batch.note" class="text-caption text-medium-emphasis mt-2">
          <span v-for="(mod, i) in batch.modifications" :key="i">{{ describe(mod) }}<span v-if="i < batch.modifications.length - 1"> · </span></span>
          <span v-if="batch.override"> · {{ $t("diet.manual-total") }}</span>
          <span v-if="batch.note"> · {{ batch.note }}</span>
        </div>
      </v-card-text>
    </v-card>

    <DietFreezerDialog v-model="dialog" @saved="load" />
  </v-container>
</template>

<script setup lang="ts">
import DietFreezerDialog from "~/components/Domain/Diet/DietFreezerDialog.vue";
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { DietFreezerBatchOut, DietFreezerModificationOut } from "~/lib/api/types/diet";

definePageMeta({
  middleware: ["auth"],
});

const api = useUserApi();
const i18n = useI18n();
const auth = useMealieAuth();
const groupSlug = computed(() => auth.user.value?.groupSlug || "");
useSeoMeta({ title: i18n.t("diet.freezer") });

const batches = ref<DietFreezerBatchOut[]>([]);
const slugs = ref<Record<string, string>>({});
const showEmpty = ref(false);
const dialog = ref(false);
const loaded = ref(false);

function fraction(value: number) {
  const whole = Math.floor(value);
  return value - whole >= 0.5 ? `${whole || ""}½` : `${whole}`;
}
function formatDate(iso: string) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(i18n.locale.value);
}
function daysAgo(iso: string) {
  return Math.max(0, Math.round((Date.now() - new Date(`${iso}T12:00:00`).getTime()) / 86400000));
}
function describe(mod: DietFreezerModificationOut) {
  if (mod.kind === "swap") {
    return i18n.t("diet.swap-described", { from: mod.replacedName, fromGrams: mod.replacedGrams, to: mod.productName, toGrams: mod.grams });
  }
  return i18n.t(mod.kind === "add" ? "diet.add-described" : "diet.remove-described", { name: mod.productName, grams: mod.grams });
}

async function load() {
  const [{ data }, { data: recipes }] = await Promise.all([api.diet.listFreezer(showEmpty.value), api.diet.recipeOptions()]);
  batches.value = data ?? [];
  slugs.value = Object.fromEntries((recipes ?? []).map(r => [r.id, r.slug]));
  loaded.value = true;
}

async function adjust(id: string, index: number, delta: number) {
  const { error } = await api.diet.adjustFreezer(id, index, delta);
  if (error) {
    alert.error(i18n.t("events.something-went-wrong"));
  }
  await load();
}

async function remove(id: string) {
  if (!window.confirm(i18n.t("diet.delete-batch-confirm"))) {
    return;
  }
  await api.diet.deleteFreezerBatch(id);
  await load();
}

watch(showEmpty, load);
onMounted(load);
</script>
