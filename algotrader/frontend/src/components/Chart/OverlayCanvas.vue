<template>
  <canvas ref="canvas" class="overlay-canvas"
          :style="{ pointerEvents: drawMode ? 'auto' : 'none' }"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseLeave"
          @contextmenu.prevent="onContextMenu"/>
</template>

<script>
import { onMounted, onBeforeUnmount } from 'vue';
import { useDrawingsStore } from '@/stores/drawingsStore';

export default {
  name: 'OverlayCanvas',
  props: {
    drawMode: { type: Boolean, default: false },
    symbol: { type: [String, Number], default: null },
    timeframe: { type: [String, Number], default: null },
  },
  data() {
    return {
      drawingsStore: useDrawingsStore(),
      ctx: null,
      dpr: window.devicePixelRatio || 1,
      resizeObserver: null,
      width: 0,
      height: 0,
      isDrawing: false,
      dragId: null,
      dragTarget: null, // 'a' | 'b' | 'line'
      startRel: null,   // { xRel, yRel }
      tempRel: null,
      hoverId: null,
    };
  },
  watch: {
    symbol() { this.syncFromStore(); },
    timeframe() { this.syncFromStore(); },
    // Redraw whenever store changes
    'drawingsStore.lines': {
      handler() { this.paint(); },
      deep: true,
    },
    drawMode() {
      // Reset temp state when toggling
      this.isDrawing = false;
      this.dragId = null;
      this.dragTarget = null;
      this.tempRel = null;
      this.paint();
    },
  },
  mounted() {
    this.initCanvas();
    this.syncFromStore();
    window.addEventListener('keydown', this.onKeyDown);
  },
  beforeUnmount() {
    this.teardown();
    window.removeEventListener('keydown', this.onKeyDown);
  },
  methods: {
    initCanvas() {
      const canvas = this.$refs.canvas;
      this.ctx = canvas.getContext('2d');
      this.resizeObserver = new ResizeObserver(() => this.resizeToParent());
      this.resizeObserver.observe(canvas.parentElement);
      this.resizeToParent();
    },
    teardown() {
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
        this.resizeObserver = null;
      }
    },
    resizeToParent() {
      const canvas = this.$refs.canvas;
      const parent = canvas.parentElement;
      const rect = parent.getBoundingClientRect();
      this.width = rect.width;
      this.height = rect.height;
      const dpr = this.dpr;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = rect.width + 'px';
      canvas.style.height = rect.height + 'px';
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.paint();
    },
    syncFromStore() {
      // Ensure lines are loaded by ChartArea; just repaint
      this.paint();
    },
    clear() {
      this.ctx.clearRect(0, 0, this.width, this.height);
    },
    paint() {
      if (!this.ctx) return;
      this.clear();
      // Draw existing px lines
      for (const line of this.drawingsStore.allLines) {
        if (line.type !== 'px') continue;
        this.drawLine(line, line.id === this.hoverId ? '#ffd166' : '#f5a524');
      }
      // Draw temp line if drawing
      if (this.isDrawing && this.startRel && this.tempRel) {
        this.strokeRel(this.startRel, this.tempRel, '#f5a524', 2, [5, 5]);
      }
    },
    relToPx(pt) {
      return { x: pt.xRel * this.width, y: pt.yRel * this.height };
    },
    pxToRel(x, y) {
      return { xRel: Math.min(1, Math.max(0, x / this.width)), yRel: Math.min(1, Math.max(0, y / this.height)) };
    },
    strokeRel(aRel, bRel, color = '#f5a524', width = 2, dash = null) {
      const a = this.relToPx(aRel);
      const b = this.relToPx(bRel);
      const ctx = this.ctx;
      ctx.save();
      if (dash) ctx.setLineDash(dash);
      ctx.lineWidth = width;
      ctx.strokeStyle = color;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      // endpoints
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(a.x, a.y, 4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(b.x, b.y, 4, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    },
    drawLine(line, color) {
      const aRel = line.a;
      const bRel = line.b;
      this.strokeRel(aRel, bRel, color, 2);
    },
    hitTest(x, y) {
      // returns { id, target: 'a'|'b'|'line' } or null
      const radius = 8; // px
      for (let i = this.drawingsStore.allLines.length - 1; i >= 0; i--) {
        const line = this.drawingsStore.allLines[i];
        if (line.type !== 'px') continue;
        const a = this.relToPx(line.a);
        const b = this.relToPx(line.b);
        // endpoints
        if (Math.hypot(x - a.x, y - a.y) <= radius) return { id: line.id, target: 'a' };
        if (Math.hypot(x - b.x, y - b.y) <= radius) return { id: line.id, target: 'b' };
        // segment distance
        const dist = this.pointToSegmentDistance(x, y, a.x, a.y, b.x, b.y);
        if (dist <= radius) return { id: line.id, target: 'line' };
      }
      return null;
    },
    pointToSegmentDistance(px, py, x1, y1, x2, y2) {
      const dx = x2 - x1, dy = y2 - y1;
      if (dx === 0 && dy === 0) return Math.hypot(px - x1, py - y1);
      const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
      const cx = x1 + t * dx, cy = y1 + t * dy;
      return Math.hypot(px - cx, py - cy);
    },
    onMouseDown(e) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      if (!this.drawMode) {
        // Begin drag existing
        const hit = this.hitTest(x, y);
        if (hit) {
          this.dragId = hit.id;
          this.dragTarget = hit.target;
          e.preventDefault();
        }
        return;
      }
      // Start a new line
      this.isDrawing = true;
      this.startRel = this.pxToRel(x, y);
      this.tempRel = this.startRel;
      this.paint();
    },
    onMouseMove(e) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      this.hoverId = null;

      if (this.isDrawing) {
        this.tempRel = this.pxToRel(x, y);
        this.paint();
        return;
      }

      if (this.dragId) {
        const rel = this.pxToRel(x, y);
        const line = this.drawingsStore.allLines.find(l => l.id === this.dragId);
        if (line && line.type === 'px') {
          if (this.dragTarget === 'a') this.drawingsStore.updateLinePixel(this.dragId, rel, line.b);
          else if (this.dragTarget === 'b') this.drawingsStore.updateLinePixel(this.dragId, line.a, rel);
          else if (this.dragTarget === 'line') {
            // move whole line by delta
            const aPx = this.relToPx(line.a);
            const bPx = this.relToPx(line.b);
            const dx = x - aPx.x;
            const dy = y - aPx.y;
            const a2 = this.pxToRel(aPx.x + dx, aPx.y + dy);
            const b2 = this.pxToRel(bPx.x + dx, bPx.y + dy);
            this.drawingsStore.updateLinePixel(this.dragId, a2, b2);
          }
          this.drawingsStore.saveFor(this.symbol, this.timeframe);
          this.paint();
        }
        return;
      }

      // Hover feedback
      const hit = this.hitTest(x, y);
      this.hoverId = hit?.id || null;
      this.$refs.canvas.style.cursor = hit ? (hit.target === 'line' ? 'move' : 'pointer') : (this.drawMode ? 'crosshair' : 'default');
      this.paint();
    },
    onMouseUp(e) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (this.isDrawing && this.startRel) {
        const endRel = this.pxToRel(x, y);
        const id = this.drawingsStore.addLinePixel(this.startRel, endRel);
        this.drawingsStore.saveFor(this.symbol, this.timeframe);
        this.isDrawing = false;
        this.startRel = null;
        this.tempRel = null;
        this.paint();
        return;
      }

      // End drag
      if (this.dragId) {
        this.dragId = null;
        this.dragTarget = null;
      }
    },
    onMouseLeave() {
      if (this.isDrawing) {
        this.isDrawing = false;
        this.startRel = null;
        this.tempRel = null;
      }
      this.dragId = null;
      this.dragTarget = null;
      this.hoverId = null;
      this.$refs.canvas.style.cursor = 'default';
      this.paint();
    },
    onContextMenu(e) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const hit = this.hitTest(x, y);
      if (hit) {
        this.drawingsStore.removeLine(hit.id);
        this.drawingsStore.saveFor(this.symbol, this.timeframe);
        this.paint();
      }
    },
    onKeyDown(e) {
      if (e.key === 'Escape') {
        this.isDrawing = false;
        this.startRel = null;
        this.tempRel = null;
        this.drawingsStore.setDrawMode(false);
        this.$refs.canvas.style.cursor = 'default';
        this.paint();
      }
    },
  },
};
</script>

<style scoped>
.overlay-canvas {
  position: absolute;
  inset: 0;
  z-index: 500; /* above chart but below indicator UI panels */
  pointer-events: none;
}
</style>
