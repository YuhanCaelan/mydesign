<script setup lang="ts">
defineProps<{message:string}>()
defineEmits<{(event:'retry'):void}>()
</script>
<template>
  <div class="list-error" role="alert">
    <div><b>数据加载失败</b><p>{{message}}</p></div>
    <el-button type="primary" plain @click="$emit('retry')">重试</el-button>
  </div>
</template>
