<template>
  <div>
    <Teleport
      :to="indicator.paneHtmlElement?.querySelector('.indicators-wrapper')"
      v-if="indicator.paneHtmlElement"
    >
      <div class="indicator-container">
        <indicator-panel
          :indicator="indicator"
          @remove-indicator="onRemoveIndicator"
          @toggle-visibility="onToggleVisibility"
          @reset-parameters="onResetParameters"
        />
      </div>
    </Teleport>

    <indicator-settings-modal
      :indicator="indicator"
      :modalId="`indicatorSettings_${indicator.id}`"
      @update-styles="onUpdateStyles"
    />
  </div>
</template>

<script>
import IndicatorPanel from "./IndicatorPanel.vue";
import IndicatorSettingsModal from "./IndicatorSettingsModal.vue";
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

export default {
  name: "Indicator",

  components: {
    IndicatorPanel,
    IndicatorSettingsModal,
  },

  props: {
    indicatorManager: {
      type: Object,
      required: true,
    },

    indicator: {
      type: Object,
      required: true,
    },
  },

  emits: ["remove-indicator"],

  data() {
    return {
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
    };
  },

  watch: {
    "indicator.paneIndex": {
      handler(paneIndex) {
        if (paneIndex === null || paneIndex === undefined) {
          return;
        }

        this.indicatorManager.updateMissingPaneHtmlElements();
      },
      immediate: true,
    },

    "indicator.paneHtmlElement": {
      handler(paneHtmlElement) {
        if (!paneHtmlElement) {
          return;
        }

        paneHtmlElement.style.position = "relative";

        if (!paneHtmlElement.querySelector(".indicators-wrapper")) {
          const wrapper = this.createNewIndicatorsWrapper();
          paneHtmlElement.appendChild(wrapper);
        }
      },
      immediate: true,
    },

    "indicator.data": {
      handler(newData) {
        if (!newData || newData.length === 0) {
          return;
        }

        // Ensure pane wrapper exists then add series to chart
        this.indicatorManager.updateMissingPaneHtmlElements();
        this.indicatorManager.addIndicatorSeries(this.indicator.id);
      },
      deep: true,
      immediate: true,
    },
  },

  methods: {
    onRemoveIndicator(indicatorId) {
      this.indicatorManager.removeIndicatorSeriesAndData(indicatorId);
      this.indicatorManager.updateMissingPaneHtmlElements();
    },

    onUpdateStyles({ outputKey, styles }) {
      this.indicatorManager.updateIndicatorStyles(this.indicator.id, outputKey, styles);
    },

    onToggleVisibility(indicatorId) {
      const ind = this.indicatorsStore.getById(indicatorId);
      const next = !(ind?.visible === true);
      this.indicatorsStore.setVisibility(indicatorId, next);
      this.indicatorManager.addIndicatorSeries(indicatorId);
    },

    async onResetParameters(indicatorId) {
      // Reset to defaults in store
      this.indicatorsStore.resetIndicatorParameters(indicatorId);
      // Fetch fresh data from CSV endpoint based on indicator type
      try {
        const ind = this.indicatorsStore.getById(indicatorId);
        const symbol = this.currentMarketStore.symbol_id;
        const tf = this.currentTimeframeStore.value;
        if (!ind || !symbol) return;
        const name = ind.info?.name;
        const code = this.mapNameToCode(name);
        if (!code) return;
        const resp = await fetch(`/api/csv-indicator/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(tf)}&name=${encodeURIComponent(code)}`);
        const series = await resp.json();
        this.indicatorsStore.updateIndicatorData(indicatorId, series);
        // Re-render
        this.indicatorManager.addIndicatorSeries(indicatorId);
      } catch (e) {
        console.error('Failed to reset indicator', e);
      }
    },

    mapNameToCode(name) {
      if (!name) return null;
      if (name === 'Simple Moving Average') return 'SMA';
      if (name === 'Relative Strength Index') return 'RSI';
      if (name === 'Bollinger Bands') return 'BBANDS';
      if (name === 'Moving Average Convergence Divergence') return 'MACD';
      return null;
    },

    createNewIndicatorsWrapper() {
      const wrapper = document.createElement("div");
      wrapper.className = "indicators-wrapper";
      wrapper.style.cssText = `
        position: absolute;
        top: 10px;
        left: 0px;
        z-index: 1000;
        max-width: 350px;
      `;
      return wrapper;
    },
  },
};
</script>

<style scoped>
.indicator-container {
  margin-bottom: 8px;
}
</style>
