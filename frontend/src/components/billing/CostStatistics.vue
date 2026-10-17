<script setup lang="ts">
import{computed,onMounted,ref}from'vue'
import{ElMessage,ElMessageBox}from'element-plus'
import VChart from'vue-echarts'
import{use}from'echarts/core'
import{CanvasRenderer}from'echarts/renderers'
import{BarChart,LineChart}from'echarts/charts'
import{GridComponent,LegendComponent,TooltipComponent}from'echarts/components'
import ChartPanel from'../dashboard/ChartPanel.vue'
import ListError from'../common/ListError.vue'
import StatusLegend from'../common/StatusLegend.vue'
import{useListState}from'../../composables/useListState'
import{useAuthStore}from'../../stores/auth'
import{cancelBill,getExaminationCosts,getMedicineCosts,getPatients,payBill}from'../../services/operations'
import type{BillingRecord,ExaminationCostSummary,MedicineCostSummary,PatientSummary}from'../../types/medical'
import{categoryAxis,chartColors,tooltip,valueAxis}from'../../utils/charts'
import{statusInfo}from'../../utils/status'

use([CanvasRenderer,BarChart,LineChart,GridComponent,LegendComponent,TooltipComponent])

type CostKind='examination'|'medicine'
interface CostData{
  patient:{id:number;patient_no:string;full_name:string}
  date_from:string;date_to:string;date_basis:string
  summary:{total_amount:string;paid_amount:string;unpaid_amount:string;cancelled_amount:string;bill_count:number;cancelled_count:number}
  trend:{date:string;total:string;paid:string;unpaid:string}[]
  by_item?:ExaminationCostSummary['by_item']
  by_medicine?:MedicineCostSummary['by_medicine']
  count:number;page:number;page_size:number;results:BillingRecord[];max_range_days:number
}
const props=defineProps<{kind:CostKind}>()
const auth=useAuthStore(),isAdmin=computed(()=>auth.user?.role==='admin'),role=auth.user?.role||'patient'
const state=useListState(`cost-statistics-${props.kind}-${role}`,{preset:'30d' as '7d'|'30d'|'month'|'custom',range:null as [string,string]|null,patient:undefined as number|undefined,page:1,pageSize:10})
const data=ref<CostData|null>(null),loading=ref(false),error=ref(''),patients=ref<PatientSummary[]>([])
const isMedicine=computed(()=>props.kind==='medicine')
const label=computed(()=>isMedicine.value?'药品费用':'检查费用')
const reducedMotion=typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function isoDate(value:Date){const year=value.getFullYear(),month=String(value.getMonth()+1).padStart(2,'0'),day=String(value.getDate()).padStart(2,'0');return`${year}-${month}-${day}`}
function setPreset(value:'7d'|'30d'|'month'|'custom',reload=true){state.preset=value;if(value==='custom')return;const today=new Date(),start=new Date(today);if(value==='7d')start.setDate(today.getDate()-6);else if(value==='30d')start.setDate(today.getDate()-29);else start.setDate(1);state.range=[isoDate(start),isoDate(today)];if(reload)load(1)}
function changePreset(value:string|number|boolean){setPreset(String(value) as '7d'|'30d'|'month'|'custom')}
function errorText(e:any,fallback:string){return e.response?.data?.detail||fallback}
async function load(target=state.page){
  if(isAdmin.value&&!state.patient){data.value=null;return}
  if(!state.range)setPreset(state.preset==='custom'?'30d':state.preset,false)
  loading.value=true;error.value='';state.page=target
  try{const params={date_from:state.range?.[0],date_to:state.range?.[1],patient:isAdmin.value?state.patient:undefined,page:target,page_size:state.pageSize};data.value=(isMedicine.value?await getMedicineCosts(params):await getExaminationCosts(params)) as CostData}
  catch(e:any){data.value=null;error.value=errorText(e,`${label.value}加载失败`)}
  finally{loading.value=false}
}
async function pay(row:BillingRecord){try{await ElMessageBox.confirm(row.prescription_no?`确认支付 ¥${row.amount}？支付后将自动发药并扣减库存。`:`确认结算 ¥${row.amount}？`,'费用结算',{type:'info'});await payBill(row.id);ElMessage.success(row.prescription_no?'支付成功，药品已发放':'结算成功');await load(state.page)}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'结算失败'))}}
async function cancel(row:BillingRecord){try{await ElMessageBox.confirm('取消后该账单将不计入有效费用合计。','取消账单',{type:'warning'});await cancelBill(row.id);ElMessage.success('账单已取消');await load(state.page)}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'取消失败'))}}
function money(value?:string|number|null){return value===null||value===undefined?'—':`¥${Number(value||0).toFixed(2)}`}
function medicineSummary(row:BillingRecord){if(row.source_type!=='prescription')return'手工药品费用';const details=row.charge_details||[];if(!details.length||details.some(line=>!line.price_snapshot))return'历史处方明细';return details.map(line=>line.medicine_name).filter(Boolean).join('、')||'药品明细'}
function itemLabel(row:BillingRecord){return isMedicine.value?medicineSummary(row):row.examination_item_name||row.description}
function detailSummary(row:BillingRecord){return(row.charge_details||[]).map(line=>`${line.medicine_name} × ${line.quantity}`).join('；')}
function hasHistoricalLines(row:BillingRecord){return(row.charge_details||[]).some(line=>!line.price_snapshot)}
const trendOption=computed(()=>({
  animation:!reducedMotion,color:[chartColors[0],chartColors[2]],tooltip:{...tooltip,trigger:'axis'},legend:{top:0,right:0,itemWidth:16,itemHeight:3,textStyle:{color:'#587078'}},grid:{left:52,right:24,top:46,bottom:28},
  xAxis:{...categoryAxis,boundaryGap:false,data:(data.value?.trend||[]).map(row=>row.date.slice(5))},yAxis:{...valueAxis,axisLabel:{formatter:'¥{value}',color:'#587078'}},
  series:[{name:`${label.value}总额`,type:'line',smooth:.3,symbol:'circle',symbolSize:5,data:(data.value?.trend||[]).map(row=>Number(row.total)),lineStyle:{width:2.5},areaStyle:{color:isMedicine.value?'rgba(0,117,74,.08)':'rgba(28,110,140,.08)'}},{name:'待付金额',type:'bar',barMaxWidth:9,data:(data.value?.trend||[]).map(row=>Number(row.unpaid)),itemStyle:{borderRadius:[2,2,0,0]}}]
}))
onMounted(async()=>{if(isAdmin.value){try{patients.value=await getPatients()}catch{patients.value=[]}}if(!state.range)setPreset(state.preset==='custom'?'30d':state.preset,false);if(!isAdmin.value||state.patient)await load(1)})
</script>

<template>
  <div class="cost-statistics">
    <div class="table-tools exam-cost-tools">
      <el-segmented style="flex:none" :model-value="state.preset" :options="[{label:'近 7 天',value:'7d'},{label:'近 30 天',value:'30d'},{label:'本月',value:'month'},{label:'自定义',value:'custom'}]" @change="changePreset"/>
      <el-date-picker v-model="state.range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width:270px;flex:none" @change="state.preset='custom';load(1)"/>
      <el-select v-if="isAdmin" v-model="state.patient" filterable clearable placeholder="选择患者查询" style="width:220px" @change="load(1)"><el-option v-for="item in patients" :key="item.id" :label="`${item.full_name} · ${item.patient_no}`" :value="item.id"/></el-select>
      <el-button :disabled="isAdmin&&!state.patient" @click="load(1)">查询</el-button>
    </div>
    <div class="legend-row"><StatusLegend domain="billing" title="账单状态"/></div>
    <ListError v-if="error" :message="error" @retry="load(state.page)"/>
    <div v-else v-loading="loading" class="exam-cost-body">
      <template v-if="data">
        <div class="exam-cost-metrics">
          <div class="exam-cost-metric total"><span>{{label}}总额</span><strong>{{money(data.summary.total_amount)}}</strong><small>{{data.summary.bill_count}} 张有效账单</small></div>
          <div class="exam-cost-metric paid"><span>已付金额</span><strong>{{money(data.summary.paid_amount)}}</strong><small>按账单状态统计</small></div>
          <div class="exam-cost-metric unpaid"><span>待付金额</span><strong>{{money(data.summary.unpaid_amount)}}</strong><small>未形成账单的项目不计费</small></div>
          <div class="exam-cost-metric muted"><span>已取消</span><strong>{{money(data.summary.cancelled_amount)}}</strong><small>{{data.summary.cancelled_count}} 张，未计入合计</small></div>
        </div>
        <p class="data-footnote-inline">{{data.date_basis}} 区间 {{data.date_from}} 至 {{data.date_to}}。</p>
        <ChartPanel :title="`${label}逐日趋势`" description="折线为当日费用总额，柱状为当日待付金额" :empty="!data.trend.some(row=>Number(row.total)||Number(row.unpaid))"><v-chart class="chart exam-cost-chart" :option="trendOption" autoresize/></ChartPanel>
        <div class="exam-cost-grid">
          <el-card class="exam-cost-panel">
            <template #header><div class="section-head"><div><h2>{{isMedicine?'按药品汇总':'按检查项目汇总'}}</h2><p>{{isMedicine?'处方按药品快照分摊，历史处方与手工账单单独列示':'金额取账单快照，不使用当前项目价格重算'}}</p></div></div></template>
            <el-table v-if="isMedicine" :data="data.by_medicine||[]" empty-text="区间内暂无药品费用">
              <el-table-column prop="medicine_name" label="药品 / 费用来源" min-width="180"/>
              <el-table-column prop="quantity" label="数量" width="80"/>
              <el-table-column prop="bill_count" label="账单数" width="90"/>
              <el-table-column label="金额" width="120"><template #default="{row}"><b>{{money(row.total_amount)}}</b></template></el-table-column>
            </el-table>
            <el-table v-else :data="data.by_item||[]" empty-text="区间内暂无检查项目费用">
              <el-table-column prop="item_name" label="检查项目" min-width="170"/>
              <el-table-column prop="type_display" label="类别" width="100"/>
              <el-table-column prop="bill_count" label="账单数" width="90"/>
              <el-table-column label="金额" width="120"><template #default="{row}"><b>{{money(row.total_amount)}}</b></template></el-table-column>
            </el-table>
          </el-card>
          <el-card class="exam-cost-panel">
            <template #header><div class="section-head"><div><h2>{{label}}账单明细</h2><p>起止日均包含，按费用发生日期统计；取消账单保留展示但不计入合计</p></div><span class="muted">共 {{data.count}} 条</span></div></template>
            <el-table :data="data.results" row-key="id" class="desktop-table" empty-text="区间内暂无账单">
              <el-table-column v-if="isMedicine" type="expand"><template #default="{row}"><div class="charge-detail-panel"><template v-if="row.charge_details?.length"><ol><li v-for="(line,index) in row.charge_details" :key="line.prescription_item_id||index"><span class="charge-detail-name">{{line.medicine_name}}</span><span v-if="line.specification" class="muted">{{line.specification}}</span><span>数量 {{line.quantity}}</span><span v-if="line.price_snapshot&&line.unit_price">单价 ¥{{line.unit_price}}</span><span v-else class="muted">历史处方明细（按原账单总额）</span><b>¥{{line.amount}}</b></li></ol><p v-if="hasHistoricalLines(row)" class="muted">该处方缺少历史单价快照，按原账单总额列示。</p></template><p v-else class="muted">手工药品费用：{{row.description}}</p></div></template></el-table-column>
              <el-table-column prop="charge_date" label="发生日期" width="110"/>
              <el-table-column prop="bill_no" label="账单号" min-width="135"/>
              <el-table-column :label="isMedicine?'药品 / 费用来源':'检查项目'" min-width="160"><template #default="{row}">{{itemLabel(row)}}</template></el-table-column>
              <el-table-column label="金额" width="105"><template #default="{row}"><b>¥{{row.amount}}</b></template></el-table-column>
              <el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="statusInfo('billing',row.status).tone">{{statusInfo('billing',row.status).label}}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="120" fixed="right"><template #default="{row}"><template v-if="row.status==='unpaid'&&(isAdmin||auth.user?.role==='patient')"><el-button link type="success" @click="pay(row)">结算</el-button><el-button v-if="isAdmin" link type="danger" @click="cancel(row)">取消</el-button></template><span v-else class="cell-empty">—</span></template></el-table-column>
            </el-table>
            <div class="mobile-card-list">
              <article v-for="row in data.results" :key="row.id" class="mobile-info-card">
                <header><h3>{{itemLabel(row)}}</h3><el-tag :type="statusInfo('billing',row.status).tone">{{statusInfo('billing',row.status).label}}</el-tag></header>
                <p class="mobile-sub">{{row.bill_no}} · {{row.charge_date}}</p>
                <div class="mobile-line"><span>金额</span><b>¥{{row.amount}}</b></div>
                <div v-if="isMedicine&&row.charge_details?.length" class="mobile-sub">{{detailSummary(row)}}</div>
                <div v-else-if="isMedicine" class="mobile-sub">手工药品费用：{{row.description}}</div>
                <div class="actions"><template v-if="row.status==='unpaid'&&(isAdmin||auth.user?.role==='patient')"><el-button link type="success" @click="pay(row)">结算</el-button><el-button v-if="isAdmin" link type="danger" @click="cancel(row)">取消</el-button></template></div>
              </article>
            </div>
            <div class="pagination"><span>共 {{data.count}} 条</span><el-pagination v-model:current-page="state.page" v-model:page-size="state.pageSize" layout="sizes,prev,pager,next" :page-sizes="[10,20,50]" :total="data.count" @current-change="load" @size-change="()=>load(1)"/></div>
          </el-card>
        </div>
      </template>
      <el-empty v-else-if="!loading" :description="isAdmin?'请选择患者后查询'+label:'当前区间暂无'+label"/>
    </div>
  </div>
</template>
