<script setup lang="ts">
import {computed,onMounted,ref}from'vue'
import {useRoute,useRouter}from'vue-router'
import {ElMessage,ElMessageBox}from'element-plus'
import {useAuthStore} from '../../stores/auth'
import ListError from '../../components/common/ListError.vue'
import {statusInfo} from '../../utils/status'
import {cancelBill,dischargePatient,getAdmissionCharges,payBill}from '../../services/operations'
import type {BillingRecord,ChargeDetailLine,InpatientChargeDetail}from '../../types/medical'

const auth=useAuthStore(),route=useRoute(),router=useRouter()
const canManage=computed(()=>auth.user?.role==='admin'||auth.user?.role==='doctor'),isPatient=computed(()=>auth.user?.role==='patient'),isAdmin=computed(()=>auth.user?.role==='admin')
const admissionId=computed(()=>Number(route.params.admissionId))
const returnPath=computed(()=>typeof route.query.returnTo==='string'&&route.query.returnTo.startsWith('/')?route.query.returnTo:auth.user?.role==='admin'?'/console/inpatient?tab=admissions':auth.user?.role==='doctor'?'/doctor/inpatient?tab=admissions':'/patient/care?tab=admissions')
const data=ref<InpatientChargeDetail|null>(null),loading=ref(false),error=ref('')

async function load(){loading.value=true;error.value='';try{data.value=await getAdmissionCharges(admissionId.value)}catch(e:any){data.value=null;error.value=e.response?.data?.detail||'住院详情加载失败';ElMessage.error(error.value)}finally{loading.value=false}}
function shortTime(value?:string|null){return value?value.replace('T',' ').slice(0,16):'—'}
function lineNames(row:BillingRecord&{charge_details?:ChargeDetailLine[]}){return (row.charge_details||[]).map(line=>line.medicine_name).join('、')}
function money(value?:string|number|null){return value===null||value===undefined?'—':`¥${Number(value).toFixed(2)}`}
async function settle(row:BillingRecord){const hint=row.prescription_id?'确认支付该药品费用？支付后系统将自动发药并扣减库存。':'确认结算该笔住院费用？';try{await ElMessageBox.confirm(hint,'费用结算',{type:'info'});await payBill(row.id);ElMessage.success(row.prescription_id?'支付成功，药品已发放':'结算成功');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'结算失败')}}
async function cancel(row:BillingRecord){try{await ElMessageBox.confirm('取消后该笔费用不计入住院合计。','取消账单',{type:'warning'});await cancelBill(row.id);ElMessage.success('账单已取消');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'取消失败')}}
async function discharge(){const admission=data.value?.admission;if(!admission)return;try{const{value}=await ElMessageBox.prompt('填写出院小结，系统将固定床位费并生成唯一床位费账单。','办理出院',{inputType:'textarea',inputValidator:(text:string)=>Boolean(text&&text.trim())||'出院小结不能为空'});await dischargePatient(admission.id,value.trim());ElMessage.success('出院办理完成，床位费已固定');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}
onMounted(load)
</script>

<template>
  <section v-loading="loading">
    <div class="page-heading">
      <div>
        <el-button link @click="router.push(returnPath)">← 返回</el-button>
        <h1>{{isPatient?'我的住院详情':'住院详情与费用清单'}}</h1>
        <p v-if="data">{{data.admission.admission_no}} · {{data.admission.patient_name}} · {{data.admission.department_name}} · {{data.admission.ward}} {{data.admission.bed_no}}</p>
      </div>
      <div v-if="data" class="visit-actions">
        <el-tag size="large" :type="statusInfo('inpatient',data.admission.status).tone">{{statusInfo('inpatient',data.admission.status).label}}</el-tag>
        <el-button v-if="canManage&&data.admission.status==='admitted'" type="success" @click="discharge">办理出院</el-button>
        <el-button @click="load">刷新费用</el-button>
      </div>
    </div>
    <template v-if="data">
      <div class="patient-band">
        <div><span>患者</span><strong>{{data.admission.patient_name}}</strong><small>{{data.admission.patient_no}} · {{data.admission.department_name}}</small></div>
        <div><span>主治医师</span><b>{{data.admission.doctor_name}}</b></div>
        <div><span>床位与日费快照</span><b>{{data.admission.ward}} {{data.admission.bed_no}} · {{money(data.admission.daily_rate_snapshot)}}/日</b></div>
        <div><span>{{data.admission.status==='admitted'?'已住天数':'实际计费天数'}}</span><b>{{data.admission.status==='admitted'?`${data.admission.days_admitted} 天（预计 ${money(data.summary.projected_bed_fee)}）`:`${data.admission.billable_days} 天`}}</b></div>
      </div>
      <div class="charge-metrics">
        <div class="charge-metric"><span>费用合计</span><strong>{{money(data.summary.billed_amount)}}</strong><small>不含已取消账单</small></div>
        <div class="charge-metric"><span>已付金额</span><strong>{{money(data.summary.paid_amount)}}</strong><small>{{data.summary.bill_count||0}} 张有效账单</small></div>
        <div class="charge-metric warning"><span>待付金额</span><strong>{{money(data.summary.unpaid_amount)}}</strong><small>各账单分别支付</small></div>
        <div class="charge-metric"><span>住院中预计床位费</span><strong>{{money(data.summary.projected_bed_fee)}}</strong><small>{{money(data.summary.bed_daily_rate)}} × {{data.summary.billable_days}} 天</small></div>
        <div class="charge-metric total"><span>预计总额</span><strong>{{money(data.summary.estimated_total)}}</strong><small>{{data.summary.bed_bill_generated?'床位费账单已生成':'出院时生成床位费账单'}}</small></div>
      </div>
      <div class="admission-grid">
        <el-card class="clinical-editor">
          <template #header><div class="section-head"><div><h2>住院信息</h2><p>诊断、床位与状态时间线</p></div></div></template>
          <div class="record-detail">
            <div><span>入院诊断</span><p>{{data.admission.admission_diagnosis}}</p></div>
            <div><span>床位快照</span><b>{{data.admission.ward}} {{data.admission.bed_no}} · 日费 {{money(data.admission.daily_rate_snapshot)}}</b></div>
            <div><span>入院时间</span><b>{{shortTime(data.admission.admitted_at)}}</b></div>
            <div v-if="data.admission.discharged_at"><span>出院时间</span><b>{{shortTime(data.admission.discharged_at)}}</b></div>
            <div><span>出院小结</span><p>{{data.admission.discharge_summary||'尚未办理出院'}}</p></div>
          </div>
          <h3>状态时间线</h3>
          <el-timeline>
            <el-timeline-item v-for="event in data.admission.timeline||[]" :key="event.key" :timestamp="event.at?shortTime(event.at):'待完成'" :type="event.done?'success':'info'">{{event.label}}</el-timeline-item>
          </el-timeline>
        </el-card>
        <el-card class="charge-card">
          <template #header><div class="section-head"><div><h2>费用清单</h2><p>按发生日期逐项列出，多药品处方可展开逐项核对；取消的账单不计入合计</p></div><span class="muted">{{data.bed_fee_rule}}</span></div></template>
          <el-table :data="data.items" row-key="id" empty-text="本次住院暂无费用记录">
            <el-table-column type="expand">
              <template #default="{row}">
                <div class="charge-detail-panel">
                  <p v-if="!row.charge_details?.length" class="muted">该账单没有药品明细行，金额为账单汇总金额。</p>
                  <ol v-else>
                    <li v-for="(line,index) in row.charge_details" :key="line.prescription_item_id||index">
                      <span class="charge-detail-name">{{line.medicine_name}}</span>
                      <span v-if="line.specification" class="muted">{{line.specification}}</span>
                      <span>数量 {{line.quantity}}</span>
                      <span v-if="line.unit_price">单价 ¥{{line.unit_price}}</span>
                      <span v-else class="muted">历史处方无单价快照</span>
                      <b>¥{{line.amount}}</b>
                    </li>
                  </ol>
                  <p v-if="row.charge_details?.length" class="muted">明细行合计 ¥{{row.details_total}}<template v-if="row.details_consistent">（与账单金额一致）</template></p>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="发生日期" width="115"><template #default="{row}">{{row.charge_date||'—'}}</template></el-table-column>
            <el-table-column prop="category_display" label="类别" width="95"/>
            <el-table-column label="费用明细" min-width="220"><template #default="{row}"><span v-if="row.charge_details?.length">{{row.charge_details.length}} 条明细：{{lineNames(row)}}</span><span v-else>{{row.description}}</span></template></el-table-column>
            <el-table-column label="金额" width="110"><template #default="{row}"><b>¥{{row.amount}}</b></template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('billing',row.status).tone">{{statusInfo('billing',row.status).label}}</el-tag></template></el-table-column>
            <el-table-column label="支付日期" min-width="140"><template #default="{row}"><span v-if="row.payment_date">{{row.payment_date}}</span><span v-else class="cell-empty">未支付</span></template></el-table-column>
            <el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><template v-if="row.status==='unpaid'"><el-button v-if="isPatient||isAdmin" link type="success" @click="settle(row)">{{row.prescription_id?'支付并取药':'结算'}}</el-button><el-button v-if="isAdmin" link type="danger" @click="cancel(row)">取消</el-button></template><span v-else class="cell-empty">—</span></template></el-table-column>
          </el-table>
          <div class="charge-subtotals">
            <span v-for="row in data.summary.categories||[]" :key="row.category">{{row.label}} ¥{{row.total}}</span>
            <span v-if="data.summary.detail_line_count">共 {{data.summary.detail_line_count}} 条药品明细行</span>
            <span v-if="data.summary.cancelled_count">已取消 {{data.summary.cancelled_count}} 张（¥{{data.summary.cancelled_amount}}）未计入合计</span>
          </div>
        </el-card>
      </div>
    </template>
    <ListError v-if="error" :message="error" @retry="load"/>
    <el-empty v-else-if="!loading&&!data" description="住院记录不存在或无权访问"/>
  </section>
</template>
