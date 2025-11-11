<template>
  <n-popselect
    :default-value="currentTimeframeStore.value"
    style="width: 80px;"
    :scrollable="false"
    @update:value="onTimeframeChange"
    :options="timeframes"
  >
    <n-button
      round
      class="timeframe-button"
    >
      {{ currentTimeframeStore.label }}
    </n-button>
  </n-popselect>
</template>

<script>
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

import { NPopselect, NButton } from "naive-ui";

export default {
  name: "TimeframeDropdown",

  components: {
    NPopselect,
    NButton,
  },

  data() {
    return {
      currentTimeframeStore: useCurrentTimeframeStore(),
      timeframes: [
        { label: "12H", value: 720 },
        { label: "D", value: 1440 },
      ],
    };
  },

  methods: {
    onTimeframeChange(value, option) {
      this.currentTimeframeStore.setCurrentTimeframe(option);
    },
  },
};
</script>

<style scoped>
.timeframe-button {
  width: 80px;
}
</style>