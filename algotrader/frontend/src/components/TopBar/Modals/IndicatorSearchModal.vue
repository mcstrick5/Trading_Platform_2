<template>
  <base-modal :modalId="'indicatorSearch'" :title="'Indicator'">
    <div>
      <span id="search-bar-wrapper">
        <n-input
          v-model:value="indicatorInput"
          id="indicator-input"
          autocomplete="off"
          placeholder="Indicator"
          round
          clearable
        >
          <template #prefix>
            <n-icon>
              <SearchOutline />
            </n-icon>
          </template>
        </n-input>
        <hr class="separator" />
      </span>

      <n-scrollbar style="height: 300px">
        <table>
          <tbody>
            <template v-for="(indicatorName, key) in filteredIndicators" :key="key">
              <tr @click="onApplyIndicator(indicatorName)">
                <td>
                  {{ indicatorName }}
                </td>
              </tr>

              <hr class="row-separator" />
            </template>
          </tbody>
        </table>
      </n-scrollbar>
    </div>
  </base-modal>
</template>

<script>
import BaseModal from "@/components/Common/BaseModal.vue";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";

import { NScrollbar, NInput, NIcon } from "naive-ui";
import { SearchOutline } from "@/icons";

export default {
  name: "IndicatorSearchModal",

  components: {
    BaseModal,
    NScrollbar,
    NInput,
    NIcon,
    SearchOutline,
  },

  data() {
    return {
      indicatorInput: "",
      // CSV mode: populate locally
      indicators: [
        'Volume',
        'Simple Moving Average',
        'Relative Strength Index',
        'Bollinger Bands',
        'Moving Average Convergence Divergence',
      ],
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      indicatorsStore: useIndicatorsStore(),
    };
  },

  computed: {
    filteredIndicators() {
      return this.indicators
        .filter((indicator) =>
          indicator.toUpperCase().includes(this.indicatorInput.toUpperCase()),
        )
        .sort((a, b) => a.localeCompare(b));
    },

    symbolID() {
      return this.currentMarketStore.symbol_id;
    },

    timeframe() {
      return this.currentTimeframeStore.value;
    },
  },

  mounted() {
    // Keep websocket hook for backtester mode, but CSV mode already has local list
    this.$wss.on("message", this.wssMessageHandler);
    this.$wss.send("Backtester", "list-indicators");
  },

  beforeUnmount() {
    this.$wss.off("message", this.wssMessageHandler);
  },

  methods: {
    getInfoByName(name) {
      // Minimal info schema to drive rendering
      if (name === 'Volume') {
        return {
          code: 'VOL',
          name,
          overlay: false,
          outputs: {
            volume: { type: 'histogram', plotOptions: { priceFormat: { minMove: 1 } } },
          },
          parameters: {},
        }
      }
      if (name === 'Simple Moving Average') {
        return {
          code: 'SMA',
          name,
          overlay: true,
          outputs: {
            sma: { type: 'line', plotOptions: { lineWidth: 2, color: '#FCFC4E' } },
          },
          parameters: {
            window: { type: 'int', default: 20, min: 1, max: 1e6, step: 1 },
          },
        }
      }
      if (name === 'Relative Strength Index') {
        return {
          code: 'RSI',
          name,
          overlay: false,
          outputs: {
            rsi: { type: 'line', plotOptions: { lineWidth: 2, color: '#7E57C2' } },
          },
          parameters: {
            length: { type: 'int', default: 14, min: 1, max: 1e6, step: 1 },
          },
        }
      }
      if (name === 'Bollinger Bands') {
        return {
          code: 'BBANDS',
          name,
          overlay: true,
          outputs: {
            lower: { type: 'line', plotOptions: { lineWidth: 2, color: '#089981' } },
            mid: { type: 'line', plotOptions: { lineWidth: 2, color: '#2962ff' } },
            upper: { type: 'line', plotOptions: { lineWidth: 2, color: '#f23645' } },
          },
          parameters: {
            length: { type: 'int', default: 20, min: 1, max: 1e6, step: 1 },
            std: { type: 'float', default: 2, min: 0, max: 1e6, step: 0.1 },
          },
        }
      }
      if (name === 'Moving Average Convergence Divergence') {
        return {
          code: 'MACD',
          name,
          overlay: false,
          outputs: {
            histogram: { type: 'histogram', plotOptions: { color: '#089981', priceFormat: { minMove: 0.00001 } } },
            macd: { type: 'line', plotOptions: { lineWidth: 2, color: '#2962ff', priceFormat: { minMove: 0.00001 } } },
            signal: { type: 'line', plotOptions: { lineWidth: 2, color: '#f23645', priceFormat: { minMove: 0.00001 } } },
          },
          parameters: {
            fast: { type: 'int', default: 12, min: 1, max: 1e6, step: 1 },
            slow: { type: 'int', default: 26, min: 1, max: 1e6, step: 1 },
            signal: { type: 'int', default: 9, min: 1, max: 1e6, step: 1 },
          },
        }
      }
      return null;
    },
    wssMessageHandler(data) {
      const message = this.parseMessage(data);
      this.handleMessage(message);
    },

    parseMessage(data) {
      try {
        return JSON.parse(data);
      } catch (error) {
        console.error("Failed to parse message:", error);
      }
    },

    handleMessage(message) {
      if (message.type === "list-indicators-response")
        this.handleListIndicatorsResponse(message.data);
    },

    handleListIndicatorsResponse(indicators) {
      this.indicators = indicators;
    },

    async onApplyIndicator(indicatorName) {
      // CSV mode: fetch REST and add to store
      const info = this.getInfoByName(indicatorName);
      if (!info) return;

      const symbol = this.symbolID; // in CSV mode symbol_id is the symbol string
      const tf = this.timeframe; // minutes or code; backend normalizes
      let nameParam = '';
      if (indicatorName === 'Volume') nameParam = 'VOL';
      if (indicatorName === 'Simple Moving Average') nameParam = 'SMA';
      else if (indicatorName === 'Relative Strength Index') nameParam = 'RSI';
      else if (indicatorName === 'Bollinger Bands') nameParam = 'BBANDS';
      else if (indicatorName === 'Moving Average Convergence Divergence') nameParam = 'MACD';

      try {
        const url = `/api/csv-indicator/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(tf)}&name=${encodeURIComponent(nameParam)}`;
        const resp = await fetch(url);
        const series = await resp.json();
        // Add to store (no auto-save; persistence handled on context switch/unload)
        this.indicatorsStore.addIndicator(info, series, {});
      } catch (e) {
        console.error('Failed to load indicator:', e);
      }
    },

    // No auto-save here; ChartArea saves on context switch and beforeunload
  },
};
</script>

<style scoped>
#search-bar-wrapper {
  position: sticky;
  top: -10px;
}

#indicator-input {
  width: calc(100% - 30px);
  margin: 8px 15px;
}

table {
  width: 100%;
}

tr {
  padding: 5px 15px;
  width: calc(100% - 30px);
  display: flex;
  cursor: pointer;
}

td {
  line-height: 20px;
  padding: 10px 0;
}

.row-separator {
  border: none;
  height: 1px;
  background-color: #a0a0a029;
  margin: 0;
}

tr:hover {
  background-color: #36363661;
}
</style>
