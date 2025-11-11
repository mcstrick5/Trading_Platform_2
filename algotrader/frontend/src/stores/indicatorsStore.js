import { defineStore } from "pinia";
import { wsService } from "../utils/websocketService";

export const useIndicatorsStore = defineStore('indicators', {
  state: () => ({
    indicators: new Map(),
    paneCount: 1,
  }),

  getters: {
    all: (state) => Array.from(state.indicators.values()),
    getById: (state) => (id) => state.indicators.get(id),
    exists: (state) => (id) => state.indicators.has(id),
  },

  actions: {
    requestAllIndicators(symbolID, timeframe) {
      const currentMarketData = {
        symbol_id: symbolID,
        timeframe: timeframe,
      };

      for (const indicator of this.all) {
        const indicatorData = {
          id: indicator.id,
          name: indicator.info.name,
          ...currentMarketData,
        };

        this.requestIndicator(indicatorData);
      }
    },

    requestIndicator(data) {
      wsService.send("Backtester", "get-indicator", data);
    },

    addIndicator(info, data, parameters = {}) {
      const id = String(Date.now());
      // Start with provided parameters; only fill missing keys with defaults
      const finalParameters = { ...parameters };
      for (const [key, paramInfo] of Object.entries(info.parameters || {})) {
        if (!(key in finalParameters) || finalParameters[key]?.value === undefined) {
          finalParameters[key] = { ...paramInfo, value: paramInfo.default };
        } else {
          // Ensure other metadata from paramInfo exists while keeping provided value
          finalParameters[key] = { ...paramInfo, value: finalParameters[key].value };
        }
      }

      const indicator = {
        id,
        info: { ...info },
        paneIndex: info.overlay ? 0 : this.paneCount++,
        paneHtmlElement: null,
        data: [...data],
        parameters: finalParameters,
        styles: this.createStyles(info.outputs || {}),
        visible: true,
      };
      this.indicators.set(id, indicator);

      return id;
    },

    updateIndicatorData(id, newData) {
      const indicator = this.indicators.get(id);
      if (!indicator) return false;
      indicator.data = [...newData];
      return true;
    },

    updateIndicatorParameters(id, newParameters) {
      const indicator = this.indicators.get(id);

      for (const [key, { value: paramValue }] of Object.entries(newParameters)) {
        indicator.parameters[key].value = paramValue;
      }

      return indicator.parameters;
    },

    resetIndicatorParameters(id) {
      const indicator = this.indicators.get(id);
      if (!indicator) return false;
      const defaults = {};
      for (const [key, paramInfo] of Object.entries(indicator.info.parameters || {})) {
        defaults[key] = { value: paramInfo.default };
      }
      indicator.parameters = this.updateIndicatorParameters(id, defaults);
      return true;
    },

    setVisibility(id, visible) {
      const indicator = this.indicators.get(id);
      if (!indicator) return false;
      indicator.visible = !!visible;
      return true;
    },

    // updateIndicatorStyles(id, outputKey, newStyles) {
    //   const indicator = this.indicators.get(id);
    //   if (!indicator) {
    //     console.warn(`Indicator ${id} not found`);
    //     return false;
    //   }

    //   if (!indicator.styles[outputKey]) {
    //     indicator.styles[outputKey] = {};
    //   }

    //   indicator.styles[outputKey] = {
    //     ...indicator.styles[outputKey],
    //     ...newStyles
    //   };

    //   return true;
    // },

    createStyles(outputs) {
      const styles = {};

      for (const outputKey in outputs) {
        if (outputKey !== 'timestamp') {
          styles[outputKey] = {
            ...outputs[outputKey].plotOptions || {},
          };
        }
      }
      return styles;
    },

    updateIndicatorPaneElement(id, paneHtmlElement) {
      const indicator = this.indicators.get(id);
      indicator.paneHtmlElement = paneHtmlElement;
    },

    removeIndicator(id) {
      const indicator = this.indicators.get(id);
      const paneIndex = indicator.paneIndex;
      if (paneIndex > 0) {
        this.updateIndicatorsPaneIndex(paneIndex);
      }

      this.indicators.delete(id);
    },

    updateIndicatorsPaneIndex(changedPaneIndex) {
      for (const [_, indicator] of this.indicators.entries()) {
        if (indicator.paneIndex > changedPaneIndex) {
          indicator.paneIndex--;
          indicator.paneHtmlElement = null;
        }
      }

      this.paneCount = Math.max(1, this.paneCount - 1);
    },

    clear() {
      this.indicators.clear();
      this.paneCount = 1;
    },
  },
});
