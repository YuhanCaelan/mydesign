<script setup lang="ts">
import type{ViewMode}from'../../utils/view'
defineProps<{modelValue:ViewMode;cardLabel?:string;listLabel?:string}>()
const emit=defineEmits<{(event:'update:modelValue',value:ViewMode):void}>()
</script>
<template>
  <div class="view-switch" role="group" aria-label="视图切换">
    <button type="button" :class="{active:modelValue==='cards'}" :aria-pressed="modelValue==='cards'" @click="emit('update:modelValue','cards')">{{cardLabel||'卡片'}}</button>
    <button type="button" :class="{active:modelValue==='list'}" :aria-pressed="modelValue==='list'" @click="emit('update:modelValue','list')">{{listLabel||'列表'}}</button>
  </div>
</template>
