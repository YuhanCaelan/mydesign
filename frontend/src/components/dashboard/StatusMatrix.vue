<script setup lang="ts">
import{computed}from'vue'
import{statusInfo}from'../../utils/status'
import type{NamedValue}from'../../types/dashboard'

const props=defineProps<{items:NamedValue[]}>()
const rows=computed(()=>{
  const values=props.items.map(item=>({name:String(item.name),value:Number(item.value)||0}))
  const total=values.reduce((sum,item)=>sum+item.value,0)
  return{total,values:values.map(item=>({...item,info:statusInfo('appointment',item.name),percent:total?item.value*100/total:0}))}
})
function percentText(value:number){return value>0&&value<0.1?'<0.1%':`${value.toFixed(1)}%`}
</script>

<template>
  <div v-if="rows.total" class="status-matrix" role="list" aria-label="诊疗状态进度矩阵">
    <div v-for="row in rows.values" :key="row.name" class="status-matrix-row" role="listitem" :aria-label="`${row.info.label} ${row.value} 人，占 ${percentText(row.percent)}`">
      <span class="status-matrix-label"><i :data-tone="row.info.tone" aria-hidden="true"/>{{row.info.label}}</span>
      <b class="status-matrix-value">{{row.value}}<small>人</small></b>
      <span class="status-matrix-percent">{{percentText(row.percent)}}</span>
      <span class="status-matrix-track" aria-hidden="true"><i :data-tone="row.info.tone" :style="{width:`${row.percent}%`}"/></span>
    </div>
  </div>
  <div v-else class="matrix-empty" role="status"><b>当前周期暂无预约数据</b><p>切换统计周期或等待新的预约后，状态分布会显示在这里。</p></div>
</template>
