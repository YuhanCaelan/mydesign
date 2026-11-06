<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import{statusInfo}from'../../utils/status'
import{admitPatient,dischargePatient,getInpatients,getWardBeds,getBills,payBill}from'../../services/operations'
import{createSchedule,getDoctorsAdmin,getSchedules}from'../../services/admin'
import{assignInpatientBed,getProcedures,startProcedure,completeProcedure,dispensePrescription,refundBill}from'../../services/clinical'
import{getPrescriptions}from'../../services/prescriptions'
import{getExaminations,startExamination}from'../../services/examinations'
import type{BillingRecord,DoctorScheduleSummary,DoctorSummary,ExaminationOrder,InpatientAdmission,Prescription,ProcedureOrder,WardBed}from'../../types/medical'

const auth=useAuthStore()
const station=auth.user?.station||''
const stationLabel=computed(()=>{const labels:Record<string,string>={schedule:'科室排班',admission:'住院处',cashier:'收费退费',pharmacy:'药房发药',execution:'医技执行'};return labels[station]||'岗位工作台'})
const loading=ref(false),schedules=ref<DoctorScheduleSummary[]>([]),doctors=ref<DoctorSummary[]>([])
const scheduleOpen=ref(false),scheduleSaving=ref(false)
const scheduleForm=reactive({doctor:undefined as number|undefined,date:'',start_time:'09:00:00',end_time:'10:00:00',slot_minutes:30})

const admissions=ref<InpatientAdmission[]>([]),admitted=ref<InpatientAdmission[]>([]),beds=ref<WardBed[]>([]),bedDialog=ref(false),currentAdmission=ref<InpatientAdmission|null>(null),selectedBed=ref<number|undefined>(),admissionSaving=ref(false)
const bills=ref<BillingRecord[]>([]),paidBills=ref<BillingRecord[]>([]),billSearch=ref('')
const prescriptions=ref<Prescription[]>([]),examinations=ref<ExaminationOrder[]>([]),procedures=ref<ProcedureOrder[]>([])

async function loadSchedules(){loading.value=true;try{schedules.value=(await getSchedules({page_size:100})).results;doctors.value=await getDoctorsAdmin({department:auth.user?.department_id,page_size:100})}catch(e:any){ElMessage.error(e.response?.data?.detail||'排班加载失败')}finally{loading.value=false}}
function openSchedule(){Object.assign(scheduleForm,{doctor:doctors.value[0]?.id,date:'',start_time:'09:00:00',end_time:'10:00:00',slot_minutes:30});scheduleOpen.value=true}
async function submitSchedule(){const doctor=scheduleForm.doctor;if(!doctor||!scheduleForm.date){ElMessage.warning('请选择医师与日期');return}scheduleSaving.value=true;try{await createSchedule({...scheduleForm,doctor});ElMessage.success('排班已创建');scheduleOpen.value=false;await loadSchedules()}catch(e:any){ElMessage.error(e.response?.data?.detail||'排班创建失败')}finally{scheduleSaving.value=false}}
function stockSummary(row:Prescription){return row.items?.map(item=>`${item.medicine_name}×${item.quantity}（库存${item.stock}）`).join('、')||'—'}

async function loadAdmissions(){loading.value=true;try{admissions.value=(await getInpatients({status:'pending',page_size:50})).results;admitted.value=(await getInpatients({status:'admitted',page_size:50})).results}catch(e:any){ElMessage.error(e.response?.data?.detail||'住院处数据加载失败')}finally{loading.value=false}}
async function openAdmit(row:InpatientAdmission){currentAdmission.value=row;selectedBed.value=undefined;beds.value=[];bedDialog.value=true;try{beds.value=(await getWardBeds({department:row.department_id,available:true,page_size:100})).results}catch{beds.value=[]}}
async function confirmAdmit(){if(!currentAdmission.value||!selectedBed.value){ElMessage.warning('请选择床位');return}admissionSaving.value=true;try{await assignInpatientBed(currentAdmission.value.id,selectedBed.value);await admitPatient(currentAdmission.value.id);ElMessage.success('已分配床位并办理入院');bedDialog.value=false;await loadAdmissions()}catch(e:any){ElMessage.error(e.response?.data?.detail||'入院办理失败')}finally{admissionSaving.value=false}}
async function discharge(row:InpatientAdmission){try{const{value}=await ElMessageBox.prompt('填写出院小结','办理出院',{inputType:'textarea',inputValidator:(text:string)=>Boolean(text&&text.trim())||'出院小结不能为空'});await dischargePatient(row.id,value.trim());ElMessage.success('出院办理完成');await loadAdmissions()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}

async function loadCashier(){loading.value=true;try{const[unpaid,paid]=await Promise.all([getBills({status:'unpaid',search:billSearch.value||undefined,page_size:50}),getBills({status:'paid',search:billSearch.value||undefined,page_size:50})]);bills.value=unpaid.results;paidBills.value=paid.results}catch(e:any){ElMessage.error(e.response?.data?.detail||'账单加载失败')}finally{loading.value=false}}
async function collect(row:BillingRecord){try{await ElMessageBox.confirm(`确认收取 ¥${row.amount}？`,'收费确认',{type:'info'});await payBill(row.id);ElMessage.success('收费完成');await loadCashier()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'收费失败')}}
async function refund(row:BillingRecord){try{const{value}=await ElMessageBox.prompt('请填写退费原因','门诊退费',{inputType:'textarea',inputValidator:(text:string)=>Boolean(text&&text.trim())||'退费原因不能为空'});await refundBill(row.id,value.trim());ElMessage.success('退费完成，关联医嘱已取消');await loadCashier()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'退费失败')}}

async function loadPharmacy(){loading.value=true;try{prescriptions.value=(await getPrescriptions({payment_status:'paid',status:'issued',page_size:50})).results}catch(e:any){ElMessage.error(e.response?.data?.detail||'发药队列加载失败')}finally{loading.value=false}}
async function dispense(row:Prescription){try{await ElMessageBox.confirm(`确认发药：${row.items?.map(item=>item.medicine_name).join('、')}？发药后将扣减库存。`,'药房发药',{type:'warning'});await dispensePrescription(row.id);ElMessage.success('发药完成');await loadPharmacy()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'发药失败')}}

async function loadExecution(){loading.value=true;try{const[exams,procs]=await Promise.all([getExaminations({payment_status:'paid',page_size:50}),getProcedures({payment_status:'paid',page_size:50})]);examinations.value=exams.results.filter(row=>['requested','in_progress'].includes(row.status));procedures.value=procs.results.filter(row=>['requested','in_progress'].includes(row.status))}catch(e:any){ElMessage.error(e.response?.data?.detail||'执行队列加载失败')}finally{loading.value=false}}
async function startExam(row:ExaminationOrder){try{await startExamination(row.id);ElMessage.success('已确认开始检查');await loadExecution()}catch(e:any){ElMessage.error(e.response?.data?.detail||'操作失败')}}
async function startProc(row:ProcedureOrder){try{await startProcedure(row.id);ElMessage.success('处置已开始');await loadExecution()}catch(e:any){ElMessage.error(e.response?.data?.detail||'操作失败')}}
async function completeProc(row:ProcedureOrder){try{await completeProcedure(row.id);ElMessage.success('处置已完成');await loadExecution()}catch(e:any){ElMessage.error(e.response?.data?.detail||'操作失败')}}

onMounted(()=>{if(station==='schedule')loadSchedules();else if(station==='admission')loadAdmissions();else if(station==='cashier')loadCashier();else if(station==='pharmacy')loadPharmacy();else if(station==='execution')loadExecution()})
</script>

<template>
  <section v-loading="loading">
    <div class="page-heading">
      <div><p class="eyebrow">STAFF WORKSPACE</p><h1>{{stationLabel}}</h1><p>{{auth.user?.department_name||'未绑定科室'}} · 当前岗位职责内的业务操作</p></div>
      <el-button @click="station==='schedule'?loadSchedules():station==='admission'?loadAdmissions():station==='cashier'?loadCashier():station==='pharmacy'?loadPharmacy():loadExecution()">刷新</el-button>
    </div>

    <template v-if="station==='schedule'">
      <el-card class="table-card"><template #header><div class="section-head"><div><h2>本科室排班</h2><p>仅可维护所属科室医师的排班与号源</p></div><el-button type="primary" @click="openSchedule">＋ 新建排班</el-button></div></template>
        <el-table :data="schedules" empty-text="暂无排班"><el-table-column label="日期" width="120"><template #default="{row}">{{row.date}}</template></el-table-column><el-table-column label="医师" min-width="150"><template #default="{row}">{{row.doctor_name}}</template></el-table-column><el-table-column label="时段" min-width="160"><template #default="{row}">{{row.start_time?.slice(0,5)}}–{{row.end_time?.slice(0,5)}}</template></el-table-column><el-table-column prop="slot_minutes" label="号源间隔" width="100"/><el-table-column prop="available_slots" label="可约" width="90"/><el-table-column prop="booked_slots" label="已约" width="90"/><el-table-column label="状态" width="90"><template #default="{row}"><el-tag :type="row.is_active?'success':'info'">{{row.is_active?'启用':'停用'}}</el-tag></template></el-table-column></el-table>
      </el-card>
      <el-dialog v-model="scheduleOpen" title="新建排班" width="min(520px,94vw)"><el-form label-position="top"><el-form-item label="医师" required><el-select v-model="scheduleForm.doctor" filterable style="width:100%"><el-option v-for="doctor in doctors" :key="doctor.id" :value="doctor.id" :label="`${doctor.full_name} · ${doctor.title||doctor.specialty}`"/></el-select></el-form-item><el-form-item label="日期" required><el-date-picker v-model="scheduleForm.date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item><el-row :gutter="12"><el-col :span="12"><el-form-item label="开始时间"><el-time-picker v-model="scheduleForm.start_time" value-format="HH:mm:ss" style="width:100%"/></el-form-item></el-col><el-col :span="12"><el-form-item label="结束时间"><el-time-picker v-model="scheduleForm.end_time" value-format="HH:mm:ss" style="width:100%"/></el-form-item></el-col></el-row><el-form-item label="号源间隔（分钟）"><el-input-number v-model="scheduleForm.slot_minutes" :min="5" :max="120"/></el-form-item></el-form><template #footer><el-button @click="scheduleOpen=false">取消</el-button><el-button type="primary" :loading="scheduleSaving" @click="submitSchedule">创建排班</el-button></template></el-dialog>
    </template>

    <template v-else-if="station==='admission'">
      <div class="staff-columns">
        <el-card><template #header><div class="section-head"><div><h2>待入院</h2><p>医生已提交，等待分床与办理入院</p></div><span class="table-count">{{admissions.length}} 人</span></div></template>
          <el-table :data="admissions" empty-text="暂无待入院"><el-table-column prop="admission_no" label="住院号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="department_name" label="科室" min-width="110"/><el-table-column prop="admission_diagnosis" label="入院诊断" min-width="180" show-overflow-tooltip/><el-table-column label="操作" width="150"><template #default="{row}"><el-button link type="primary" @click="openAdmit(row)">分床并入院</el-button></template></el-table-column></el-table>
        </el-card>
        <el-card><template #header><div class="section-head"><div><h2>在院患者</h2><p>出院由住院处结算</p></div><span class="table-count">{{admitted.length}} 人</span></div></template>
          <el-table :data="admitted" empty-text="暂无在院患者"><el-table-column prop="admission_no" label="住院号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column label="床位" min-width="100"><template #default="{row}">{{row.ward}} {{row.bed_no}}</template></el-table-column><el-table-column label="护士接诊" width="110"><template #default="{row}"><el-tag :type="row.received_at?'success':'warning'">{{row.received_at?'已接诊':'待接诊'}}</el-tag></template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="success" @click="discharge(row)">出院</el-button></template></el-table-column></el-table>
        </el-card>
      </div>
      <el-dialog v-model="bedDialog" title="分床并办理入院" width="min(520px,94vw)"><p v-if="currentAdmission" class="clinic-dialog-sub">{{currentAdmission.patient_name}} · {{currentAdmission.department_name}} · {{currentAdmission.admission_diagnosis}}</p><el-select v-model="selectedBed" filterable style="width:100%" placeholder="选择空闲床位"><el-option v-for="bed in beds" :key="bed.id" :value="bed.id" :label="`${bed.ward_name} · ${bed.bed_no} · ¥${bed.daily_rate}/日`"/></el-select><el-empty v-if="!beds.length" :image-size="60" description="本科室暂无空闲床位"/><template #footer><el-button @click="bedDialog=false">取消</el-button><el-button type="primary" :loading="admissionSaving" :disabled="!selectedBed" @click="confirmAdmit">分配并入院</el-button></template></el-dialog>
    </template>

    <template v-else-if="station==='cashier'">
      <el-card><template #header><div class="section-head"><div><h2>收费与退费</h2><p>输入患者姓名或账单号搜索；退费仅限已缴费且未执行/未发药</p></div><div class="heading-actions"><el-input v-model="billSearch" clearable placeholder="患者 / 账单号" style="width:220px" @keyup.enter="loadCashier"/><el-button @click="loadCashier">搜索</el-button></div></div></template>
        <h3 class="staff-subtitle">待缴费 {{bills.length}} 张</h3>
        <el-table :data="bills" empty-text="暂无待缴费账单"><el-table-column prop="bill_no" label="账单号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="description" label="项目" min-width="200" show-overflow-tooltip/><el-table-column label="金额" width="100"><template #default="{row}">¥{{row.amount}}</template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="success" @click="collect(row)">收费</el-button></template></el-table-column></el-table>
        <h3 class="staff-subtitle">已缴费 {{paidBills.length}} 张</h3>
        <el-table :data="paidBills" empty-text="暂无已缴费账单"><el-table-column prop="bill_no" label="账单号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="description" label="项目" min-width="200" show-overflow-tooltip/><el-table-column label="金额" width="100"><template #default="{row}">¥{{row.amount}}</template></el-table-column><el-table-column label="操作" width="110"><template #default="{row}"><el-button link type="danger" @click="refund(row)">退费</el-button></template></el-table-column></el-table>
      </el-card>
    </template>

    <template v-else-if="station==='pharmacy'">
      <el-card><template #header><div class="section-head"><div><h2>待发药处方</h2><p>仅已缴费处方进入队列；发药时扣减库存</p></div><span class="table-count">{{prescriptions.length}} 张</span></div></template>
        <el-table :data="prescriptions" empty-text="暂无待发药处方"><el-table-column prop="prescription_no" label="处方号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column label="药品" min-width="220"><template #default="{row}">{{stockSummary(row)}}</template></el-table-column><el-table-column label="金额" width="100"><template #default="{row}">¥{{row.total_amount}}</template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="dispense(row)">确认发药</el-button></template></el-table-column></el-table>
      </el-card>
    </template>

    <template v-else-if="station==='execution'">
      <el-card><template #header><div class="section-head"><div><h2>检查执行</h2><p>仅已缴费检查可确认开始</p></div><span class="table-count">{{examinations.length}} 项</span></div></template>
        <el-table :data="examinations" empty-text="暂无待执行检查"><el-table-column prop="order_no" label="申请单号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="item_name_snapshot" label="项目" min-width="150"/><el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusInfo('examination',row.status).tone">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button v-if="row.status==='requested'" link type="primary" @click="startExam(row)">开始检查</el-button></template></el-table-column></el-table>
        <h3 class="staff-subtitle">处置执行 {{procedures.length}} 项</h3>
        <el-table :data="procedures" empty-text="暂无待执行处置"><el-table-column prop="order_no" label="处置单号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="item_name_snapshot" label="项目" min-width="150"/><el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusInfo('procedure',row.status).tone">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="操作" width="150"><template #default="{row}"><el-button v-if="row.status==='requested'" link type="primary" @click="startProc(row)">开始</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="completeProc(row)">完成</el-button></template></el-table-column></el-table>
      </el-card>
    </template>

    <el-empty v-else description="当前账号未分配岗位，请联系系统管理员"/>
  </section>
</template>
