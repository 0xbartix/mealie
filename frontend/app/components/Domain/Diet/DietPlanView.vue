<template>
  <div>
    <v-alert v-if="!activePersons.length" type="info" variant="tonal" class="mb-4">
      {{ $t("diet.no-persons") }}
    </v-alert>

    <v-row density="compact" align="center" class="mb-2">
      <v-col cols="6" sm="3">
        <v-text-field v-model="startDate" type="date" :label="$t('diet.start-date')" density="compact" hide-details />
      </v-col>
      <v-col cols="6" sm="3">
        <v-text-field v-model="endDate" type="date" :label="$t('diet.end-date')" density="compact" hide-details />
      </v-col>
      <v-col cols="12" sm="6" class="d-flex flex-wrap ga-2">
        <v-btn variant="outlined" size="small" @click="setLength(7)">
          {{ $t("diet.one-week") }}
        </v-btn>
        <v-btn variant="outlined" size="small" @click="setLength(14)">
          {{ $t("diet.two-weeks") }}
        </v-btn>
      </v-col>
    </v-row>

    <div class="d-flex flex-wrap ga-2 mb-4">
      <BaseButton :loading="loading" :disabled="!activePersons.length" :icon="$globals.icons.calendarWeekBegin" @click="generate(true)">
        {{ preview ? $t("diet.regenerate") : $t("diet.generate") }}
      </BaseButton>
      <BaseButton v-if="preview" save :loading="saving" @click="save">
        {{ $t("diet.save-to-calendar") }}
      </BaseButton>
      <BaseButton v-if="savedCount !== null" secondary to="/household/mealplan/planner/view" :icon="$globals.icons.calendarMultiselect">
        {{ $t("diet.open-planner") }}
      </BaseButton>
      <BaseButton
        v-for="list in shoppingLists"
        :key="list.id"
        secondary
        :to="`/shopping-lists/${list.id}`"
        :icon="$globals.icons.formatListCheck"
      >
        {{ list.name }}
      </BaseButton>
    </div>

    <v-alert
      v-for="warning in warnings"
      :key="warning"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-2"
    >
      {{ warning }}
    </v-alert>

    <template v-if="preview">
      <v-card v-for="batch in preview.batches" :key="batch.index" variant="outlined" class="mb-4">
        <v-card-title class="d-flex flex-wrap align-center ga-2">
          <v-icon size="small">
            {{ $globals.icons.potSteam }}
          </v-icon>
          <span>{{ $t("diet.cooking-on", { date: formatDate(batch.cookDate, true) }) }}</span>
          <span class="text-body-2 text-medium-emphasis">
            {{ batch.days === 1
              ? $t("diet.eating-one-day", { start: formatDate(batch.startDate) })
              : $t("diet.eating-days", { days: batch.days, start: formatDate(batch.startDate), end: formatDate(batch.endDate) }) }}
          </span>
        </v-card-title>
        <v-divider />
        <v-list density="compact" class="py-0">
          <v-list-item v-for="slot in batch.slots" :key="slot.slotIndex" class="py-2">
            <div class="d-flex flex-wrap align-center ga-2">
              <v-chip size="small" label variant="tonal" color="primary" class="meal-chip">
                {{ $t(`meal-plan.${slot.mealType}`) }}
              </v-chip>
              <div class="flex-grow-1" style="min-width: 200px">
                <template v-if="slot.recipe">
                  <router-link :to="`/g/${groupSlug}/r/${slot.recipe.slug}`" class="text-primary font-weight-medium">
                    {{ slot.recipe.name }}
                  </router-link>
                  <div class="text-caption text-medium-emphasis">
                    {{ portionsText(slot) }}
                  </div>
                </template>
                <span v-else class="text-medium-emphasis">{{ $t("diet.no-recipe") }}</span>
              </div>
              <div v-if="slot.recipe" class="text-body-2 text-right">
                <div class="text-caption text-medium-emphasis">
                  {{ $t("diet.to-cook") }}
                </div>
                <strong>{{ fraction(slot.portionsPerBatch ?? 0) }} {{ $t("diet.portions") }}</strong>
              </div>
              <v-btn
                v-if="slot.recipe && (slot.candidatesCount ?? 0) > 1"
                variant="text"
                size="small"
                :loading="swapping === `${batch.index}-${slot.slotIndex}`"
                :prepend-icon="$globals.icons.swapHorizontal"
                @click="swap(batch.index, slot.slotIndex)"
              >
                {{ $t("diet.swap") }}
              </v-btn>
            </div>
          </v-list-item>
        </v-list>
        <v-divider />
        <v-card-text class="py-2">
          <div class="text-caption text-medium-emphasis mb-1">
            {{ $t("diet.day-totals") }}
          </div>
          <div v-for="totals in batch.totals" :key="totals.personId" class="d-flex flex-wrap align-center ga-1 mb-1">
            <span class="font-weight-medium mr-1" style="min-width: 80px">{{ personName(totals.personId) }}</span>
            <v-chip
              v-for="metric in metrics(totals)"
              :key="metric.key"
              size="small"
              variant="tonal"
              :color="metric.color"
            >
              {{ metric.label }} {{ metric.value }} / {{ metric.target }}
            </v-chip>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type {
  DietPlanPreview,
  DietPlanRequest,
  DietPlanSlot,
  DietPlanTotals,
  DietSettingsOut,
  DietShoppingListRef,
} from "~/lib/api/types/diet";

const props = defineProps<{ settings: DietSettingsOut }>();

const api = useUserApi();
const i18n = useI18n();
const auth = useMealieAuth();
const groupSlug = computed(() => auth.user.value?.groupSlug || "");

function isoDate(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function addDays(iso: string, days: number) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return isoDate(date);
}

// when food is eaten from the day after cooking, a plan starting tomorrow makes today the first cooking day
const startDate = ref(addDays(isoDate(new Date()), props.settings.eatNextDay ? 1 : 0));
const endDate = ref(addDays(startDate.value, 13));
function setLength(days: number) {
  endDate.value = addDays(startDate.value, days - 1);
}

const preview = ref<DietPlanPreview | null>(null);
const excluded = ref<Record<number, Record<number, string[]>>>({});
const loading = ref(false);
const saving = ref(false);
const swapping = ref<string | null>(null);
const savedCount = ref<number | null>(null);
const shoppingLists = ref<DietShoppingListRef[]>([]);

const activePersons = computed(() => (props.settings.persons ?? []).filter(p => p.active !== false));

function personName(id: string) {
  return props.settings.persons?.find(p => p.id === id)?.name ?? "?";
}

function fraction(value: number) {
  const whole = Math.floor(value);
  const rest = Math.round((value - whole) * 100) / 100;
  const symbol = ({ 0.25: "¼", 0.5: "½", 0.75: "¾" } as Record<number, string>)[rest] ?? "";
  return `${whole || !symbol ? whole : ""}${symbol}`;
}

function formatDate(iso: string, withWeekday = false) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(i18n.locale.value, {
    weekday: withWeekday ? "long" : undefined,
    day: "numeric",
    month: "numeric",
  });
}

function portionsText(slot: DietPlanSlot) {
  return (slot.portions ?? [])
    .map(p => `${personName(p.personId)}: ${fraction(p.portions)} (${Math.round(p.kcal)} kcal)`)
    .join(" · ");
}

function metrics(totals: DietPlanTotals) {
  const person = props.settings.persons?.find(p => p.id === totals.personId);
  const rows = [
    { key: "kcal", label: "kcal", value: totals.kcal, target: person?.kcal ?? 0 },
    { key: "protein", label: "B", value: totals.protein, target: person?.protein ?? 0 },
    { key: "fat", label: "T", value: totals.fat, target: person?.fat ?? 0 },
    { key: "carbs", label: "W", value: totals.carbs, target: person?.carbs ?? 0 },
  ];
  return rows.map((row) => {
    const deviation = row.target ? Math.abs(row.value - row.target) / row.target : 0;
    const color = deviation <= 0.05 ? "success" : deviation <= 0.15 ? "warning" : "error";
    return { ...row, value: Math.round(row.value), target: Math.round(row.target), color };
  });
}

const warnings = computed(() =>
  (preview.value?.warnings ?? []).map((code) => {
    const [kind, meal, count] = code.split(":");
    const mealName = i18n.t(`meal-plan.${meal}`);
    return kind === "no-candidates"
      ? i18n.t("diet.warning-no-candidates", { meal: mealName })
      : i18n.t("diet.warning-few-candidates", { meal: mealName, count });
  }),
);

function currentLocks(skip?: { batch: number; slot: number }) {
  const locked: Record<number, Record<number, string>> = {};
  for (const batch of preview.value?.batches ?? []) {
    locked[batch.index] = {};
    for (const slot of batch.slots) {
      if (slot.recipe && !(skip && skip.batch === batch.index && skip.slot === slot.slotIndex)) {
        locked[batch.index]![slot.slotIndex] = slot.recipe.id;
      }
    }
  }
  return locked;
}

async function request(payload: DietPlanRequest) {
  const { data, error } = await api.diet.preview(payload);
  if (error || !data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  preview.value = data;
}

async function generate(fresh: boolean) {
  loading.value = true;
  savedCount.value = null;
  if (fresh) {
    excluded.value = {};
  }
  await request({ startDate: startDate.value, endDate: endDate.value });
  loading.value = false;
}

async function swap(batchIndex: number, slotIndex: number) {
  const current = preview.value?.batches[batchIndex]?.slots[slotIndex]?.recipe;
  if (!preview.value || !current) {
    return;
  }
  swapping.value = `${batchIndex}-${slotIndex}`;
  const batchExcluded = (excluded.value[batchIndex] ??= {});
  const slotExcluded = (batchExcluded[slotIndex] ??= []);
  slotExcluded.push(current.id);
  if (slotExcluded.length >= (preview.value.batches[batchIndex]?.slots[slotIndex]?.candidatesCount ?? 0)) {
    // every candidate was shown once – start the cycle again, skipping only the current one
    batchExcluded[slotIndex] = [current.id];
  }
  savedCount.value = null;
  await request({
    startDate: startDate.value,
    endDate: endDate.value,
    seed: preview.value.seed,
    locked: currentLocks({ batch: batchIndex, slot: slotIndex }),
    excluded: excluded.value,
  });
  swapping.value = null;
}

async function save() {
  if (!preview.value) {
    return;
  }
  saving.value = true;
  const { data, error } = await api.diet.save({
    startDate: startDate.value,
    endDate: endDate.value,
    seed: preview.value.seed,
    locked: currentLocks(),
  });
  saving.value = false;
  if (error || !data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  savedCount.value = data.created;
  shoppingLists.value = data.shoppingLists ?? [];
  alert.success(
    shoppingLists.value.length
      ? i18n.t("diet.saved-with-lists", { created: data.created, lists: shoppingLists.value.length })
      : i18n.t("diet.saved-to-calendar", { created: data.created }),
  );
}

// batch and slot indexes of an old preview mean something else after the settings change
watch([startDate, endDate, () => props.settings], () => {
  excluded.value = {};
  shoppingLists.value = [];
  preview.value = null;
  savedCount.value = null;
});
</script>

<style scoped>
.meal-chip {
  min-width: 96px;
  justify-content: center;
}
</style>
