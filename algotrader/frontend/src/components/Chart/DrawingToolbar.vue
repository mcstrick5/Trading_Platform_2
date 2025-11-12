<template>
  <div class="drawing-toolbar">
    <n-button-group size="small">
      <n-button 
        :type="drawingsStore.tool === 'chart' && !drawingsStore.drawMode ? 'primary' : 'default'"
        @click="selectTool('chart')"
        title="Chart mode (no drawing)"
      >
        <template #icon>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        </template>
      </n-button>

      <n-button 
        :type="drawingsStore.tool === 'trendline' && drawingsStore.drawMode ? 'primary' : 'default'"
        @click="selectTool('trendline')"
        title="Draw trendline"
      >
        <template #icon>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="19" x2="19" y2="5"></line>
          </svg>
        </template>
      </n-button>

      <n-button 
        :type="drawingsStore.tool === 'horizontal' && drawingsStore.drawMode ? 'primary' : 'default'"
        @click="selectTool('horizontal')"
        title="Draw horizontal line"
      >
        <template #icon>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </template>
      </n-button>

      <n-button 
        @click="clearAllDrawings"
        title="Clear all drawings"
        :disabled="drawingsStore.lines.length === 0"
      >
        <template #icon>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </template>
      </n-button>

      <n-button 
        :type="drawingsStore.gridOn ? 'primary' : 'default'"
        @click="toggleGrid"
        title="Toggle grid"
      >
        <template #icon>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
        </template>
      </n-button>
    </n-button-group>

    <span v-if="drawingsStore.drawMode" class="draw-mode-indicator">
      Drawing: {{ drawingsStore.tool }}
    </span>
  </div>
</template>

<script>
import { useDrawingsStore } from '@/stores/drawingsStore';
import { NButton, NButtonGroup } from 'naive-ui';

export default {
  name: 'DrawingToolbar',
  
  components: {
    NButton,
    NButtonGroup,
  },

  data() {
    return {
      drawingsStore: useDrawingsStore(),
    };
  },

  methods: {
    selectTool(tool) {
      if (tool === 'chart') {
        this.drawingsStore.setDrawMode(false);
        this.drawingsStore.setTool('chart');
      } else {
        this.drawingsStore.setDrawMode(true);
        this.drawingsStore.setTool(tool);
      }
    },

    clearAllDrawings() {
      if (confirm('Clear all drawings on this chart?')) {
        this.$emit('clear-drawings');
      }
    },

    toggleGrid() {
      this.drawingsStore.toggleGrid();
    },
  },
};
</script>

<style scoped>
.drawing-toolbar {
  position: absolute;
  top: 80px; /* Position under OHLC legend */
  left: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 10;
}

.draw-mode-indicator {
  background: rgba(41, 98, 255, 0.1);
  border: 1px solid #2962ff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #2962ff;
  font-weight: 500;
}
</style>
