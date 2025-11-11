import { defineStore } from 'pinia';

export const useCurrentTimeframeStore = defineStore('currentTimeframe', {
  state: () => ({
    label: 'D',
    value: 1440,
  }),
  actions: {
    setCurrentTimeframe(timeframe) {
      this.label = timeframe.label;
      this.value = timeframe.value;
    },
  },
});
