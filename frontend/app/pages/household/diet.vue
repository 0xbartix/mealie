<template>
  <v-container class="narrow-container">
    <BasePageTitle class="mb-5">
      <template #header>
        <v-img width="100%" max-height="100" max-width="100" src="/svgs/manage-group-settings.svg" />
      </template>
      <template #title>
        {{ $t("diet.diet-plan") }}
      </template>
      {{ $t("diet.diet-plan-description") }}
    </BasePageTitle>

    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab value="plan">
        {{ $t("diet.plan") }}
      </v-tab>
      <v-tab value="settings">
        {{ $t("diet.settings") }}
      </v-tab>
    </v-tabs>

    <v-window v-if="settings && draft" v-model="tab">
      <v-window-item value="plan">
        <DietPlanView :settings="settings" />
      </v-window-item>
      <v-window-item value="settings">
        <DietSettingsForm ref="form" v-model="draft" />
        <div class="d-flex pa-2 mt-4">
          <BaseButton save class="ml-auto" :loading="saving" :disabled="!sharesOk" @click="saveSettings">
            {{ $t("diet.save-settings") }}
          </BaseButton>
        </div>
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup lang="ts">
import DietPlanView from "~/components/Domain/Diet/DietPlanView.vue";
import DietSettingsForm from "~/components/Domain/Diet/DietSettingsForm.vue";
import { useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { DietSettingsOut, DietSettingsUpdate } from "~/lib/api/types/diet";

definePageMeta({
  middleware: ["auth"],
});

const api = useUserApi();
const i18n = useI18n();

useSeoMeta({
  title: i18n.t("diet.diet-plan"),
});

const tab = ref("plan");
const settings = ref<DietSettingsOut | null>(null);
const draft = ref<DietSettingsUpdate | null>(null);
const saving = ref(false);
const form = ref<InstanceType<typeof DietSettingsForm> | null>(null);
const sharesOk = computed(() => form.value?.sharesOk ?? true);

function toDraft(value: DietSettingsOut): DietSettingsUpdate {
  return JSON.parse(JSON.stringify({ persons: value.persons, cookingDays: value.cookingDays, mealSlots: value.mealSlots }));
}

onMounted(async () => {
  const { data } = await api.diet.getSettings();
  if (data) {
    settings.value = data;
    draft.value = toDraft(data);
    if (!data.persons?.length) {
      tab.value = "settings";
    }
  }
});

async function saveSettings() {
  if (!draft.value) {
    return;
  }
  saving.value = true;
  const { data, error } = await api.diet.updateSettings(draft.value);
  saving.value = false;
  if (error || !data) {
    alert.error(i18n.t("events.something-went-wrong"));
    return;
  }
  settings.value = data;
  draft.value = toDraft(data);
  alert.success(i18n.t("diet.settings-saved"));
}
</script>
