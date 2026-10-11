<script setup lang="ts">
import{computed,onMounted,ref}from'vue'
import VChart from'vue-echarts'
import{use}from'echarts/core'
import{CanvasRenderer}from'echarts/renderers'
import{BarChart,LineChart,PieChart}from'echarts/charts'
import{GridComponent,LegendComponent,TooltipComponent}from'echarts/components'
import{Download,Refresh}from'@element-plus/icons-vue'
import ChartPanel from'../../components/dashboard/ChartPanel.vue'
import MetricTile from'../../components/dashboard/MetricTile.vue'
import{getDashboard}from'../../services/statistics'
import type{DashboardData,DashboardRange}from'../../types/dashboard'
import{categoryAxis,chartColors,tooltip,valueAxis}from'../../utils/charts'

use([CanvasRenderer,BarChart,LineChart,PieChart,GridComponent,LegendComponent,TooltipComponent])
const loading=ref(true),range=ref<DashboardRange>('30d'),data=ref<DashboardData|null>(null)
const trend=computed(()=>({color:[chartColors[0],chartColors[1],chartColors[2]],tooltip:{...tooltip,trigger:'axis'},legend:{top:0,right:0,itemWidth:16,itemHeight:3},grid:{left:48,right:42,top:50,bottom:30},xAxis:{...categoryAxis,boundaryGap:false,data:(data.value?.timeseries||[]).map(x=>x.date.slice(5))},yAxis:[valueAxis,{...valueAxis,minInterval:0,axisLabel:{formatter:'¥{value}',color:'#587078'}}],series:[{name:'预约量',type:'line',smooth:true,data:(data.value?.timeseries||[]).map(x=>x.visits),lineStyle:{width:2.5},areaStyle:{color:'rgba(28,110,140,.07)'}},{name:'完成诊疗',type:'line',smooth:true,data:(data.value?.timeseries||[]).map(x=>x.completed),lineStyle:{width:2.5}},{name:'结算收入',type:'bar',yAxisIndex:1,barMaxWidth:10,data:(data.value?.timeseries||[]).map(x=>x.revenue),itemStyle:{borderRadius:[2,2,0,0]}}]}))
function rankingOption(items:any[]=[],color=chartColors[0]){return{tooltip:{...tooltip,trigger:'axis'},grid:{left:88,right:28,top:12,bottom:24},xAxis:valueAxis,yAxis:{...categoryAxis,data:[...items].reverse().map(x=>x.name)},series:[{type:'bar',barWidth:11,data:[...items].reverse().map(x=>x.value),itemStyle:{color,borderRadius:[0,3,3,0]}}]}}
const department=computed(()=>rankingOption(data.value?.department_workload,chartColors[0]))
const doctor=computed(()=>rankingOption(data.value?.doctor_workload,chartColors[1]))
const inpatient=computed(()=>({color:[chartColors[1],chartColors[2],chartColors[4]],tooltip:{...tooltip,trigger:'item'},legend:{bottom:0,itemWidth:8,itemHeight:8},series:[{type:'pie',radius:['50%','72%'],center:['50%','43%'],label:{show:false},data:(data.value?.inpatient_status||[]).filter(x=>Number(x.value))}]}))
async function load(){loading.value=true;try{data.value=await getDashboard(range.value)}finally{loading.value=false}}
function download(){
  if(!data.value)return
  const rows=[['日期','预约量','完成诊疗','结算收入'],...data.value.timeseries.map(x=>[x.date,x.visits,x.completed,x.revenue])]
  const blob=new Blob(['\ufeff'+rows.map(row=>row.join(',')).join('\n')],{type:'text/csv;charset=utf-8'}),link=document.createElement('a')
  link.href=URL.createObjectURL(blob);link.download=`医疗运营数据-${data.value.meta.start}-${data.value.meta.end}.csv`;link.click();URL.revokeObjectURL(link.href)
}
onMounted(load)
</script>

<template><section v-loading="loading" class="analytics-page">
  <header class="page-heading analytics-heading"><div><div class="live-label"><i/>运营分析</div><h1>医疗数据驾驶舱</h1><p>观察诊疗效率、科室负荷、医师工作量与费用结算趋势</p></div><div class="intro-actions"><el-segmented v-model="range" :options="[{label:'7 天',value:'7d'},{label:'30 天',value:'30d'},{label:'90 天',value:'90d'}]" @change="load"/><el-button :icon="Download" @click="download">导出 CSV</el-button><el-button :icon="Refresh" @click="load">刷新</el-button></div></header>
  <div class="clinical-metrics"><MetricTile v-for="item in data?.kpis||[]" :key="item.key" :item="item"/></div>
  <div class="analytics-grid">
    <ChartPanel class="span-12" title="业务与收入趋势" :description="`${data?.meta.start||''} 至 ${data?.meta.end||''}，左轴为人次，右轴为元`" :empty="!data?.timeseries?.some(x=>x.visits||x.completed||x.revenue)"><v-chart class="chart chart-wide" :option="trend" autoresize/></ChartPanel>
    <ChartPanel class="span-5" title="科室业务负荷" description="按周期预约量排序" :empty="!data?.department_workload?.length"><v-chart class="chart" :option="department" autoresize/></ChartPanel>
    <ChartPanel class="span-4" title="医师完成诊疗量" description="按已完成诊疗次数排序" :empty="!data?.doctor_workload?.length"><v-chart class="chart" :option="doctor" autoresize/></ChartPanel>
    <ChartPanel class="span-3" title="住院状态构成" description="当前全部住院记录" :empty="!data?.inpatient_status?.some(x=>Number(x.value))"><v-chart class="chart" :option="inpatient" autoresize/></ChartPanel>
  </div>
  <section class="data-footnote"><span>数据口径</span><p>预约按排班日期统计，收入仅统计已支付账单；页面更新时间 {{data?.meta.generated_at?new Date(data.meta.generated_at).toLocaleString('zh-CN'):'—'}}。</p></section>
</section></template>
