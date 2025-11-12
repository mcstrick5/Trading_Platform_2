<template>
  <div 
    v-if="visible" 
    class="drawing-context-menu"
    :style="{ left: x + 'px', top: y + 'px' }"
  >
    <div class="menu-item" @click="$emit('delete')">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="3 6 5 6 21 6"></polyline>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
      </svg>
      Delete
    </div>
    <div class="menu-item" @click="$emit('change-color')">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
      </svg>
      Change Color
    </div>
    <div class="menu-item" @click="$emit('change-width')">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12" stroke-width="3"></line>
      </svg>
      Change Width
    </div>
  </div>
</template>

<script>
export default {
  name: 'DrawingContextMenu',
  
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    x: {
      type: Number,
      default: 0,
    },
    y: {
      type: Number,
      default: 0,
    },
  },
};
</script>

<style scoped>
.drawing-context-menu {
  position: fixed;
  background: #1e1e1e;
  border: 1px solid #3a3a3a;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10000;
  min-width: 150px;
  padding: 4px 0;
}

.menu-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #d1d4dc;
  font-size: 13px;
  transition: background 0.15s;
}

.menu-item:hover {
  background: #2a2a2a;
}

.menu-item svg {
  flex-shrink: 0;
}
</style>
