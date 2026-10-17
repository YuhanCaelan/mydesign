<script setup lang="ts">
import{computed}from'vue'
import VChart from'vue-echarts'
import{use}from'echarts/core'
import{CanvasRenderer}from'echarts/renderers'
import{PieChart}from'echarts/charts'
import{TooltipComponent}from'echarts/components'
import{billingCategoryLabel}from'../../utils/billing'
import{tooltip}from'../../utils/charts'
import type{NamedValue}from'../../types/dashboard'

use([CanvasRenderer,PieChart,TooltipComponent])

const props=defineProps<{items:NamedValue[]}>()
const palette=['#006241','#00754a','#1c6e8c','#00a88f','#c98a2e','#8a5a12','#55bba6','#715b9d']
const reducedMotion=typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const rows=computed(()=>{
  const values=props.items.map(item=>({label:billingCategoryLabel(String(item.name)),value:Number(item.value)||0})).filter(item=>item.value>0).sort((a,b)=>b.value-a.value)
  const total=values.reduce((sum,item)=>sum+item.value,0)
  return{total,values:values.map((item,index)=>({...item,index,percent:total?item.value*100/total:0}))}
})
const pieOption=computed(()=>({
  animation:!reducedMotion,
  color:palette,
  tooltip:{...tooltip,trigger:'item',formatter:(params:any)=>`${params.name}<br/>¥${Number(params.value).toFixed(2)}（${Number(params.percent).toFixed(1)}%）`},
  series:[{type:'pie',radius:'72%',center:['50%','50%'],roseType:false,avoidLabelOverlap:true,label:{show:false},labelLine:{show:false},itemStyle:{borderColor:'#fff',borderWidth:2,borderRadius:2},emphasis:{scale:true,scaleSize:6,itemStyle:{shadowBlur:14,shadowColor:'rgba(16,42,51,.2)'}},data:rows.value.values.map(row=>({name:row.label,value:row.value}))}]
}))
function money(value:number){return`¥${value.toFixed(2)}`}
function percentText(value:number){return value>0&&value<0.1?'<0.1%':`${value.toFixed(1)}%`}
</script>

<template>
  <div v-if="rows.total" class="revenue-pie">
    <v-chart class="revenue-pie-chart" :option="pieOption" autoresize/>
    <ul class="revenue-pie-legend" aria-label="收入构成文字列表">
      <li v-for="row in rows.values" :key="row.label" tabindex="0" :aria-label="`${row.label} ${money(row.value)}，占 ${percentText(row.percent)}`">
        <i :style="{background:palette[row.index%palette.length]}" aria-hidden="true"/>
        <span>{{row.label}}</span>
        <b>{{money(row.value)}}</b>
        <em>{{percentText(row.percent)}}</em>
      </li>
    </ul>
  </div>
  <div v-else class="matrix-empty" role="status"><b>暂无已结算收入</b><p>当前周期没有正金额的已缴费账单。</p></div>
</template>
