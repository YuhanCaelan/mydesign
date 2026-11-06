<script setup lang="ts">
import{computed,onMounted,ref}from'vue';import VChart from'vue-echarts';import{use}from'echarts/core';import{CanvasRenderer}from'echarts/renderers';import{PieChart}from'echarts/charts';import{TooltipComponent,LegendComponent}from'echarts/components';import http from'../api/http'
use([CanvasRenderer,PieChart,TooltipComponent,LegendComponent]);const data=ref<any>({cards:{},appointment_status:[]}),loading=ref(false)
const labels:Record<string,string>={pending:'待就诊',in_progress:'就诊中',completed:'已完成',cancelled:'已取消',no_show:'爽约'}
const option=computed(()=>({tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['42%','68%'],data:data.value.appointment_status.map((x:any)=>({name:labels[x.name]||x.name,value:x.value}))}]}))
onMounted(async()=>{loading.value=true;try{data.value=(await http.get('/dashboard')).data}finally{loading.value=false}})
</script>
<template><div><div class="page-title"><div><h1>数据总览</h1><p>查看医院核心业务数据与预约状态分布</p></div></div><div v-loading="loading" class="metrics"><el-card><span>科室数量</span><b>{{data.cards.departments||0}}</b></el-card><el-card><span>医师数量</span><b>{{data.cards.doctors||0}}</b></el-card><el-card><span>患者数量</span><b>{{data.cards.patients||0}}</b></el-card><el-card><span>今日预约</span><b>{{data.cards.today_appointments||0}}</b></el-card></div><el-card class="chart"><template #header>预约状态分布</template><VChart :option="option" autoresize/></el-card></div></template>
