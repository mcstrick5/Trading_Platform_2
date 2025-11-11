<template>
  <div id="chart-wrapper">
    <div ref="chartContainer" id="lightweight-chart" class="chart-container" />

    <div class="chart-toolbar">
      <n-button size="small" @click="onZoomIn">+</n-button>
      <n-button size="small" @click="onZoomOut">-</n-button>
      <n-button size="small" @click="onResetZoom">Reset</n-button>
    </div>

    <span class="legend" v-if="candlestickOhlc">
      <span v-for="(legend, key) in candlestickOhlc" :key="key" class="legend-value">
        {{ legend.label }}: {{ legend.value }}
      </span>
    </span>

    

    <div>
      <indicator
        v-for="indicator in getAllIndicators()"
        :key="indicator.id"
        :indicator="indicator"
        :indicator-manager="indicatorManager"
      />
    </div>
  </div>
</template>

<script>
import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

import { ChartMixin } from "@/utils/chart";
import { NButton } from "naive-ui";
import { useDrawingsStore } from "@/stores/drawingsStore";
import Indicator from "@/components/Chart/Indicator/Indicator.vue";

export default {
  name: "ChartArea",

  components: {
    Indicator,
    NButton,
  },

  mixins: [ChartMixin],

  data() {
    return {
      candlesticksStore: useCandlesticksStore(),
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      drawingsStore: useDrawingsStore(),
      seriesOptions: {
        priceFormat: {
          type: "price",
          minMove: 0.00001,
          precision: 5,
        },
      },
      crossHairTimeout: null,
      candlestickOhlc: undefined,
      isFetchingCandles: false,
      candlesFetchLimit: 5000,
    };
  },

  computed: {
    currentMarketMinMove() {
      return this.currentMarketStore.min_move;
    },
  },

  watch: {
    "candlesticksStore.data": {
      handler(newData) {
        this.setMinMove(this.currentMarketMinMove);
        this.addCandlestickData(newData, this.seriesOptions);
      },
      deep: true,
    },

    "currentMarketStore.symbol_id": {
      handler() {
        this.fetchCandlesticks();
        // Save current context before switching
        this.saveIndicatorsForContext();
        // Clear indicators when switching symbol; they'll be restored if saved for this context
        this.clearIndicatorsForContext();
        this.restoreIndicatorsForContext();
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler() {
        this.fetchCandlesticks();
        // Save current context before switching
        this.saveIndicatorsForContext();
        // Clear indicators when switching timeframe; they'll be restored if saved for this context
        this.clearIndicatorsForContext();
        this.restoreIndicatorsForContext();
      },
      immediate: true,
    },
    // Apply grid toggle immediately
    "drawingsStore.gridOn": {
      handler(on) {
        this.chartManager?.setGrid(on);
      },
      immediate: true,
    },
  },

  mounted() {
    this.initializeChartComponent();
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('beforeunload', this.saveIndicatorsForContext);
  },

  methods: {
    async initializeChartComponent() {
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);

      await this.fetchCandlesticks();
      // Ensure grid state applied
      this.chartManager.setGrid(this.drawingsStore.gridOn);

      // Restore indicators for current context
      this.restoreIndicatorsForContext();
    },

    async fetchCandlesticks() {
      if (this.currentMarketStore.symbol_id === null) return;

      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;

      await this.candlesticksStore.fetch(symbolID, timeframe, null, null, this.candlesFetchLimit);
      // After candles fetched, ensure indicators render for this context
      this.clearIndicatorsForContext();
      this.restoreIndicatorsForContext();
    },

    setMinMove(minMove) {
      this.seriesOptions.priceFormat.minMove = minMove;
      this.seriesOptions.priceFormat.precision = Math.log10(1 / minMove);
    },

    onCrosshairMove(param) {
      try {
        if (this.crossHairTimeout != null) {
          clearTimeout(this.crossHairTimeout);
        }

        const validCrosshairPoint = this.isValidCrosshairPoint(param);
        if (!validCrosshairPoint) {
          return;
        }

        this.crossHairTimeout = setTimeout(() => {
          const bar = Array.from(param.seriesData.values())[0];

          if (!bar) {
            return;
          }
          // Update small legacy legend
          this.candlestickOhlc = {
            open: { label: "O", value: bar.open },
            high: { label: "H", value: bar.high },
            low: { label: "L", value: bar.low },
            close: { label: "C", value: bar.close },
          };

          this.crossHairTimeout = null;
        }, 10);
      } catch (error) {
        console.log("Error in crosshair move handler:", error);
      }
    },

    onVisibleLogicalRangeChange(newVisibleLogicalRange) {
      const series = this.getSeries();

      for (const [, value] of series.entries()) {
        const barsInfo = value.series.barsInLogicalRange(newVisibleLogicalRange);

        if (barsInfo !== null && barsInfo.barsBefore < 100 && !this.isFetchingCandles) {
          this.isFetchingCandles = true;

          this.loadMoreBars();
        }
      }
    },

    async loadMoreBars() {
      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;
      const firstBarTime = this.candlesticksStore.data[0].time;
      const firstBarDate = new Date(firstBarTime * 1000).toISOString().slice(0, -5);

      await this.candlesticksStore.fetch(symbolID, timeframe, null, firstBarDate, this.candlesFetchLimit, true);
      this.isFetchingCandles = false;
    },

    isValidCrosshairPoint(param) {
      return (
        param !== undefined &&
        param.time !== undefined &&
        param.point.x >= 0 &&
        param.point.y >= 0
      );
    },

    getAllIndicators() {
      return this.indicatorsStore.all;
    },

    // ===== Indicator persistence =====
    storageKey() {
      const sym = this.currentMarketStore.symbol; // use symbol text for CSV mode
      const tf = this.currentTimeframeStore.value;
      return sym == null || tf == null ? null : `indicators:v2:${sym}:${tf}`;
    },
    saveIndicatorsForContext() {
      try {
        const key = this.storageKey();
        if (!key) return;
        const payload = this.indicatorsStore.all.map(ind => ({
          info: ind.info,
          parameters: Object.fromEntries(Object.entries(ind.parameters || {}).map(([k,v]) => [k, v?.value])),
          visible: ind.visible !== false,
        }));
        localStorage.setItem(key, JSON.stringify({ list: payload }));
      } catch {}
    },
    clearIndicatorsForContext() {
      try {
        for (const ind of this.indicatorsStore.all) {
          this.indicatorManager.removeIndicatorSeriesAndData(ind.id);
        }
        this.indicatorsStore.clear();
      } catch {}
    },
    async restoreIndicatorsForContext() {
      try {
        const key = this.storageKey();
        if (!key) return;
        const raw = localStorage.getItem(key);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed?.list)) return;
        
        // Clear any existing indicators first
        this.clearIndicatorsForContext();
        
        // Recreate indicators for this context
        for (const item of parsed.list) {
          const params = {};
          for (const [k, v] of Object.entries(item.parameters || {})) {
            params[k] = { value: v };
          }
          
          const id = this.indicatorsStore.addIndicator(item.info, [], params);
          
          // Set visibility immediately
          this.indicatorsStore.setVisibility(id, item.visible !== false);
          
          // Fetch data for each indicator
          const symbol = this.currentMarketStore.symbol_id;
          const tf = this.currentTimeframeStore.value;
          const name = item.info?.code || this.mapNameToCode(item.info?.name);
          
          if (symbol && name) {
            try {
              const resp = await fetch(
                `/api/csv-indicator/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(tf)}&name=${encodeURIComponent(name)}`
              );
              if (resp.ok) {
                const series = await resp.json();
                this.indicatorsStore.updateIndicatorData(id, series);
                this.$nextTick(() => {
                  if (this.indicatorManager) {
                    this.indicatorManager.addIndicatorSeries(id);
                  }
                });
              }
            } catch (error) {
              console.error('Error loading indicator data:', error);
            }
          }
        }
      } catch (error) {
        console.error('Error restoring indicators:', error);
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

    // ===== Toolbar and keyboard =====
    onZoomIn() { this.chartManager?.zoomIn?.(); },
    onZoomOut() { this.chartManager?.zoomOut?.(); },
    onResetZoom() { this.chartManager?.resetZoom?.(); },
    onKeyDown(e) {
      if (e.key === '+=' || e.key === '+') this.onZoomIn();
      else if (e.key === '-' || e.key === '_') this.onZoomOut();
      else if (e.key === '0') this.onResetZoom();
      else if (e.key === 'ArrowLeft') this.chartManager?.scrollBars?.(-10);
      else if (e.key === 'ArrowRight') this.chartManager?.scrollBars?.(10);
    },
  },
};
</script>

<style scoped>
#chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.chart-toolbar {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 6px;
  z-index: 1200;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.legend {
  position: absolute;
  top: 50px;
  left: 10px;
}

.legend-value {
  margin-right: 10px;
}


</style>
