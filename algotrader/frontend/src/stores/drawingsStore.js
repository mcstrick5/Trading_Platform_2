import { defineStore } from 'pinia';

export const useDrawingsStore = defineStore('drawings', {
  state: () => ({
    drawMode: false,
    gridOn: false,
    tool: 'chart', // 'chart' | 'trendline' | 'horizontal' | 'vertical'
    // Lines: { id, type: 'trendline'|'horizontal'|'vertical', a: { time, price }, b: { time, price }, color, lineWidth }
    lines: [],
    selectedLineId: null,
  }),
  getters: {
    allLines: (s) => s.lines,
  },
  actions: {
    toggleDrawMode() {
      this.drawMode = !this.drawMode;
    },
    setDrawMode(val) {
      this.drawMode = !!val;
    },
    setTool(tool) {
      const validTools = ['chart', 'trendline', 'horizontal', 'vertical'];
      this.tool = validTools.includes(tool) ? tool : 'chart';
    },
    toggleGrid() {
      this.gridOn = !this.gridOn;
    },
    setGrid(val) {
      this.gridOn = !!val;
    },
    addLine(a, b, type = 'trendline', options = {}) {
      const id = `${Date.now()}_${Math.random().toString(36).slice(2,7)}`;
      const line = { 
        id, 
        type, 
        a, 
        b,
        color: options.color || '#f5a524',
        lineWidth: options.lineWidth || 2,
      };
      this.lines.push(line);
      return id;
    },
    addLinePixel(aRel, bRel) {
      const id = `${Date.now()}_${Math.random().toString(36).slice(2,7)}`;
      const line = { id, type: 'px', a: aRel, b: bRel };
      this.lines.push(line);
      return id;
    },
    updateLinePixel(id, aRel, bRel) {
      const i = this.lines.findIndex(l => l.id === id);
      if (i >= 0) {
        this.lines[i] = { ...this.lines[i], type: 'px', a: aRel, b: bRel };
      }
    },
    removeLine(id) {
      this.lines = this.lines.filter(l => l.id !== id);
      if (this.selectedLineId === id) {
        this.selectedLineId = null;
      }
    },
    updateLine(id, updates) {
      const line = this.lines.find(l => l.id === id);
      if (line) {
        Object.assign(line, updates);
      }
    },
    selectLine(id) {
      this.selectedLineId = id;
    },
    deselectLine() {
      this.selectedLineId = null;
    },
    clear() {
      this.lines = [];
      this.selectedLineId = null;
    },
    saveFor(symbol, timeframe) {
      try {
        const key = this._key(symbol, timeframe);
        localStorage.setItem(key, JSON.stringify({ lines: this.lines }));
      } catch {}
    },
    loadFor(symbol, timeframe) {
      try {
        const key = this._key(symbol, timeframe);
        const raw = localStorage.getItem(key);
        if (!raw) { this.lines = []; return; }
        const parsed = JSON.parse(raw);
        this.lines = Array.isArray(parsed?.lines) ? parsed.lines : [];
      } catch {
        this.lines = [];
      }
    },
    _key(symbol, timeframe) {
      return `draw:${symbol}:${timeframe}`;
    }
  }
});
