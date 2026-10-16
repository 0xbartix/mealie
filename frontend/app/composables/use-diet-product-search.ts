import type { Ref } from "vue";
import { useUserApi } from "~/composables/api";
import type { DietOffProduct } from "~/lib/api/types/diet";

/**
 * Searches the Open Food Facts product database as the query is typed (after a short pause).
 * Only the newest answer counts when an older, slower one arrives later.
 */
export function useDietProductSearch(query: Ref<string | null | undefined>, delay = 450) {
  const api = useUserApi();
  const results = ref<DietOffProduct[]>([]);
  const unavailable = ref(false);
  const searching = ref(false);
  const searched = ref(false);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let run = 0;

  async function search(q: string) {
    const current = ++run;
    searching.value = true;
    const { data } = await api.diet.searchProducts(q);
    if (current !== run) {
      return;
    }
    searching.value = false;
    searched.value = true;
    results.value = data?.off ?? [];
    unavailable.value = !!data?.offUnavailable;
  }

  function searchNow() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    const q = (query.value || "").trim();
    if (q.length >= 2) {
      search(q);
    }
  }

  /** Drops a result once it has been saved to the household's products. */
  function forget(code: string) {
    results.value = results.value.filter(r => r.code !== code);
  }

  watch(query, (value) => {
    if (timer) {
      clearTimeout(timer);
    }
    run++; // drop answers to what was typed before
    searching.value = false;
    results.value = [];
    searched.value = false;
    unavailable.value = false;
    if ((value || "").trim().length >= 2) {
      timer = setTimeout(searchNow, delay);
    }
  });

  onBeforeUnmount(() => {
    if (timer) {
      clearTimeout(timer);
    }
  });

  return { results, unavailable, searching, searched, searchNow, forget };
}
