<template>
  <v-dialog v-model="open" max-width="480" @after-leave="stop">
    <v-card>
      <v-card-title>{{ $t("diet.scan-barcode") }}</v-card-title>
      <v-card-text>
        <div class="scanner">
          <video ref="video" playsinline muted class="scanner-video" />
          <div class="scanner-frame" />
        </div>
        <p v-if="error" class="text-caption text-error mt-2">
          {{ error }}
        </p>
        <p v-else class="text-caption text-medium-emphasis mt-2">
          {{ $t("diet.scan-hint") }}
        </p>
        <v-text-field
          v-model="manual"
          :label="$t('diet.barcode-manual')"
          inputmode="numeric"
          density="compact"
          hide-details
          class="mt-2"
          @keyup.enter="submitManual"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <BaseButton cancel @click="open = false" />
        <BaseButton :disabled="!manual.trim()" @click="submitManual">
          {{ $t("diet.search") }}
        </BaseButton>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import wasmUrl from "zxing-wasm/reader/zxing_reader.wasm?url";

const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ detected: [code: string] }>();

const i18n = useI18n();
const video = ref<HTMLVideoElement | null>(null);
const manual = ref("");
const error = ref("");
let stream: MediaStream | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
let run = 0; // every start/stop bumps it, so a start still waiting for the camera knows it was cancelled

const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

interface Reader {
  detect: (source: HTMLVideoElement) => Promise<{ rawValue: string }[]>;
}

async function detector(): Promise<Reader> {
  // the browser's own reader when it has one (Chrome on Android, Safari on Mac), otherwise ZXing compiled to
  // WebAssembly – served with the app instead of the package's default CDN
  const Native = (globalThis as { BarcodeDetector?: any }).BarcodeDetector;
  if (Native) {
    const supported: string[] = await Native.getSupportedFormats().catch(() => []);
    if (supported.includes("ean_13")) {
      return new Native({ formats: FORMATS.filter(f => supported.includes(f)) });
    }
  }
  const { BarcodeDetector, prepareZXingModule } = await import("barcode-detector/ponyfill");
  prepareZXingModule({
    overrides: { locateFile: (path: string, prefix: string) => (path.endsWith(".wasm") ? wasmUrl : prefix + path) },
  });
  return new BarcodeDetector({ formats: FORMATS as never });
}

function stopTracks(media: MediaStream | null) {
  media?.getTracks().forEach(track => track.stop());
}

async function start() {
  const current = ++run;
  const cancelled = () => current !== run;
  error.value = "";
  manual.value = "";
  if (!navigator.mediaDevices?.getUserMedia) {
    error.value = i18n.t("diet.camera-unavailable");
    return;
  }
  let media: MediaStream;
  try {
    media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  }
  catch {
    if (!cancelled()) {
      error.value = i18n.t("diet.camera-unavailable");
    }
    return;
  }
  if (cancelled() || !video.value) {
    stopTracks(media);
    return;
  }
  stream = media;
  let reader: Reader;
  try {
    video.value.srcObject = media;
    await video.value.play();
    reader = await detector();
  }
  catch {
    if (!cancelled()) {
      error.value = i18n.t("diet.scanner-failed");
      stop();
    }
    return;
  }
  if (cancelled()) {
    return;
  }

  let failures = 0;
  const scan = async () => {
    if (cancelled() || !video.value) {
      return;
    }
    try {
      const codes = await reader.detect(video.value);
      failures = 0;
      const code = codes.find(c => /^\d{6,14}$/.test(c.rawValue))?.rawValue;
      if (code && !cancelled()) {
        emit("detected", code);
        open.value = false;
        return;
      }
    }
    catch {
      // a single unreadable frame is fine; a reader that keeps failing is broken
      if (++failures >= 8) {
        error.value = i18n.t("diet.scanner-failed");
        stop();
        return;
      }
    }
    timer = setTimeout(scan, 250);
  };
  scan();
}

function stop() {
  run++;
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  stopTracks(stream);
  stream = null;
  if (video.value) {
    video.value.srcObject = null;
  }
}

function submitManual() {
  const code = manual.value.replace(/\D/g, "");
  if (code) {
    emit("detected", code);
    open.value = false;
  }
}

watch(open, (value) => {
  if (value) {
    nextTick(start);
  }
  else {
    stop();
  }
});

onBeforeUnmount(stop);
</script>

<style scoped>
.scanner {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.scanner-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.scanner-frame {
  position: absolute;
  inset: 30% 12%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  border-radius: 8px;
}
</style>
