import { defineStore } from 'pinia';

export const useDrawingsStore = defineStore('drawings', {
  state: () => ({
    drawMode: false,
    gridOn: false,
    tool: 'chart', // 'chart' | 'freehand'
    // Lines can be time/price or pixel-relative
    // time/price form: { id, a: { time, price }, b: { time, price } }
    // pixel form: { id, type: 'px', a: { xRel, yRel }, b: { xRel, yRel } }
    lines: [],
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
      this.tool = tool === 'freehand' ? 'freehand' : 'chart';
    },
    toggleGrid() {
      this.gridOn = !this.gridOn;
    },
    setGrid(val) {
      this.gridOn = !!val;
    },
    addLine(a, b) {
      const id = `${Date.now()}_${Math.random().toString(36).slice(2,7)}`;
      const line = { id, a, b };
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
    },
    clear() {
      this.lines = [];
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
