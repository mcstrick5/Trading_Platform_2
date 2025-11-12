<template>
  <div id="chart-wrapper" @contextmenu.prevent="onRightClick">
    <drawing-toolbar @clear-drawings="clearAllDrawings" />
    
    <drawing-context-menu
      :visible="contextMenu.visible"
      :x="contextMenu.x"
      :y="contextMenu.y"
      @delete="deleteSelectedDrawing"
      @change-color="changeDrawingColor"
      @change-width="changeDrawingWidth"
    />
    
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
import DrawingToolbar from "@/components/Chart/DrawingToolbar.vue";
import DrawingContextMenu from "@/components/Chart/DrawingContextMenu.vue";

export default {
  name: "ChartArea",

  components: {
    Indicator,
    NButton,
    DrawingToolbar,
    DrawingContextMenu,
  },

  mixins: [ChartMixin],

  data() {
    return {
      candlesticksStore: useCandlesticksStore(),
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      drawingsStore: useDrawingsStore(),
      isSwitchingContext: false,
      lastSymbolText: null,
      lastTimeframe: null,
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
      isRestoringIndicators: false,
      drawingClickCount: 0,
      drawingFirstPoint: null,
      contextMenu: {
        visible: false,
        x: 0,
        y: 0,
      },
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
      handler(newVal, oldVal) {
        this.isSwitchingContext = true;
        try {
          // Save drawings for previous context using tracked values
          if (this.lastSymbolText && this.lastTimeframe) {
            this.saveDrawings(this.lastSymbolText, this.lastTimeframe);
          }
          this.fetchCandlesticks();
          // Save current context before switching
          this.saveIndicatorsForContext();
          // Clear indicators when switching symbol; they'll be restored if saved for this context
          this.clearIndicatorsForContext();
          // Clear all drawings from chart BEFORE restoring new ones
          this.clearAllDrawingsFromChart();
          this.restoreIndicatorsForContext();
          // Restore drawings for new symbol
          this.restoreDrawings();
        } finally {
          this.isSwitchingContext = false;
          // Update last known context to new values
          this.lastSymbolText = this.currentMarketStore.symbol;
          this.lastTimeframe = this.currentTimeframeStore.value;
        }
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler(newVal, oldVal) {
        if (this.isSwitchingContext) return; // avoid double-processing during symbol switches
        console.log('[WATCHER] Timeframe changed from', oldVal, 'to', newVal);
        this.saveIndicatorsForContext(this.currentMarketStore.symbol_id, oldVal);
        // Save drawings for previous timeframe of current symbol
        if (this.lastTimeframe) {
          const sym = this.currentMarketStore.symbol;
          this.saveDrawings(sym, this.lastTimeframe);
        }
        this.fetchCandlesticks();
        this.restoreIndicatorsForContext();
        // Clear all drawings from chart BEFORE restoring new ones
        this.clearAllDrawingsFromChart();
        this.restoreDrawings();
        // Update last timeframe after switch
        this.lastTimeframe = this.currentTimeframeStore.value;
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
    // Disable crosshair in drawing mode
    "drawingsStore.drawMode": {
      handler(drawMode) {
        if (this.chartManager) {
          this.chartManager.setCrosshairEnabled(!drawMode);
        }
      },
      immediate: true,
    },
  },

  mounted() {
    this.initializeChartComponent();
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('beforeunload', () => this.saveIndicatorsForContext());
    
    // Add method to clear all drawings from browser console
    window.clearAllDrawingsStorage = () => {
      const keys = Object.keys(localStorage).filter(k => k.startsWith('draw:'));
      keys.forEach(k => localStorage.removeItem(k));
      console.log('Cleared drawing storage for:', keys);
    };

    // Initialize last known context
    this.lastSymbolText = this.currentMarketStore.symbol;
    this.lastTimeframe = this.currentTimeframeStore.value;
  },

  methods: {
    async initializeChartComponent() {
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);
      this.chartManager.subscribeClick(this.onChartClick);

      await this.fetchCandlesticks();
      // Ensure grid state applied
      this.chartManager.setGrid(this.drawingsStore.gridOn);

      // Restore indicators and drawings for current context
      this.restoreIndicatorsForContext();
      this.restoreDrawings();
    },

    async fetchCandlesticks() {
      if (this.currentMarketStore.symbol_id === null) return;

      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;

      await this.candlesticksStore.fetch(symbolID, timeframe, null, null, this.candlesFetchLimit);
      // After candles fetched, ensure indicators render for this context
      this.restoreIndicatorsForContext();
    },

    setMinMove(minMove) {
      // Enforce 2 decimals for stock-like tickers (e.g., AAPL, MSFT, SPY)
      const sym = this.currentMarketStore.symbol;
      const looksLikeStock = typeof sym === 'string' && /^[A-Z.]+$/.test(sym) && !sym.includes('/');
      const effectiveMinMove = looksLikeStock ? Math.max(minMove, 0.01) : minMove;

      this.seriesOptions.priceFormat.minMove = effectiveMinMove;
      this.seriesOptions.priceFormat.precision = Math.log10(1 / effectiveMinMove);
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
      if (!this.candlesticksStore.data || this.candlesticksStore.data.length === 0) {
        this.isFetchingCandles = false;
        return;
      }
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

    storageMapKey() {
      return "indicators:v3";
    },
    makeContextKey(symId, tf) {
      return symId == null || tf == null ? null : `${symId}:${tf}`;
    },
    readStorageMap() {
      try {
        const raw = localStorage.getItem(this.storageMapKey());
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {};
      } catch { return {}; }
    },
    writeStorageMap(map) {
      try { localStorage.setItem(this.storageMapKey(), JSON.stringify(map)); } catch {}
    },
    saveIndicatorsForContext(symIdOverride = null, tfOverride = null) {
      try {
        const symId = symIdOverride ?? this.currentMarketStore.symbol_id;
        const tf = tfOverride ?? this.currentTimeframeStore.value;
        const ctxKey = this.makeContextKey(symId, tf);
        console.log('[SAVE] Context key:', ctxKey, 'Indicators count:', this.indicatorsStore.all.length);
        if (!ctxKey) return;
        const payload = this.indicatorsStore.all.map(ind => ({
          info: ind.info,
          parameters: Object.fromEntries(Object.entries(ind.parameters || {}).map(([k,v]) => [k, v?.value])),
          visible: ind.visible !== false,
        }));
        const map = this.readStorageMap();
        map[ctxKey] = { list: payload };
        this.writeStorageMap(map);
        console.log('[SAVE] Saved to storage:', JSON.stringify(map, null, 2));
      } catch (e) {
        console.error('[SAVE] Error:', e);
      }
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
        if (this.isRestoringIndicators) return;
        this.isRestoringIndicators = true;
        const symId = this.currentMarketStore.symbol_id;
        const tf = this.currentTimeframeStore.value;
        const ctxKey = this.makeContextKey(symId, tf);
        console.log('[RESTORE] Context key:', ctxKey);
        if (!ctxKey) return;
        const map = this.readStorageMap();
        console.log('[RESTORE] Full storage map:', JSON.stringify(map, null, 2));
        const entry = map[ctxKey];
        console.log('[RESTORE] Entry for context:', entry);
        if (!entry || !Array.isArray(entry.list)) {
          console.log('[RESTORE] No indicators to restore for this context');
          this.clearIndicatorsForContext();
          return;
        }
        
        // Clear any existing indicators first
        this.clearIndicatorsForContext();
        console.log('[RESTORE] Restoring', entry.list.length, 'indicators');
        
        // Recreate indicators for this context
        for (const item of entry.list) {
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
                // Only update if indicator still exists (avoid race conditions)
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
      } finally {
        this.isRestoringIndicators = false;
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
      else if (e.key === 'Escape' && this.drawingsStore.drawMode) {
        this.drawingsStore.setDrawMode(false);
        this.drawingClickCount = 0;
        this.drawingFirstPoint = null;
      }
    },

    // ===== Drawing tools =====
    onChartClick(param) {
      // Close context menu on any click
      this.contextMenu.visible = false;
      
      if (!this.drawingsStore.drawMode) return;
      
      if (!param.time) return;

      // Get price from the chart's price scale using logical coordinates
      const price = this.chartManager.priceFromY(param.point?.y || 0);
      
      if (!price) return;

      const point = { time: param.time, price: price };

      if (this.drawingsStore.tool === 'horizontal') {
        // Horizontal line only needs one click
        // Create a line that extends from the click point to the right edge of visible chart
        const chartWidth = this.$refs.chartContainer?.clientWidth || 1000;
        const rightTime = this.chartManager?.timeFromX?.(chartWidth - 50); // 50px from right edge
        const endTime = rightTime || (param.time + (30 * 24 * 60 * 60)); // 30 days ahead as fallback
        
        const id = this.drawingsStore.addLine(point, { time: endTime, price: point.price }, 'horizontal');
        this.renderDrawing(id);
        this.saveDrawings();
      } else if (this.drawingsStore.tool === 'trendline') {
        // Trendline needs two clicks
        if (this.drawingClickCount === 0) {
          this.drawingFirstPoint = point;
          this.drawingClickCount = 1;
        } else {
          const id = this.drawingsStore.addLine(this.drawingFirstPoint, point, 'trendline');
          this.renderDrawing(id);
          this.saveDrawings();
          this.drawingClickCount = 0;
          this.drawingFirstPoint = null;
        }
      }
    },

    renderDrawing(id) {
      const line = this.drawingsStore.lines.find(l => l.id === id);
      if (!line) return;

      this.chartManager.addTrendline(id, line.a, line.b, {
        color: '#ffffff', // Always white
        lineWidth: line.lineWidth,
      });
    },

    renderAllDrawings() {
      console.log('[DRAW] renderAllDrawings called with', this.drawingsStore.lines.length, 'lines');
      this.drawingsStore.lines.forEach(line => {
        console.log('[DRAW] Rendering line', line.id);
        this.chartManager.addTrendline(line.id, line.a, line.b, {
          color: '#ffffff', // Always white
          lineWidth: line.lineWidth,
        });
      });
    },

    clearAllDrawings() {
      this.drawingsStore.lines.forEach(line => {
        this.chartManager.removeTrendline(line.id);
      });
      this.drawingsStore.clear();
      this.saveDrawings();
    },

    clearAllDrawingsFromChart() {
      // Only remove from chart, keep in store
      this.drawingsStore.lines.forEach(line => {
        this.chartManager.removeTrendline(line.id);
      });
    },

    saveDrawings(symbolOverride, timeframeOverride) {
      const symbol = symbolOverride || this.currentMarketStore.symbol; // Use symbol text like "AAPL"
      const timeframe = timeframeOverride || this.currentTimeframeStore.value;
      if (!symbol || !timeframe) return;
      console.log('[DRAW] Saving drawings for', `${symbol}:${timeframe}`, this.drawingsStore.lines);
      this.drawingsStore.saveFor(symbol, timeframe);
    },

    restoreDrawings() {
      const symbol = this.currentMarketStore.symbol; // Use symbol text like "AAPL"
      const timeframe = this.currentTimeframeStore.value;
      console.log('[DRAW] Restoring drawings for', `${symbol}:${timeframe}`);
      this.drawingsStore.loadFor(symbol, timeframe);
      console.log('[DRAW] Loaded drawings', this.drawingsStore.lines);
      this.renderAllDrawings();
    },

    // ===== Drawing selection and editing =====
    onRightClick(e) {
      // Check if we're near a drawing
      const clickedDrawing = this.findDrawingNearClick(e);
      
      if (clickedDrawing) {
        this.drawingsStore.selectLine(clickedDrawing.id);
        this.contextMenu = {
          visible: true,
          x: e.clientX,
          y: e.clientY,
        };
      } else {
        this.contextMenu.visible = false;
        this.drawingsStore.deselectLine();
      }
    },

    findDrawingNearClick(e) {
      const rect = this.$refs.chartContainer.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;
      const threshold = 10; // pixels

      for (const line of this.drawingsStore.lines) {
        const x1 = this.chartManager.xFromTime(line.a.time);
        const y1 = this.chartManager.yFromPrice(line.a.price);
        const x2 = this.chartManager.xFromTime(line.b.time);
        const y2 = this.chartManager.yFromPrice(line.b.price);

        if (x1 == null || y1 == null || x2 == null || y2 == null) continue;

        const dist = this.distanceToLine(clickX, clickY, x1, y1, x2, y2);
        if (dist < threshold) {
          return line;
        }
      }
      return null;
    },

    distanceToLine(px, py, x1, y1, x2, y2) {
      const A = px - x1;
      const B = py - y1;
      const C = x2 - x1;
      const D = y2 - y1;

      const dot = A * C + B * D;
      const lenSq = C * C + D * D;
      let param = -1;
      if (lenSq !== 0) param = dot / lenSq;

      let xx, yy;

      if (param < 0) {
        xx = x1;
        yy = y1;
      } else if (param > 1) {
        xx = x2;
        yy = y2;
      } else {
        xx = x1 + param * C;
        yy = y1 + param * D;
      }

      const dx = px - xx;
      const dy = py - yy;
      return Math.sqrt(dx * dx + dy * dy);
    },

    deleteSelectedDrawing() {
      const id = this.drawingsStore.selectedLineId;
      if (id) {
        this.chartManager.removeTrendline(id);
        this.drawingsStore.removeLine(id);
        this.saveDrawings();
      }
      this.contextMenu.visible = false;
    },

    changeDrawingColor() {
      const id = this.drawingsStore.selectedLineId;
      if (!id) return;

      const colors = ['#f5a524', '#2962ff', '#f23645', '#089981', '#9c27b0', '#ff6b6b'];
      const line = this.drawingsStore.lines.find(l => l.id === id);
      const currentIndex = colors.indexOf(line.color);
      const nextColor = colors[(currentIndex + 1) % colors.length];

      this.drawingsStore.updateLine(id, { color: nextColor });
      this.chartManager.removeTrendline(id);
      this.renderDrawing(id);
      this.saveDrawings();
      this.contextMenu.visible = false;
    },

    changeDrawingWidth() {
      const id = this.drawingsStore.selectedLineId;
      if (!id) return;

      const widths = [1, 2, 3, 4];
      const line = this.drawingsStore.lines.find(l => l.id === id);
      const currentIndex = widths.indexOf(line.lineWidth);
      const nextWidth = widths[(currentIndex + 1) % widths.length];

      this.drawingsStore.updateLine(id, { lineWidth: nextWidth });
      this.chartManager.removeTrendline(id);
      this.renderDrawing(id);
      this.saveDrawings();
      this.contextMenu.visible = false;
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
