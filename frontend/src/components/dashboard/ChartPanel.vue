<script setup lang="ts">
defineProps<{title:string;description?:string;empty?:boolean}>()
</script>
<template><section class="chart-panel"><header><div><h2>{{title}}</h2><p v-if="description">{{description}}</p></div><slot name="actions"/></header><div class="chart-panel-body"><el-empty v-if="empty" :image-size="56" description="当前范围暂无数据"/><slot v-else/></div><footer v-if="$slots.footer"><slot name="footer"/></footer></section></template>
