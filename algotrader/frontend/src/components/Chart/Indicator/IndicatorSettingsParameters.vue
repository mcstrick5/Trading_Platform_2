<template>
  <n-scrollbar style="height: 300px">
    <table>
      <tr
        v-for="(parameter, key) in indicatorParameters"
        :key="key"
        class="indicator-parameter"
      >
        <td>
          <p>
            {{ replaceUnderscoreWithSpace(key) }}
          </p>
        </td>

        <td>
          <n-select
            v-if="isStringWithOptions(parameter)"
            v-model:value="parameter.value"
            @update:value="onParameterUpdate"
            :name="`param-${key}`"
            :id="`param-${key}`"
            :options="parameter.options.map((opt) => ({ label: opt, value: opt }))"
          />

          <n-input
            v-else-if="isStringWithoutOptions(parameter)"
            v-model:value="parameter.value"
            @update:value="onParameterUpdate"
            :name="`param-${key}`"
            :id="`param-${key}`"
          />

          <n-input-number
            v-else-if="isNumber(parameter)"
            v-model:value="parameter.value"
            :min="parameter.min"
            :max="parameter.max"
            :step="parameter.step"
            @update:value="onParameterUpdate"
            :name="`param-${key}`"
            :id="`param-${key}`"
          />
        </td>
      </tr>
    </table>
  </n-scrollbar>
</template>

<script>
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

import { NScrollbar, NInput, NInputNumber, NSelect } from "naive-ui";

export default {
  name: "IndicatorSettingsParameters",

  components: {
    NScrollbar,
    NInput,
    NInputNumber,
    NSelect,
  },

  props: {
    indicator: {
      type: Object,
      required: true,
    },
  },

  data() {
    return {
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      updateDelay: 200,
      updateTimeout: null,
    };
  },

  computed: {
    symbolID() {
      return this.currentMarketStore.symbol_id;
    },

    timeframe() {
      return this.currentTimeframeStore.value;
    },

    indicatorId() {
      return this.indicator.id;
    },

    indicatorInfo() {
      return this.indicator?.info;
    },

    indicatorParameters() {
      return this.indicator?.parameters;
    },
  },

  methods: {
    replaceUnderscoreWithSpace(str) {
      return str.replace(/_/g, " ");
    },

    isStringWithOptions(parameter) {
      return parameter.type === "string" && parameter.options !== null;
    },
    isStringWithoutOptions(parameter) {
      return parameter.type === "string" && parameter.options === null;
    },
    isNumber(parameter) {
      return parameter.type === "int" || parameter.type === "float";
    },

    onParameterUpdate() {
      if (this.updateTimeout) {
        clearTimeout(this.updateTimeout);
      }

      this.updateTimeout = setTimeout(() => {
        this.updateTimeout = null;
        this.handleParameterUpdate();
      }, this.updateDelay);
    },

    async handleParameterUpdate() {
      const customParameters = this.buildCustomParameters();
      this.updateIndicatorStoreParameters(this.indicatorId, customParameters);

      // CSV mode: fetch REST endpoint and update data
      try {
        const nameCode = this.mapIndicatorNameToCode(this.indicatorInfo?.name);
        if (!nameCode) return;
        const paramsStr = this.toParamsString(customParameters);
        const url = `/api/csv-indicator/${encodeURIComponent(this.symbolID)}?timeframe=${encodeURIComponent(this.timeframe)}&name=${encodeURIComponent(nameCode)}${paramsStr ? `&params=${encodeURIComponent(paramsStr)}` : ''}`;
        const resp = await fetch(url);
        const series = await resp.json();
        this.indicatorsStore.updateIndicatorData(this.indicatorId, series);
      } catch (e) {
        console.error('Failed to update indicator with new parameters:', e);
      }
    },

    updateIndicatorStoreParameters(indicatorId, newParameters) {
      this.indicatorsStore.updateIndicatorParameters(indicatorId, newParameters);
    },

    // Helpers for CSV mode
    mapIndicatorNameToCode(name) {
      if (!name) return null;
      if (name === 'Simple Moving Average') return 'SMA';
      if (name === 'Relative Strength Index') return 'RSI';
      if (name === 'Bollinger Bands') return 'BBANDS';
      if (name === 'Moving Average Convergence Divergence') return 'MACD';
      return null;
    },
    toParamsString(customParameters) {
      // customParameters structure: { key: { value: any } }
      const parts = [];
      for (const [k, obj] of Object.entries(customParameters)) {
        const v = obj?.value;
        if (v === undefined || v === null || v === '') continue;
        parts.push(`${k}=${v}`);
      }
      return parts.join(',');
    },

    buildCustomParameters() {
      const customParameters = {};

      for (const [key, param] of Object.entries(this.indicatorParameters)) {
        customParameters[key] = { value: param.value };
      }
      return customParameters;
    },
  },
};
</script>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
}

.indicator-parameter td,
.output-style-option td {
  padding: 5px 15px;
  border-bottom: 1px solid #333;
}

.indicator-parameter p {
  margin: 0;
  color: #ccc;
  text-transform: capitalize;
}
</style>
