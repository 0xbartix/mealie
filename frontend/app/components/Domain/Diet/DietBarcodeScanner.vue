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
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ detected: [code: string] }>();

const i18n = useI18n();
const video = ref<HTMLVideoElement | null>(null);
const manual = ref("");
const error = ref("");
let stream: MediaStream | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
let active = false;

const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

async function detector() {
  // the ponyfill uses the browser's own detector when there is one (Chrome on Android) and a WebAssembly
  // build of ZXing otherwise (e.g. Safari on iPhone)
  const { BarcodeDetector } = await import("barcode-detector/ponyfill");
  return new BarcodeDetector({ formats: FORMATS as never });
}

async function start() {
  error.value = "";
  manual.value = "";
  if (!navigator.mediaDevices?.getUserMedia) {
    error.value = i18n.t("diet.camera-unavailable");
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  }
  catch {
    error.value = i18n.t("diet.camera-unavailable");
    return;
  }
  if (!video.value) {
    return;
  }
  video.value.srcObject = stream;
  await video.value.play();
  const reader = await detector();
  active = true;

  const scan = async () => {
    if (!active || !video.value) {
      return;
    }
    try {
      const codes = await reader.detect(video.value);
      const code = codes.find(c => /^\d{6,14}$/.test(c.rawValue))?.rawValue;
      if (code) {
        emit("detected", code);
        open.value = false;
        return;
      }
    }
    catch {
      // a frame that couldn't be read – try the next one
    }
    timer = setTimeout(scan, 250);
  };
  scan();
}

function stop() {
  active = false;
  if (timer) {
    clearTimeout(timer);
  }
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
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
