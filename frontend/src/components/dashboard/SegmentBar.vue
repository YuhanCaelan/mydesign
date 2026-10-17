<script setup lang="ts">
import{computed}from'vue'
import{statusInfo}from'../../utils/status'
import type{NamedValue}from'../../types/dashboard'

const props=defineProps<{items:NamedValue[];domain?:'inpatient'|'appointment'}>()
const rows=computed(()=>{
  const values=props.items.map(item=>({name:String(item.name),value:Number(item.value)||0})).map(item=>({...item,info:statusInfo(props.domain||'inpatient',item.name)}))
  const total=values.reduce((sum,item)=>sum+item.value,0)
  return{total,values:values.map(item=>({...item,percent:total?item.value*100/total:0}))}
})
function percentText(value:number){return value>0&&value<0.1?'<0.1%':`${value.toFixed(1)}%`}
</script>

<template>
  <div v-if="rows.total" class="segment-chart">
    <div class="segment-bar" role="img" :aria-label="rows.values.map(row=>`${row.info.label} ${row.value} 人`).join('，')">
      <span v-for="row in rows.values.filter(item=>item.value>0)" :key="row.name" :data-tone="row.info.tone" :style="{width:`${row.percent}%`}" :title="`${row.info.label} ${row.value} 人（${percentText(row.percent)}）`"/>
    </div>
    <div class="segment-legend">
      <div v-for="row in rows.values" :key="row.name" :aria-label="`${row.info.label} ${row.value} 人，占 ${percentText(row.percent)}`">
        <span class="segment-legend-label"><i :data-tone="row.info.tone" aria-hidden="true"/>{{row.info.label}}</span>
        <b>{{row.value}}<small>人</small></b>
        <em>{{percentText(row.percent)}}</em>
      </div>
    </div>
  </div>
  <div v-else class="matrix-empty" role="status"><b>当前没有住院记录</b><p>新的住院申请或入院记录会显示在这里。</p></div>
</template>
