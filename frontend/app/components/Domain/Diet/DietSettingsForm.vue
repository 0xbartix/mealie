<template>
  <div>
    <BaseCardSectionTitle :title="$t('diet.persons')">
      {{ $t("diet.persons-description") }}
    </BaseCardSectionTitle>
    <v-card
      v-for="(person, index) in modelValue.persons"
      :key="person.id || index"
      variant="outlined"
      class="mb-3"
    >
      <v-card-text>
        <v-row dense>
          <v-col cols="12" sm="4">
            <v-text-field v-model="person.name" :label="$t('diet.name')" density="compact" hide-details />
          </v-col>
          <v-col cols="6" sm="2">
            <v-text-field
              v-model.number="person.kcal"
              type="number"
              min="0"
              :label="$t('diet.kcal')"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="6" sm="2">
            <v-text-field
              v-model.number="person.protein"
              type="number"
              min="0"
              :label="$t('diet.protein')"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="6" sm="2">
            <v-text-field
              v-model.number="person.fat"
              type="number"
              min="0"
              :label="$t('diet.fat')"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="6" sm="2">
            <v-text-field
              v-model.number="person.carbs"
              type="number"
              min="0"
              :label="$t('diet.carbs')"
              density="compact"
              hide-details
            />
          </v-col>
        </v-row>
        <div class="d-flex align-center flex-wrap mt-2 ga-2">
          <span class="text-caption text-medium-emphasis">{{ macroSummary(person) }}</span>
          <v-spacer />
          <v-switch v-model="person.active" :label="$t('diet.active')" color="primary" density="compact" hide-details />
          <v-btn icon variant="text" size="small" color="error" @click="removePerson(index)">
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
    <BaseButton create class="mb-6" @click="addPerson">
      {{ $t("diet.add-person") }}
    </BaseButton>

    <BaseCardSectionTitle :title="$t('diet.cooking-days')">
      {{ $t("diet.cooking-days-description") }}
    </BaseCardSectionTitle>
    <v-chip-group v-model="modelValue.cookingDays" multiple column selected-class="text-primary" class="mb-6">
      <v-chip v-for="day in weekDays" :key="day.value" :value="day.value" filter variant="outlined">
        {{ day.label }}
      </v-chip>
    </v-chip-group>

    <BaseCardSectionTitle :title="$t('diet.meals-per-day')">
      {{ $t("diet.meals-per-day-description") }}
    </BaseCardSectionTitle>
    <v-btn-toggle
      :model-value="mealSlots.length"
      mandatory
      density="compact"
      variant="outlined"
      divided
      class="mb-4"
      @update:model-value="setMealCount"
    >
      <v-btn v-for="n in 6" :key="n" :value="n">
        {{ n }}
      </v-btn>
    </v-btn-toggle>
    <v-row v-for="(slot, index) in mealSlots" :key="index" dense>
      <v-col cols="7" sm="5">
        <v-select v-model="slot.mealType" :items="mealTypes" :label="$t('diet.meal')" density="compact" hide-details />
      </v-col>
      <v-col cols="5" sm="3">
        <v-text-field
          v-model.number="slot.share"
          type="number"
          min="1"
          max="100"
          suffix="%"
          :label="$t('diet.share')"
          density="compact"
          hide-details
        />
      </v-col>
    </v-row>
    <p class="text-caption mt-2" :class="sharesOk ? 'text-medium-emphasis' : 'text-error'">
      {{ $t("diet.shares-total", { total: sharesTotal }) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { DietMealSlot, DietPerson, DietSettingsUpdate, MealType } from "~/lib/api/types/diet";

const modelValue = defineModel<DietSettingsUpdate>({ required: true });

const i18n = useI18n();

const DEFAULT_SLOTS: Record<number, [MealType, number][]> = {
  1: [["lunch", 100]],
  2: [["breakfast", 40], ["lunch", 60]],
  3: [["breakfast", 30], ["lunch", 40], ["dinner", 30]],
  4: [["breakfast", 25], ["lunch", 35], ["snack", 10], ["dinner", 30]],
  5: [["breakfast", 25], ["snack", 10], ["lunch", 35], ["snack", 10], ["dinner", 20]],
  6: [["breakfast", 20], ["snack", 10], ["lunch", 30], ["snack", 10], ["dinner", 20], ["snack", 10]],
};

const weekDays = computed(() =>
  // backend numbering: 0 = Monday ... 6 = Sunday; 2026-10-19 is a Monday
  [0, 1, 2, 3, 4, 5, 6].map(value => ({
    value,
    label: new Date(2026, 9, 19 + value).toLocaleDateString(i18n.locale.value, { weekday: "long" }),
  })),
);

const mealTypes = computed(() =>
  (["breakfast", "lunch", "dinner", "snack"] as MealType[]).map(value => ({
    value,
    title: i18n.t(`meal-plan.${value}`),
  })),
);

const mealSlots = computed<DietMealSlot[]>(() => modelValue.value.mealSlots ?? []);
const sharesTotal = computed(() => Math.round(mealSlots.value.reduce((sum, s) => sum + (Number(s.share) || 0), 0) * 10) / 10);
const sharesOk = computed(() => Math.abs(sharesTotal.value - 100) <= 0.5);

function setMealCount(count: number) {
  modelValue.value.mealSlots = (DEFAULT_SLOTS[count] ?? []).map(([mealType, share]) => ({ mealType, share }));
}

function addPerson() {
  const persons = modelValue.value.persons ?? [];
  persons.push({ id: crypto.randomUUID().replaceAll("-", ""), name: "", kcal: 2000, protein: 125, fat: 67, carbs: 225, active: true });
  modelValue.value.persons = persons;
}

function removePerson(index: number) {
  modelValue.value.persons?.splice(index, 1);
}

function macroSummary(person: DietPerson) {
  const fromMacros = 4 * (person.protein || 0) + 9 * (person.fat || 0) + 4 * (person.carbs || 0);
  const pct = (kcal: number) => (person.kcal ? Math.round((kcal / person.kcal) * 100) : 0);
  return i18n.t("diet.macro-summary", {
    protein: pct(4 * (person.protein || 0)),
    fat: pct(9 * (person.fat || 0)),
    carbs: pct(4 * (person.carbs || 0)),
    kcal: Math.round(fromMacros),
  });
}

defineExpose({ sharesOk });
</script>
