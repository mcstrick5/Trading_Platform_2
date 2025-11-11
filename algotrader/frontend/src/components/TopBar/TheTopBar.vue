<template>
  <div id="wrapper-select">
    <n-button primary round @click="modalStore.openModal('symbolSearch')">
      {{ currentSymbol }}
    </n-button>

    <timeframe-dropdown />

    <n-button round @click="modalStore.openModal('indicatorSearch')">Indicator</n-button>

    <n-button round @click="toggleGrid">Grid: {{ drawingsStore.gridOn ? 'On' : 'Off' }}</n-button>
    <n-button round :loading="isRefreshing" @click="onRefreshData">Refresh Data</n-button>

    <top-bar-modals />
  </div>
</template>

<script>
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useDrawingsStore } from "@/stores/drawingsStore";
import { useModalStore } from "@/stores/modalStore";

import { NButton, createDiscreteApi } from "naive-ui";
import TimeframeDropdown from "@/components/TopBar/TimeframeDropdown.vue";
import TopBarModals from "@/components/TopBar/Modals/TopBarModals.vue";

export default {
  name: "TheTopBar",

  components: {
    NButton,
    TimeframeDropdown,
    TopBarModals,
  },

  data() {
    return {
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      candlesticksStore: useCandlesticksStore(),
      modalStore: useModalStore(),
      drawingsStore: useDrawingsStore(),
      isRefreshing: false,
    };
  },

  computed: {
    currentSymbol() {
      return this.currentMarketStore.symbol;
    },
  },

  methods: {
    toggleGrid() {
      this.drawingsStore.toggleGrid();
      // ChartArea watches this and applies immediately
    },
    async onRefreshData() {
      try {
        this.isRefreshing = true;
        const { message } = createDiscreteApi(['message']);
        const loadingMsg = message.loading('Refreshing data…', { duration: 0 });
        const resp = await fetch('/api/csv-refresh', { method: 'POST' });
        if (!resp.ok) {
          loadingMsg.destroy();
          message.error('Refresh failed');
          return;
        }
        loadingMsg.destroy();
        message.success('Data refreshed');
        // Refetch current candles
        const symbolID = this.currentMarketStore.symbol_id;
        const timeframe = this.currentTimeframeStore.value;
        if (symbolID) {
          await this.candlesticksStore.fetch(symbolID, timeframe, null, null, 5000);
        }
      } catch (e) {
        console.error('Refresh data failed', e);
        const { message } = createDiscreteApi(['message']);
        message.error('Refresh failed');
      } finally {
        this.isRefreshing = false;
      }
    },
  },
};
</script>

<style scoped>
#wrapper-select {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
</style>
