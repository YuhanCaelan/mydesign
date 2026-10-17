<script setup lang="ts">
import{computed}from'vue'
import{statusItems,type StatusDomain}from'../../utils/status'
const props=defineProps<{domain:StatusDomain;title?:string}>()
const items=computed(()=>statusItems(props.domain))
</script>
<template>
  <div class="status-legend" :aria-label="title||'状态图例'">
    <span v-if="title" class="status-legend-title">{{title}}</span>
    <span v-for="item in items" :key="item.key" class="status-legend-item">
      <i :data-tone="item.tone" aria-hidden="true"/>{{item.label}}
    </span>
  </div>
</template>
