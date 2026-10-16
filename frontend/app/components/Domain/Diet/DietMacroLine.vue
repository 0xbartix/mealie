<template>
  <div v-if="macros" class="d-flex flex-wrap ga-1">
    <v-chip size="small" variant="tonal" color="primary">
      {{ Math.round(macros.kcal ?? 0) }} kcal
    </v-chip>
    <v-chip size="small" variant="tonal">
      B {{ round(macros.protein) }} g
    </v-chip>
    <v-chip size="small" variant="tonal">
      T {{ round(macros.fat) }} g
    </v-chip>
    <v-chip size="small" variant="tonal">
      W {{ round(macros.carbs) }} g
    </v-chip>
  </div>
</template>

<script setup lang="ts">
import type { DietMacros } from "~/lib/api/types/diet";

defineProps<{ macros: DietMacros | null }>();

function round(value?: number) {
  return Math.round((value ?? 0) * 10) / 10;
}
</script>
