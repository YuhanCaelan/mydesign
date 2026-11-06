<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage}from'element-plus'
import{statusInfo}from'../../utils/status'
import{registerEmergency,getPatientsForStaff,getDoctorsForStaff,receiveInpatient,getInpatientOrders,executeInpatientOrder}from'../../services/clinical'
import{getInpatients}from'../../services/operations'
import type{DoctorSummary,InpatientAdmission,InpatientOrder,PatientSummary}from'../../types/medical'

const patients=ref<PatientSummary[]>([]),doctors=ref<DoctorSummary[]>([]),admissions=ref<InpatientAdmission[]>([])
const loading=ref(false),saving=ref(false),activeTab=ref<'emergency'|'receive'|'orders'>('emergency')
const emergency=reactive({patient_id:undefined as number|undefined,doctor_id:undefined as number|undefined,triage_level:3,reason:''})
const selectedAdmission=ref<number|undefined>(),longOrders=ref<InpatientOrder[]>([]),shortOrders=ref<InpatientOrder[]>([]),ordersLoading=ref(false)
const pendingReceive=computed(()=>admissions.value.filter(item=>!item.received_at))
const selectedAdmissionInfo=computed(()=>admissions.value.find(item=>item.id===selectedAdmission.value)||null)

async function load(){loading.value=true;try{const[patientData,doctorData,admissionData]=await Promise.all([getPatientsForStaff(''),getDoctorsForStaff(),getInpatients({status:'admitted',page_size:100})]);patients.value=patientData.results;doctors.value=doctorData.results;admissions.value=admissionData.results}catch(error:any){ElMessage.error(error.response?.data?.detail||'护理工作台数据加载失败')}finally{loading.value=false}}
async function submitEmergency(){if(!emergency.patient_id||!emergency.doctor_id||!emergency.reason.trim()){ElMessage.warning('请选择患者、急诊医师并填写就诊原因');return}saving.value=true;try{await registerEmergency({patient_id:emergency.patient_id,doctor_id:emergency.doctor_id,triage_level:emergency.triage_level,reason:emergency.reason});ElMessage.success('急诊登记完成，已进入医生接诊队列');Object.assign(emergency,{patient_id:undefined,doctor_id:undefined,triage_level:3,reason:''})}catch(error:any){ElMessage.error(error.response?.data?.detail||'急诊登记失败')}finally{saving.value=false}}
async function receive(row:InpatientAdmission){try{await receiveInpatient(row.id);ElMessage.success('住院接诊完成');await load()}catch(error:any){ElMessage.error(error.response?.data?.detail||'接诊失败')}}
async function loadOrders(){if(!selectedAdmission.value){longOrders.value=[];shortOrders.value=[];return}ordersLoading.value=true;try{const[long,short]=await Promise.all([getInpatientOrders(selectedAdmission.value,'long'),getInpatientOrders(selectedAdmission.value,'temp')]);longOrders.value=long.results;shortOrders.value=short.results}catch(error:any){ElMessage.error(error.response?.data?.detail||'医嘱加载失败')}finally{ordersLoading.value=false}}
async function execute(order:InpatientOrder){try{await executeInpatientOrder(order.admission,order.id,'护士执行');ElMessage.success('医嘱已执行');await loadOrders()}catch(error:any){ElMessage.error(error.response?.data?.detail||'执行失败')}}
onMounted(load)
</script>

<template>
  <section v-loading="loading">
    <div class="page-heading"><div><p class="eyebrow">NURSING WORKSPACE</p><h1>护理工作台</h1><p>急诊分诊登记、住院接诊与医嘱执行；不参与医生病历和开单</p></div><el-button @click="load">刷新</el-button></div>
    <el-tabs v-model="activeTab" class="nurse-tabs">
      <el-tab-pane label="急诊登记" name="emergency">
        <el-card><template #header><div class="section-head"><div><h2>急诊现场登记</h2><p>急诊不预约，登记后直接进入医生接诊队列</p></div></div></template>
          <el-form label-position="top" class="nurse-form">
            <el-row :gutter="14">
              <el-col :md="12"><el-form-item label="患者" required><el-select v-model="emergency.patient_id" filterable style="width:100%" placeholder="搜索姓名 / 患者号"><el-option v-for="patient in patients" :key="patient.id" :value="patient.id" :label="`${patient.full_name} · ${patient.patient_no} · ${patient.phone||''}`"/></el-select></el-form-item></el-col>
              <el-col :md="12"><el-form-item label="急诊医师" required><el-select v-model="emergency.doctor_id" filterable style="width:100%"><el-option v-for="doctor in doctors" :key="doctor.id" :value="doctor.id" :label="`${doctor.full_name} · ${doctor.department_name}`"/></el-select></el-form-item></el-col>
              <el-col :md="8"><el-form-item label="分诊级别" required><el-select v-model="emergency.triage_level" style="width:100%"><el-option :value="1" label="1 级 · 濒危"/><el-option :value="2" label="2 级 · 危重"/><el-option :value="3" label="3 级 · 急症"/><el-option :value="4" label="4 级 · 非急症"/></el-select></el-form-item></el-col>
              <el-col :md="16"><el-form-item label="就诊原因" required><el-input v-model="emergency.reason" type="textarea" :rows="2" placeholder="如：突发胸痛 30 分钟"/></el-form-item></el-col>
            </el-row>
            <el-button type="primary" :loading="saving" @click="submitEmergency">登记急诊</el-button>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="receive">
        <template #label><span>住院接诊</span><em class="tab-count">{{pendingReceive.length}}</em></template>
        <el-card><template #header><div class="section-head"><div><h2>待接诊患者</h2><p>住院处办理入院后，由护士完成接诊与护理评估</p></div></div></template>
          <el-table :data="pendingReceive" empty-text="暂无待接诊患者"><el-table-column prop="admission_no" label="住院号" min-width="140"/><el-table-column prop="patient_name" label="患者" min-width="100"/><el-table-column prop="department_name" label="科室" min-width="110"/><el-table-column label="床位" min-width="100"><template #default="{row}">{{row.ward}} {{row.bed_no}}</template></el-table-column><el-table-column prop="admission_diagnosis" label="入院诊断" min-width="180"/><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="receive(row)">接诊</el-button></template></el-table-column></el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="医嘱执行" name="orders">
        <el-card><template #header><div class="section-head"><div><h2>住院医嘱执行</h2><p>长期医嘱与临时医嘱分开显示，执行后记录执行人</p></div><el-select v-model="selectedAdmission" filterable style="width:260px" placeholder="选择住院患者" @change="loadOrders"><el-option v-for="item in admissions" :key="item.id" :value="item.id" :label="`${item.patient_name} · ${item.admission_no}`"/></el-select></div></template>
          <p v-if="selectedAdmissionInfo" class="clinic-dialog-sub">{{selectedAdmissionInfo.patient_name}} · {{selectedAdmissionInfo.ward}} {{selectedAdmissionInfo.bed_no}} · {{selectedAdmissionInfo.admission_diagnosis}}</p>
          <div v-loading="ordersLoading" class="staff-columns">
            <section><h3 class="staff-subtitle">长期医嘱</h3><el-table :data="longOrders" empty-text="暂无长期医嘱"><el-table-column prop="content" label="医嘱内容" min-width="180"/><el-table-column prop="dosage" label="剂量" width="90"/><el-table-column prop="frequency" label="频次" width="100"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('procedure',row.status==='completed'?'completed':'requested').tone">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="操作" width="90"><template #default="{row}"><el-button v-if="row.status==='submitted'" link type="primary" @click="execute(row)">执行</el-button></template></el-table-column></el-table></section>
            <section><h3 class="staff-subtitle">临时医嘱</h3><el-table :data="shortOrders" empty-text="暂无临时医嘱"><el-table-column prop="content" label="医嘱内容" min-width="180"/><el-table-column prop="dosage" label="剂量" width="90"/><el-table-column prop="frequency" label="频次" width="100"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('procedure',row.status==='completed'?'completed':'requested').tone">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="操作" width="90"><template #default="{row}"><el-button v-if="row.status==='submitted'" link type="primary" @click="execute(row)">执行</el-button></template></el-table-column></el-table></section>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
