<template>
  <v-form>
    <div>
      <v-card-title class="headline">
        {{ $t("diet.import-from-files") }}
      </v-card-title>
      <v-card-text>
        {{ $t("diet.import-from-files-description") }}
        <v-file-input
          v-model="files"
          accept=".md,.zip"
          label=".md / .zip"
          multiple
          chips
          variant="solo-filled"
          clearable
          class="rounded-lg mt-2"
          rounded
          prepend-icon=""
          :prepend-inner-icon="$globals.icons.upload"
        />
        <v-expansion-panels class="mt-2">
          <v-expansion-panel>
            <v-expansion-panel-title>{{ $t("diet.file-template") }}</v-expansion-panel-title>
            <v-expansion-panel-text>
              <pre class="template">{{ template }}</pre>
              <BaseButton secondary :icon="$globals.icons.contentCopy" class="mt-2" @click="copyTemplate">
                {{ $t("diet.copy-template") }}
              </BaseButton>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
      <v-card-actions class="justify-center">
        <div style="width: 250px">
          <BaseButton
            :disabled="!files.length"
            rounded
            block
            :loading="loading"
            :icon="$globals.icons.upload"
            @click="importFiles"
          >
            {{ $t("diet.import") }}
          </BaseButton>
        </div>
      </v-card-actions>

      <v-card-text v-if="results.length">
        <p class="mb-2 font-weight-medium">
          {{ summary }}
        </p>
        <v-list density="compact" class="py-0">
          <v-list-item v-for="result in results" :key="result.fileName" class="px-0">
            <div class="d-flex flex-wrap align-center ga-2">
              <v-chip size="small" label :color="statusColor(result.status)">
                {{ $t(`diet.import-result-${result.status}`) }}
              </v-chip>
              <router-link v-if="result.recipeSlug" :to="`/g/${groupSlug}/r/${result.recipeSlug}`" class="text-primary">
                {{ result.recipeName }}
              </router-link>
              <span class="text-caption text-medium-emphasis">{{ result.fileName }}</span>
            </div>
            <div v-for="message in result.errors" :key="message" class="text-caption text-error ml-1">
              {{ message }}
            </div>
            <div v-for="message in result.warnings" :key="message" class="text-caption text-warning ml-1">
              {{ message }}
            </div>
          </v-list-item>
        </v-list>
      </v-card-text>
    </div>
  </v-form>
</template>

<script setup lang="ts">
import { useUserApi } from "~/composables/api";
import { useCopy } from "~/composables/use-copy";
import { alert } from "~/composables/use-toast";
import type { DietImportResult, DietImportStatus } from "~/lib/api/types/diet";

const api = useUserApi();
const i18n = useI18n();
const auth = useMealieAuth();
const route = useRoute();
const groupSlug = computed(() => (route.params.groupSlug as string) || auth.user.value?.groupSlug || "");

const files = ref<File[]>([]);
const loading = ref(false);
const results = ref<DietImportResult[]>([]);

const template = `---
nazwa: Owsianka z jabłkiem
porcje: 2
posilek: [sniadanie]          # sniadanie / obiad / kolacja / przekaska
kcal: 420                     # wartości NA 1 PORCJĘ
bialko: 18                    # gramy
tluszcz: 12
weglowodany: 60
czas: 15                      # minuty, opcjonalnie
tagi: [wege, szybkie]         # opcjonalnie
zrodlo: https://...           # opcjonalnie
---
## Składniki
- 100 g płatki owsiane
- 400 ml mleko 2%
- 1 szt jabłko, starte
- 30 g masło orzechowe

## Przygotowanie
1. Płatki zalej mlekiem i gotuj 5 minut.
2. Dodaj starte jabłko i masło orzechowe.
`;

const summary = computed(() => {
  const count = (status: DietImportStatus) => results.value.filter(r => r.status === status).length;
  return i18n.t("diet.imported-summary", { created: count("created"), updated: count("updated"), errors: count("error") });
});

function statusColor(status: DietImportStatus) {
  return status === "error" ? "error" : status === "updated" ? "info" : "success";
}

const { copyText } = useCopy();
function copyTemplate() {
  copyText(template);
}

async function importFiles() {
  loading.value = true;
  try {
    const response = await api.diet.importFiles(files.value);
    results.value = response.data.results;
    files.value = [];
  }
  catch (error) {
    console.error(error);
    alert.error(i18n.t("events.something-went-wrong"));
  }
  finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.template {
  white-space: pre-wrap;
  font-size: 0.8rem;
  background: rgba(127, 127, 127, 0.1);
  padding: 12px;
  border-radius: 8px;
}
</style>
