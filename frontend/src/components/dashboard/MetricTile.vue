<script setup lang="ts">
import{computed}from'vue'
import type{DashboardKpi}from'../../types/dashboard'
const props=defineProps<{item:DashboardKpi}>()
const changeText=computed(()=>props.item.change===null?'暂无同期数据':`${props.item.change>0?'+':''}${props.item.change}%`)
</script>
<template><article class="clinical-metric" :data-tone="item.tone"><div class="metric-label"><span>{{item.label}}</span><i/></div><div class="metric-value"><strong>{{item.value}}</strong><small>{{item.unit}}</small></div><div class="metric-change" :class="{up:(item.change||0)>0,down:(item.change||0)<0}"><span>{{changeText}}</span><em v-if="item.change!==null">较上一周期</em></div></article></template>
