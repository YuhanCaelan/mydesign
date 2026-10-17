<script setup lang="ts">
import{computed,onMounted,reactive,ref,watch}from'vue'
import{useRoute,useRouter}from'vue-router'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import TaskCard from'../../components/common/TaskCard.vue'
import{useListState} from'../../composables/useListState'
import{statusInfo}from'../../utils/status'
import type{ViewMode}from'../../utils/view'
import{admitPatient,createInpatient,dischargePatient,getInpatients,getOperationDepartments,getOperationDoctors,getPatients,getWardBeds}from'../../services/operations'
import type{Department,DoctorSummary,InpatientAdmission,PatientSummary,WardBed}from'../../types/medical'
const auth=useAuthStore(),route=useRoute(),router=useRouter(),role=auth.user?.role||'patient',canManage=computed(()=>role==='admin'||role==='doctor'),isPatient=computed(()=>role==='patient')
const state=useListState(`inpatients-${role}`,{page:1,search:'',status:'',view:'cards' as ViewMode})
const rows=ref<InpatientAdmission[]>([]),patients=ref<PatientSummary[]>([]),doctors=ref<DoctorSummary[]>([]),departments=ref<Department[]>([]),beds=ref<WardBed[]>([]),loading=ref(false),error=ref(''),dialog=ref(false),saving=ref(false),total=ref(0)
const statusOrder=['admitted','pending','discharged','cancelled']
const groups=computed(()=>statusOrder.map(key=>({key,info:statusInfo('inpatient',key),items:rows.value.filter(item=>item.status===key)})).filter(group=>group.items.length))
const form=reactive({patient_id:undefined as number|undefined,doctor_id:undefined as number|undefined,department_id:undefined as number|undefined,bed_id:undefined as number|undefined,admission_diagnosis:''})
const detailPrefix=computed(()=>role==='admin'?'/console/inpatients':role==='doctor'?'/doctor/inpatients':'/patient/inpatients')
async function load(){loading.value=true;error.value='';try{const data=await getInpatients({page:state.page,search:state.search||undefined,status:state.status||undefined});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'住院记录加载失败'}finally{loading.value=false}}
function searchAdmissions(){state.page=1;load()}
function openDetail(row:InpatientAdmission){router.push({path:`${detailPrefix.value}/${row.id}`,query:{returnTo:route.fullPath}})}
function openBedBoard(){router.push({path:route.path,query:{...route.query,tab:'beds'}})}
async function loadBeds(){form.bed_id=undefined;beds.value=[];if(!form.department_id)return;try{beds.value=(await getWardBeds({department:form.department_id,available:true})).results}catch(e:any){ElMessage.error(e.response?.data?.detail||'床位加载失败')}}
async function open(){Object.assign(form,{patient_id:undefined,doctor_id:undefined,department_id:undefined,bed_id:undefined,admission_diagnosis:''});dialog.value=true;[patients.value,doctors.value,departments.value]=await Promise.all([getPatients(),getOperationDoctors(),getOperationDepartments()])}
watch(()=>form.department_id,()=>{if(dialog.value)loadBeds()})
watch(()=>state.status,()=>searchAdmissions())
async function submit(){if(!form.patient_id||!form.doctor_id||!form.department_id||!form.bed_id||!form.admission_diagnosis.trim()){ElMessage.warning('请完整选择患者、医师、科室、可用床位并填写入院诊断');return}saving.value=true;try{await createInpatient(form);ElMessage.success('住院申请已创建');dialog.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||JSON.stringify(e.response?.data?.errors||'创建失败'))}finally{saving.value=false}}
async function admit(row:InpatientAdmission){try{await ElMessageBox.confirm(`确认为 ${row.patient_name} 办理入院？`,'办理入院');await admitPatient(row.id);ElMessage.success('入院办理完成');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}
async function discharge(row:InpatientAdmission){try{const{value}=await ElMessageBox.prompt('填写诊疗经过、出院情况和随访建议','办理出院',{inputType:'textarea',inputValidator:(text:string)=>Boolean(text&&text.trim())||'出院小结不能为空'});await dischargePatient(row.id,value.trim());ElMessage.success('出院办理完成');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}
function money(value?:string){return value===undefined?'—':`¥${Number(value).toFixed(2)}`}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">INPATIENT CARE</p><h1>{{isPatient?'我的住院记录':'住院管理'}}</h1><p>覆盖住院申请、床位信息、入院与出院小结，点击记录查看逐项费用清单</p></div><div class="heading-actions"><el-button v-if="canManage" @click="openBedBoard">床位总览</el-button><el-button v-if="canManage" type="primary" @click="open">＋ 住院申请</el-button></div></div>
    <el-card class="table-card">
      <div class="table-tools"><el-input v-model="state.search" clearable placeholder="搜索住院号、患者或诊断" @keyup.enter="searchAdmissions"/><el-select v-model="state.status" clearable placeholder="全部状态"><el-option label="待入院" value="pending"/><el-option label="住院中" value="admitted"/><el-option label="已出院" value="discharged"/><el-option label="已取消" value="cancelled"/></el-select><el-button @click="searchAdmissions">查询</el-button><span class="table-count">共 {{total}} 条</span><ViewSwitch v-model="state.view"/></div>
      <div class="legend-row"><StatusLegend domain="inpatient" title="住院状态"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="task-groups">
        <section v-for="group in groups" :key="group.key" class="task-group">
          <header class="task-group-head"><h2>{{group.info.label}}</h2><el-tag :type="group.info.tone" effect="plain">{{group.items.length}} 人</el-tag><span class="group-hint">{{group.key==='admitted'?'在院患者，办理出院需填写出院小结':group.key==='pending'?'待办理入院，可先核对床位与诊断':group.key==='discharged'?'历史住院记录，可查看费用清单':'已取消记录'}}</span></header>
          <div class="task-card-grid">
            <TaskCard v-for="row in group.items" :key="row.id" :time="(row.admitted_at||row.created_at)?.replace('T',' ').slice(0,16)" :title="isPatient?row.admission_no:row.patient_name" :subtitle="`${row.admission_no} · ${row.department_name} · ${row.doctor_name}`" :accent="group.info.tone" :highlight="row.status==='pending'" :meta="[{label:'床位',value:`${row.ward||'待分配'} / ${row.bed_no||'—'}`},{label:'入院诊断',value:row.admission_diagnosis},{label:'住院天数',value:row.status==='admitted'?`${row.days_admitted||0} 天`:(row.billable_days?`${row.billable_days} 天`:'—')},{label:'待付金额',value:money(row.charge_summary?.unpaid_amount)}]">
              <template #status><el-tag :type="group.info.tone">{{group.info.label}}</el-tag></template>
              <template #actions><el-button link type="primary" @click="openDetail(row)">详情与费用</el-button><el-button v-if="canManage&&row.status==='pending'" link type="primary" @click="admit(row)">办理入院</el-button><el-button v-if="canManage&&row.status==='admitted'" link type="success" @click="discharge(row)">办理出院</el-button></template>
            </TaskCard>
          </div>
        </section>
        <el-empty v-if="!rows.length&&!loading" description="暂无住院记录"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows" empty-text="暂无住院记录" class="desktop-table" @row-click="openDetail">
          <el-table-column prop="admission_no" label="住院号" min-width="150"/>
          <el-table-column v-if="!isPatient" prop="patient_name" label="患者"/>
          <el-table-column prop="department_name" label="科室"/>
          <el-table-column prop="doctor_name" label="主治医师"/>
          <el-table-column label="床位"><template #default="{row}">{{row.ward||'待分配'}} / {{row.bed_no||'—'}}</template></el-table-column>
          <el-table-column prop="admission_diagnosis" label="入院诊断" min-width="190" show-overflow-tooltip/>
          <el-table-column label="住院天数" width="100"><template #default="{row}">{{row.status==='admitted'?`${row.days_admitted||0} 天`:(row.billable_days?`${row.billable_days} 天`:'—')}}</template></el-table-column>
          <el-table-column label="已出账费用" width="130"><template #default="{row}"><b>{{money(row.charge_summary?.billed_amount)}}</b><small class="cell-sub">已付 {{money(row.charge_summary?.paid_amount)}}</small></template></el-table-column>
          <el-table-column label="待付金额" width="120"><template #default="{row}"><b class="cell-amount">{{money(row.charge_summary?.unpaid_amount)}}</b></template></el-table-column>
          <el-table-column label="预计床位费" width="140"><template #default="{row}"><span v-if="row.status==='admitted'">{{money(row.charge_summary?.projected_bed_fee)}}</span><span v-else-if="row.charge_summary?.bed_bill_generated">已固定出账</span><span v-else class="cell-empty">—</span><small v-if="row.status==='admitted'" class="cell-sub">{{money(row.daily_rate_snapshot)}} × {{row.billable_days}} 天</small></template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('inpatient',row.status).tone">{{statusInfo('inpatient',row.status).label}}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click.stop="openDetail(row)">详情</el-button><el-button v-if="canManage&&row.status==='pending'" link type="primary" @click.stop="admit(row)">办理入院</el-button><el-button v-if="canManage&&row.status==='admitted'" link type="success" @click.stop="discharge(row)">办理出院</el-button></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in rows" :key="row.id" class="mobile-info-card">
            <header><h3>{{isPatient?row.admission_no:row.patient_name}}</h3><el-tag :type="statusInfo('inpatient',row.status).tone">{{statusInfo('inpatient',row.status).label}}</el-tag></header>
            <p class="mobile-sub">{{row.admission_no}} · {{row.department_name}} · {{row.doctor_name}}</p>
            <div class="mobile-line"><span>床位</span><b>{{row.ward||'待分配'}} / {{row.bed_no||'—'}}</b></div>
            <div class="mobile-line"><span>入院诊断</span><b>{{row.admission_diagnosis}}</b></div>
            <div class="mobile-line"><span>待付金额</span><b>{{money(row.charge_summary?.unpaid_amount)}}</b></div>
            <div class="actions"><el-button link type="primary" @click="openDetail(row)">详情</el-button><el-button v-if="canManage&&row.status==='pending'" link type="primary" @click="admit(row)">办理入院</el-button><el-button v-if="canManage&&row.status==='admitted'" link type="success" @click="discharge(row)">办理出院</el-button></div>
          </article>
          <div v-if="!rows.length&&!loading" class="mobile-empty">暂无住院记录</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
    <el-dialog v-model="dialog" title="创建住院申请" width="min(650px,94vw)"><el-form label-position="top"><el-row :gutter="14"><el-col :span="12"><el-form-item label="患者" required><el-select v-model="form.patient_id" filterable style="width:100%"><el-option v-for="item in patients" :key="item.id" :label="`${item.full_name} · ${item.patient_no}`" :value="item.id"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="主治医师" required><el-select v-model="form.doctor_id" filterable style="width:100%"><el-option v-for="item in doctors" :key="item.id" :label="`${item.full_name} · ${item.title}`" :value="item.id"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="科室" required><el-select v-model="form.department_id" style="width:100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="可用床位" required><el-select v-model="form.bed_id" filterable clearable :disabled="!form.department_id" style="width:100%" placeholder="请先选择科室"><el-option v-for="bed in beds" :key="bed.id" :label="`${bed.ward_name} · ${bed.bed_no}（¥${bed.daily_rate}/日）`" :value="bed.id"/></el-select><small v-if="form.department_id&&!beds.length">该科室暂无空闲床位，请先在床位配置中添加床位。</small></el-form-item></el-col></el-row><el-form-item label="入院诊断" required><el-input v-model="form.admission_diagnosis" type="textarea" :rows="3"/></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交申请</el-button></template></el-dialog>
  </section>
</template>
