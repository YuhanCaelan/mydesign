<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{useRoute}from'vue-router'
import{ElMessage,ElMessageBox}from'element-plus'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import CostStatistics from'../../components/billing/CostStatistics.vue'
import{useListState}from'../../composables/useListState'
import type{ViewMode}from'../../utils/view'
import{useAuthStore}from'../../stores/auth'
import{cancelBill,createBill,getActiveAdmissions,getBills,getPatients,payBill}from'../../services/operations'
import type{BillingRecord,InpatientAdmission,PatientSummary}from'../../types/medical'
import{statusInfo}from'../../utils/status'

type BillingView='bills'|'exam-costs'|'medicine-costs'
const props=defineProps<{view?:BillingView}>()
const auth=useAuthStore(),route=useRoute(),isAdmin=computed(()=>auth.user?.role==='admin'),isPatient=computed(()=>auth.user?.role==='patient'),canViewCosts=computed(()=>isAdmin.value||isPatient.value)
const showTabs=computed(()=>!props.view),activeTab=ref<BillingView>(props.view||'bills')
const billState=useListState(`billing-bills-${auth.user?.role||'guest'}`,{status:'',search:'',page:1,view:(isPatient.value?'cards':'list') as ViewMode})
const rows=ref<BillingRecord[]>([]),patients=ref<PatientSummary[]>([]),loading=ref(false),billsError=ref(''),dialog=ref(false),saving=ref(false),total=ref(0)
const billGroups=computed(()=>{const groups=new Map<string,BillingRecord[]>();for(const row of rows.value){const key=row.charge_date||row.created_at?.slice(0,10)||'未标明日期';const list=groups.get(key)||[];list.push(row);groups.set(key,list)}return [...groups.entries()].map(([date,items])=>({date,items,total:items.filter(item=>item.status!=='cancelled').reduce((sum,item)=>sum+Number(item.amount||0),0)}))})
const form=reactive({patient_id:undefined as number|undefined,admission_id:null as number|null,category:'other',description:'',amount:0}),admissions=ref<InpatientAdmission[]>([])
const categories=[['registration','挂号费'],['examination','检查费'],['medicine','药品费'],['inpatient','住院费'],['other','其他']]

function errorText(e:any,fallback:string){const errors=e.response?.data?.errors;if(errors){const first=Object.values(errors)[0] as string|string[]|undefined;if(first)return Array.isArray(first)?first.join('；'):String(first)}return e.response?.data?.detail||fallback}
function inpatientPath(row:BillingRecord){if(!row.admission_id)return'';const prefix=auth.user?.role==='admin'?'/console/inpatients':auth.user?.role==='doctor'?'/doctor/inpatients':'/patient/inpatients';return`${prefix}/${row.admission_id}`}
function sourcePath(row:BillingRecord){
  if(row.source_type==='examination'){
    const report=row.examination_no?`&report=${row.examination_no}`:''
    if(auth.user?.role==='admin')return'/console/clinical?tab=examinations'
    if(auth.user?.role==='doctor')return`/doctor/records?patient=${row.patient_id}&tab=reports${report}`
    return`/patient/records?tab=reports${report}`
  }
  if(row.source_type==='admission')return auth.user?.role==='admin'?'/console/inpatient?tab=admissions':auth.user?.role==='doctor'?'/doctor/inpatient?tab=admissions':'/patient/care?tab=admissions'
  if(row.source_type==='prescription')return auth.user?.role==='patient'?'/patient/care?tab=prescriptions':auth.user?.role==='doctor'?'/doctor/clinical?tab=prescriptions':''
  return''
}
async function loadAdmissions(){admissions.value=[];form.admission_id=null;if(!form.patient_id)return;try{admissions.value=await getActiveAdmissions(form.patient_id)}catch{admissions.value=[]}}
async function load(){loading.value=true;billsError.value='';try{const data=await getBills({status:billState.status||undefined,search:billState.search||undefined,page:billState.page});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;billsError.value=errorText(e,'账单加载失败')}finally{loading.value=false}}
function searchBills(){billState.page=1;load()}
async function open(){Object.assign(form,{patient_id:undefined,admission_id:null,category:'other',description:'',amount:0});admissions.value=[];dialog.value=true;if(!patients.value.length)patients.value=await getPatients()}
async function submit(){if(!form.patient_id||!form.description.trim()||form.amount<=0){ElMessage.warning('请完整填写账单信息');return}saving.value=true;try{await createBill(form);ElMessage.success('账单已创建');dialog.value=false;await load()}catch(e:any){ElMessage.error(errorText(e,'创建失败'))}finally{saving.value=false}}
async function pay(row:BillingRecord){try{await ElMessageBox.confirm(row.prescription_no?`确认支付 ¥${row.amount}？支付后将自动发放处方药品并扣减库存。`:`确认结算 ¥${row.amount}？`,'费用结算',{type:'info'});await payBill(row.id);ElMessage.success(row.prescription_no?'支付成功，药品已发放':'结算成功');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'结算失败'))}}
async function cancel(row:BillingRecord){try{await ElMessageBox.confirm('确认取消该账单？','取消账单',{type:'warning'});await cancelBill(row.id);await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'取消失败'))}}
async function changeTab(name:string|number){activeTab.value=name==='medicine-costs'?'medicine-costs':name==='exam-costs'?'exam-costs':'bills';if(activeTab.value==='bills')await load()}
onMounted(async()=>{if(activeTab.value==='bills')await load()})
</script>

<template>
  <section>
    <div class="page-heading">
      <div><p class="eyebrow">BILLING & SETTLEMENT</p><h1>{{activeTab==='exam-costs'?'检查费用':activeTab==='medicine-costs'?'药品费用':isPatient?'我的费用':'费用结算'}}</h1><p>{{activeTab!=='bills'?'按自选日期区间核对费用趋势与明细；取消账单保留展示但不计入合计':isPatient?'查看全部账单并完成演示支付':'管理账单并查看患者检查、药品费用'}}</p></div>
      <el-button v-if="isAdmin&&activeTab==='bills'" type="primary" @click="open">＋ 创建账单</el-button>
    </div>
    <el-card class="table-card">
      <div v-if="showTabs" class="inline-tabs"><el-tabs v-model="activeTab" @tab-change="changeTab"><el-tab-pane label="全部账单" name="bills"/><el-tab-pane v-if="canViewCosts" label="检查费用" name="exam-costs"/><el-tab-pane v-if="canViewCosts" label="药品费用" name="medicine-costs"/></el-tabs></div>

      <div v-if="activeTab==='bills'">
        <div class="table-tools">
          <el-input v-model="billState.search" clearable placeholder="搜索账单号、患者或费用说明" @keyup.enter="searchBills"/>
          <el-select v-model="billState.status" clearable placeholder="全部状态" @change="searchBills"><el-option label="待缴费" value="unpaid"/><el-option label="已缴费" value="paid"/><el-option label="已取消" value="cancelled"/></el-select>
          <el-button @click="searchBills">查询</el-button>
          <span class="table-count">共 {{total}} 条</span>
          <ViewSwitch v-model="billState.view"/>
        </div>
        <div class="legend-row"><StatusLegend domain="billing" title="账单状态"/></div>
        <ListError v-if="billsError" :message="billsError" @retry="load"/>
        <div v-else-if="billState.view==='cards'" v-loading="loading" class="bill-ledger">
          <section v-for="group in billGroups" :key="group.date" class="ledger-group">
            <header class="ledger-group-head"><h3>{{group.date}}</h3><span>{{group.items.length}} 笔 · 计入 ¥{{group.total.toFixed(2)}}</span></header>
            <div class="ledger-list">
              <article v-for="row in group.items" :key="row.id" class="ledger-card" :data-status="row.status">
                <div class="ledger-main">
                  <h3>{{row.description}}</h3>
                  <p>{{row.bill_no}}<template v-if="!isPatient"> · {{row.patient_name}}</template> · {{row.category_display}}<template v-if="row.prescription_no"> · 处方 {{row.prescription_no}}</template></p>
                  <p v-if="row.examination_no">检查 {{row.examination_no}}<template v-if="row.examination_item_name"> · {{row.examination_item_name}}</template></p>
                  <p v-if="row.admission_id"><router-link :to="{path:inpatientPath(row),query:{returnTo:route.fullPath}}" class="source-link">归集住院 {{row.inpatient_admission_no||`#${row.admission_id}`}} ↗</router-link></p>
                  <p v-if="sourcePath(row)"><router-link :to="sourcePath(row)" class="source-link">查看业务来源 ↗</router-link></p>
                </div>
                <div class="ledger-amount">¥{{row.amount}}<el-tag :type="statusInfo('billing',row.status).tone" class="ledger-tag">{{statusInfo('billing',row.status).label}}</el-tag></div>
                <div class="ledger-actions"><el-button v-if="row.status==='unpaid'&&(isPatient||isAdmin)" link type="success" @click="pay(row)">{{row.prescription_no?'支付并取药':'结算'}}</el-button><el-button v-if="row.status==='unpaid'&&isAdmin" link type="danger" @click="cancel(row)">取消</el-button><span v-if="row.paid_at" class="ledger-paid">支付于 {{row.paid_at?.replace('T',' ').slice(0,16)}}</span></div>
              </article>
            </div>
          </section>
          <el-empty v-if="!rows.length&&!loading" description="暂无账单记录"/>
          <p class="ledger-note">按发生日期归组展示本页账单；已取消账单保留展示，但不计入日期合计。</p>
        </div>
        <template v-else>
          <el-table v-loading="loading" :data="rows" class="desktop-table">
            <el-table-column prop="bill_no" label="账单号" min-width="150"/>
            <el-table-column v-if="!isPatient" prop="patient_name" label="患者"/>
            <el-table-column label="费用来源" min-width="150"><template #default="{row}"><router-link v-if="sourcePath(row)" :to="sourcePath(row)" class="source-link">{{row.source_type==='examination'?`检查 ${row.examination_no||''}`:row.source_type==='admission'?`住院 ${row.admission_no||''}`:row.source_type==='prescription'?`处方 ${row.prescription_no||''}`:'业务详情'}} ↗</router-link><span v-else>{{row.source_type==='prescription'?`处方 ${row.prescription_no||''}`:'手工账单'}}</span></template></el-table-column>
            <el-table-column label="归集住院" min-width="140"><template #default="{row}"><router-link v-if="row.admission_id" :to="{path:inpatientPath(row),query:{returnTo:route.fullPath}}" class="source-link">{{row.inpatient_admission_no||`住院 #${row.admission_id}`}} ↗</router-link><span v-else class="cell-empty">未归集</span></template></el-table-column>
            <el-table-column prop="category_display" label="费用类别"/>
            <el-table-column label="发生日期" width="115"><template #default="{row}">{{row.charge_date||'—'}}</template></el-table-column>
            <el-table-column prop="description" label="费用说明" min-width="200"/>
            <el-table-column label="金额" width="120"><template #default="{row}"><b>¥{{row.amount}}</b></template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('billing',row.status).tone">{{statusInfo('billing',row.status).label}}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="150"><template #default="{row}"><el-button v-if="row.status==='unpaid'&&(isPatient||isAdmin)" link type="success" @click="pay(row)">{{row.prescription_no?'支付并取药':'结算'}}</el-button><el-button v-if="row.status==='unpaid'&&isAdmin" link type="danger" @click="cancel(row)">取消</el-button></template></el-table-column>
          </el-table>
          <div class="mobile-card-list">
            <article v-for="row in rows" :key="row.id" class="mobile-info-card">
              <header><h3>{{row.description}}</h3><el-tag :type="statusInfo('billing',row.status).tone">{{statusInfo('billing',row.status).label}}</el-tag></header>
              <p class="mobile-sub">{{row.bill_no}} · {{row.patient_name}} · {{row.category_display}}</p>
              <div class="mobile-line"><span>发生日期</span><b>{{row.charge_date||'—'}}</b></div>
              <div class="mobile-line"><span>金额</span><b>¥{{row.amount}}</b></div>
              <div class="actions"><el-button v-if="row.status==='unpaid'&&(isPatient||isAdmin)" link type="success" @click="pay(row)">{{row.prescription_no?'支付并取药':'结算'}}</el-button><el-button v-if="row.status==='unpaid'&&isAdmin" link type="danger" @click="cancel(row)">取消</el-button></div>
            </article>
            <div v-if="!rows.length&&!loading" class="mobile-empty">暂无账单记录</div>
          </div>
        </template>
        <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="billState.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
      </div>

      <CostStatistics v-else :kind="activeTab==='medicine-costs'?'medicine':'examination'"/>
    </el-card>

    <el-dialog v-model="dialog" title="创建费用账单" width="min(560px,94vw)">
      <el-form label-position="top">
        <el-form-item label="患者" required><el-select v-model="form.patient_id" filterable style="width:100%" @change="loadAdmissions"><el-option v-for="item in patients" :key="item.id" :label="`${item.full_name} · ${item.patient_no}`" :value="item.id"/></el-select></el-form-item>
        <el-form-item label="归集到住院（可选）"><el-select v-model="form.admission_id" clearable filterable style="width:100%" placeholder="选择在院记录，费用将计入该次住院清单"><el-option v-for="item in admissions" :key="item.id" :label="`${item.admission_no} · ${item.ward}${item.bed_no} · ${item.department_name}`" :value="item.id"/></el-select><small>仅显示所选患者的在院记录；患者一致性由后端再次校验。</small></el-form-item>
        <el-row :gutter="14"><el-col :span="12"><el-form-item label="类别"><el-select v-model="form.category" style="width:100%"><el-option v-for="item in categories" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" style="width:100%"/></el-form-item></el-col></el-row>
        <el-form-item label="费用说明" required><el-input v-model="form.description"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">创建账单</el-button></template>
    </el-dialog>
  </section>
</template>
