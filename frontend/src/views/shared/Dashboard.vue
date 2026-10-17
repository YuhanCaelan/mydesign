<script setup lang="ts">
import{computed,onMounted,ref}from'vue'
import{useRouter}from'vue-router'
import VChart from'vue-echarts'
import{use}from'echarts/core'
import{CanvasRenderer}from'echarts/renderers'
import{BarChart,FunnelChart,LineChart}from'echarts/charts'
import{GridComponent,LegendComponent,TooltipComponent}from'echarts/components'
import{Refresh}from'@element-plus/icons-vue'
import ChartPanel from'../../components/dashboard/ChartPanel.vue'
import MetricTile from'../../components/dashboard/MetricTile.vue'
import StatusMatrix from'../../components/dashboard/StatusMatrix.vue'
import RevenuePie from'../../components/dashboard/RevenuePie.vue'
import ListError from'../../components/common/ListError.vue'
import{useAuthStore}from'../../stores/auth'
import{getDashboard}from'../../services/statistics'
import type{DashboardData,DashboardRange,RecentActivity}from'../../types/dashboard'
import{categoryAxis,chartColors,tooltip,valueAxis}from'../../utils/charts'
import{statusTone}from'../../utils/status'

use([CanvasRenderer,BarChart,FunnelChart,LineChart,GridComponent,LegendComponent,TooltipComponent])

const auth=useAuthStore(),router=useRouter(),loading=ref(true),range=ref<DashboardRange>('30d'),data=ref<DashboardData|null>(null),error=ref('')
const reducedMotion=typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const openVisit=(id:number)=>router.push({path:`/doctor/visits/${id}`,query:{returnTo:'/dashboard'}})
const role=computed(()=>auth.user!.role),isAdmin=computed(()=>role.value==='admin'),isDoctor=computed(()=>role.value==='doctor')
const copy=computed(()=>({
  admin:{title:'医院运行全景',desc:'聚合诊疗、检查、住院、药房与费用链路，快速定位运营阻塞点。'},
  doctor:{title:`${auth.user?.full_name}，今日诊疗有序推进`,desc:'在一个视图中掌握接诊节奏、检查协作队列与患者进展。'},
  patient:{title:`您好，${auth.user?.full_name}`,desc:'这里汇总您的预约、检查报告、处方和待支付事项。'}
}[role.value]))
const quick=computed(()=>({
  admin:[['人员与科室','/console/people?tab=doctors'],['排班设置','/console/outpatient?tab=schedules'],['检查管理','/console/clinical?tab=examinations'],['费用结算','/console/operations?tab=bills']],
  doctor:[['开始接诊','/doctor/outpatient?tab=appointments'],['书写病历','/doctor/clinical?tab=records'],['检查协作','/doctor/clinical?tab=examinations'],['住院管理','/doctor/inpatient?tab=admissions']],
  patient:[['预约挂号','/patient/visits?tab=appointments'],['检查报告','/patient/care?tab=reports'],['查看账单','/patient/finance?tab=bills'],['我的处方','/patient/care?tab=prescriptions']]
}[role.value]))
function openActivity(item:RecentActivity){
  if(role.value==='doctor')router.push({path:`/doctor/visits/${item.id}`,query:{returnTo:'/dashboard'}})
  else if(role.value==='admin')router.push('/console/outpatient?tab=appointments')
  else router.push('/patient/visits?tab=appointments')
}

const trendOption=computed(()=>({
  animation:!reducedMotion,color:[chartColors[0],chartColors[1],chartColors[2]],tooltip:{...tooltip,trigger:'axis'},legend:{top:0,right:0,itemWidth:18,itemHeight:3,textStyle:{color:'#587078'}},
  grid:{left:42,right:24,top:48,bottom:28},xAxis:{...categoryAxis,boundaryGap:false,data:(data.value?.timeseries||[]).map(x=>x.date.slice(5))},yAxis:valueAxis,
  series:[
    {name:'预约人次',type:'line',smooth:.32,symbol:'circle',symbolSize:6,data:(data.value?.timeseries||[]).map(x=>x.visits),lineStyle:{width:2.5},areaStyle:{color:'rgba(28,110,140,.08)'}},
    {name:'完成诊疗',type:'line',smooth:.32,symbol:'circle',symbolSize:5,data:(data.value?.timeseries||[]).map(x=>x.completed),lineStyle:{width:2.5}}
  ]
}))
const billingTotal=computed(()=>(data.value?.billing_categories||[]).reduce((sum,item)=>sum+Math.max(0,Number(item.value)),0))
const departmentOption=computed(()=>({
  animation:!reducedMotion,color:[chartColors[0]],tooltip:{...tooltip,trigger:'axis'},grid:{left:76,right:22,top:14,bottom:24},xAxis:valueAxis,
  yAxis:{...categoryAxis,data:(data.value?.department_workload||[]).map(x=>x.name)},series:[{type:'bar',barWidth:12,data:(data.value?.department_workload||[]).map(x=>x.value),itemStyle:{borderRadius:[0,3,3,0]}}]
}))
const workflowOption=computed(()=>({
  animation:!reducedMotion,color:['#1c6e8c','#277f94','#36999e','#00a88f','#55bba6','#91c9b5'],tooltip:{...tooltip,trigger:'item'},
  series:[{type:'funnel',left:'8%',right:'8%',top:8,bottom:8,minSize:'30%',maxSize:'100%',sort:'none',gap:3,label:{position:'inside',formatter:'{b}  {c}',color:'#fff',fontWeight:600},itemStyle:{borderWidth:0},data:data.value?.workflow||[]}]
}))
async function load(){loading.value=true;error.value='';try{data.value=await getDashboard(range.value)}catch(e:any){data.value=null;error.value=e.response?.data?.detail||'工作台数据加载失败'}finally{loading.value=false}}
onMounted(load)
</script>

<template>
  <section v-loading="loading" class="command-dashboard">
    <header class="command-intro">
      <div>
        <div class="live-label"><i/>实时业务数据</div>
        <h1>{{copy.title}}</h1>
        <p>{{copy.desc}}</p>
      </div>
      <div class="intro-actions">
        <el-segmented v-if="role!=='patient'" v-model="range" :options="[{label:'7 天',value:'7d'},{label:'30 天',value:'30d'},{label:'90 天',value:'90d'}]" @change="load"/>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </header>

    <ListError v-if="error" :message="error" @retry="load"/>
    <template v-else>
    <div class="clinical-metrics">
      <MetricTile v-for="item in data?.kpis||[]" :key="item.key" :item="item"/>
    </div>

    <template v-if="isAdmin">
      <div class="command-grid command-grid-primary">
        <ChartPanel class="span-8" title="诊疗运行趋势" description="预约与完成诊疗量的周期变化" :empty="!data?.timeseries?.some(x=>x.visits||x.completed)"><v-chart class="chart chart-tall" :option="trendOption" autoresize/></ChartPanel>
        <ChartPanel class="span-4" title="诊疗状态" description="当前统计周期内预约流转构成，占比分母为全部预约"><StatusMatrix :items="data?.appointment_status||[]"/></ChartPanel>
        <ChartPanel class="span-4" title="全流程转化" description="从预约到结算的业务漏斗" :empty="!data?.workflow?.some(x=>Number(x.value))"><v-chart class="chart" :option="workflowOption" autoresize/></ChartPanel>
        <ChartPanel class="span-4" title="科室工作负荷" description="按预约量识别高负荷科室" :empty="!data?.department_workload?.length"><v-chart class="chart" :option="departmentOption" autoresize/></ChartPanel>
        <ChartPanel class="span-4" title="收入构成" description="扇区角度对应已结算金额，仅包含正金额类别"><template #actions><span class="revenue-total">已结算总额 <b>¥{{billingTotal.toFixed(2)}}</b></span></template><RevenuePie :items="data?.billing_categories||[]"/></ChartPanel>
      </div>
    </template>

    <template v-else-if="isDoctor">
      <div class="command-grid command-grid-primary">
        <ChartPanel class="span-8" title="个人诊疗趋势" description="预约与已完成诊疗的周期变化" :empty="!data?.timeseries?.some(x=>x.visits||x.completed)"><v-chart class="chart chart-tall" :option="trendOption" autoresize/></ChartPanel>
        <ChartPanel class="span-4" title="今日接诊节奏" description="按时间顺序推进患者接诊" :empty="!data?.today_schedule?.length">
          <ol class="clinical-timeline"><li v-for="item in data?.today_schedule" :key="item.id" role="link" tabindex="0" @click="openVisit(item.id)" @keyup.enter="openVisit(item.id)"><time>{{item.time}}</time><span/><div><b>{{item.patient}}</b><p>{{item.reason||'未填写就诊原因'}}</p></div><em :class="statusTone('appointment',item.status)">{{item.status_label}}</em></li></ol>
        </ChartPanel>
        <ChartPanel class="span-7" title="全院检查协作队列" description="所有医师均可参与处理待检查项目" :empty="!data?.examination_queue?.length">
          <div class="queue-list"><router-link v-for="item in data?.examination_queue" :key="item.id" to="/doctor/clinical?tab=examinations"><span class="queue-number">{{item.number}}</span><b>{{item.patient}}</b><span>{{item.type}}</span><em :class="statusTone('examination',item.status)">{{item.status_label}}</em></router-link></div>
        </ChartPanel>
        <ChartPanel class="span-5" title="诊疗状态" description="当前周期内个人预约构成，占比分母为本人全部预约"><StatusMatrix :items="data?.appointment_status||[]"/></ChartPanel>
      </div>
    </template>

    <template v-else>
      <div v-if="data?.next_appointment" class="next-visit"><div><span>下一次就诊</span><strong>{{data.next_appointment.date}} <i>{{data.next_appointment.time}}</i></strong><p>{{data.next_appointment.department}} · {{data.next_appointment.doctor}}</p></div><router-link to="/patient/visits?tab=appointments">查看预约 <b>→</b></router-link></div>
      <div v-else class="next-visit next-visit-empty"><div><span>健康计划</span><strong>暂无待就诊预约</strong><p>按科室和医师查询可预约号源</p></div><router-link to="/patient/visits?tab=appointments">立即预约 <b>→</b></router-link></div>
    </template>

    <div class="command-lower">
      <section class="activity-panel">
        <header><div><h2>{{role==='patient'?'我的就诊记录':'近期诊疗动态'}}</h2><p>最近更新的预约与诊疗状态</p></div><span>{{data?.recent_activity?.length||0}} 条</span></header>
        <div v-if="data?.recent_activity?.length" class="activity-table">
          <div class="activity-row activity-head"><span>编号</span><span v-if="role!=='patient'">患者</span><span v-else>医师 / 科室</span><span>就诊时间</span><span>状态</span></div>
          <div v-for="item in data.recent_activity" :key="item.id" class="activity-row activity-link" role="link" tabindex="0" @click="openActivity(item)" @keyup.enter="openActivity(item)"><code>{{item.number}}</code><span v-if="role!=='patient'"><b>{{item.patient}}</b><small>{{item.department}}</small></span><span v-else><b>{{item.doctor}}</b><small>{{item.department}}</small></span><time>{{item.date}}<small>{{item.time}}</small></time><em :class="statusTone('appointment',item.status)">{{item.status}}</em></div>
        </div><el-empty v-else :image-size="64" description="暂无诊疗动态"/>
      </section>
      <aside class="action-rail">
        <section class="attention-panel"><header><h2>需要关注</h2><span>待办</span></header><router-link v-for="item in data?.alerts||[]" :key="item.label" :to="item.path" :class="item.tone"><span>{{item.label}}</span><strong>{{item.value}}</strong><b>→</b></router-link></section>
        <section class="quick-panel"><h2>快捷操作</h2><router-link v-for="item in quick" :key="item[0]" :to="item[1]"><span>{{item[0]}}</span><b>↗</b></router-link></section>
      </aside>
    </div>
    </template>
  </section>
</template>
