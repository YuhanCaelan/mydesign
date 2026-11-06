<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{useRoute,useRouter}from'vue-router'
import{ElMessage}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import{statusInfo}from'../../utils/status'
import{getInpatient}from'../../services/operations'
import{getInpatientRecord,saveInpatientRecord,getInpatientOrders,createInpatientOrder,executeInpatientOrder,stopInpatientOrder}from'../../services/clinical'
import type{InpatientAdmission,InpatientOrder,InpatientRecord}from'../../types/medical'

const auth=useAuthStore(),route=useRoute(),router=useRouter()
const isDoctor=computed(()=>auth.user?.role==='doctor'),isNurse=computed(()=>auth.user?.role==='nurse')
const admissionId=computed(()=>Number(route.params.admissionId))
const admission=ref<InpatientAdmission|null>(null),record=ref<InpatientRecord|null>(null),longOrders=ref<InpatientOrder[]>([]),shortOrders=ref<InpatientOrder[]>([]),loading=ref(false),saving=ref(false),activeTab=ref<'record'|'long'|'temp'>('record')
const recordForm=reactive<InpatientRecord>({chief_complaint:'',present_illness:'',past_history:'',physical_exam:'',diagnosis:'',course:'',discharge_summary:''})
const orderForm=reactive<{order_type:'long'|'temp';category:InpatientOrder['category'];content:string;dosage:string;frequency:string}>({order_type:'temp',category:'medication',content:'',dosage:'',frequency:''})

async function load(){loading.value=true;try{admission.value=await getInpatient(admissionId.value);const recordData=await getInpatientRecord(admissionId.value);record.value=recordData.record;if(record.value)Object.assign(recordForm,record.value);await loadOrders()}catch(error:any){ElMessage.error(error.response?.data?.detail||'住院工作区加载失败')}finally{loading.value=false}}
async function loadOrders(){if(!admissionId.value)return;const[long,short]=await Promise.all([getInpatientOrders(admissionId.value,'long'),getInpatientOrders(admissionId.value,'temp')]);longOrders.value=long.results;shortOrders.value=short.results}
async function saveRecord(){saving.value=true;try{const data=await saveInpatientRecord(admissionId.value,recordForm);record.value=data.record;ElMessage.success('住院病志已保存')}catch(error:any){ElMessage.error(error.response?.data?.detail||'病志保存失败')}finally{saving.value=false}}
async function addOrder(type:'long'|'temp'){orderForm.order_type=type;activeTab.value=type;if(!orderForm.content.trim()){ElMessage.warning('请填写医嘱内容');return}saving.value=true;try{await createInpatientOrder(admissionId.value,{...orderForm});ElMessage.success('医嘱已提交');orderForm.content='';orderForm.dosage='';orderForm.frequency='';await loadOrders()}catch(error:any){ElMessage.error(error.response?.data?.detail||'医嘱提交失败')}finally{saving.value=false}}
async function execute(order:InpatientOrder){try{await executeInpatientOrder(admissionId.value,order.id,'护士执行');ElMessage.success('医嘱已执行');await loadOrders()}catch(error:any){ElMessage.error(error.response?.data?.detail||'执行失败')}}
async function stop(order:InpatientOrder){try{await stopInpatientOrder(admissionId.value,order.id);ElMessage.success('长期医嘱已停止');await loadOrders()}catch(error:any){ElMessage.error(error.response?.data?.detail||'停止失败')}}
function time(value?:string|null){return value?.replace('T',' ').slice(0,16)||'—'}
onMounted(load)
</script>

<template>
  <section v-loading="loading">
    <div class="page-heading"><div><el-button link @click="router.back()">← 返回</el-button><h1>{{isNurse?'住院护理':'住院病志与医嘱'}}</h1><p v-if="admission">{{admission.admission_no}} · {{admission.patient_name}} · {{admission.department_name}} · {{admission.ward}} {{admission.bed_no}}</p></div><div v-if="admission" class="visit-actions"><el-tag :type="statusInfo('inpatient',admission.status).tone">{{statusInfo('inpatient',admission.status).label}}</el-tag><el-tag :type="admission.received_at?'success':'warning'">{{admission.received_at?'护士已接诊':'待护士接诊'}}</el-tag><el-button @click="load">刷新</el-button></div></div>
    <template v-if="admission">
      <div class="patient-band"><div><span>患者</span><strong>{{admission.patient_name}}</strong><small>{{admission.patient_no}} · {{admission.admission_diagnosis}}</small></div><div><span>主治医师</span><b>{{admission.doctor_name}}</b></div><div><span>床位</span><b>{{admission.ward}} {{admission.bed_no}}</b></div><div><span>接诊护士</span><b>{{admission.receiving_nurse_name||'待接诊'}}</b></div></div>
      <el-card class="visit-tabs-card">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="住院病志" name="record">
            <div class="editor-head"><div><h2>住院病志</h2><p>一次住院一份病志，与门诊病历分开</p></div><el-button v-if="isDoctor&&record" plain @click="saveRecord" :loading="saving">保存病志</el-button></div>
            <el-form label-position="top" :disabled="!isDoctor">
              <el-row :gutter="14"><el-col :md="12"><el-form-item label="主诉"><el-input v-model="recordForm.chief_complaint" type="textarea" :rows="2"/></el-form-item></el-col><el-col :md="12"><el-form-item label="现病史"><el-input v-model="recordForm.present_illness" type="textarea" :rows="2"/></el-form-item></el-col><el-col :md="12"><el-form-item label="既往史"><el-input v-model="recordForm.past_history" type="textarea" :rows="2"/></el-form-item></el-col><el-col :md="12"><el-form-item label="体格检查"><el-input v-model="recordForm.physical_exam" type="textarea" :rows="2"/></el-form-item></el-col></el-row>
              <el-form-item label="诊断"><el-input v-model="recordForm.diagnosis" type="textarea" :rows="2"/></el-form-item>
              <el-form-item label="病程记录"><el-input v-model="recordForm.course" type="textarea" :rows="3"/></el-form-item>
              <el-form-item label="出院小结"><el-input v-model="recordForm.discharge_summary" type="textarea" :rows="2"/></el-form-item>
              <el-button v-if="isDoctor&&!record" type="primary" @click="saveRecord">创建病志</el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane :label="`长期医嘱 ${longOrders.length}`" name="long">
            <div class="editor-head"><div><h2>长期医嘱</h2><p>持续执行，医生可停止</p></div></div>
            <div v-if="isDoctor" class="order-entry"><el-input v-model="orderForm.content" placeholder="医嘱内容，如：低盐低脂饮食"/><el-input v-model="orderForm.dosage" placeholder="剂量"/><el-input v-model="orderForm.frequency" placeholder="频次"/><el-button type="primary" :loading="saving" @click="addOrder('long')">提交长期医嘱</el-button></div>
            <el-table :data="longOrders" empty-text="暂无长期医嘱"><el-table-column prop="content" label="医嘱内容" min-width="220"/><el-table-column prop="dosage" label="剂量" width="100"/><el-table-column prop="frequency" label="频次" width="120"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="row.status==='completed'?'success':row.status==='stopped'?'info':'warning'">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="执行" min-width="150"><template #default="{row}">{{row.executor_name||'—'}}<small v-if="row.executed_at" class="cell-sub">{{time(row.executed_at)}}</small></template></el-table-column><el-table-column label="操作" width="150"><template #default="{row}"><el-button v-if="isNurse&&row.status==='submitted'" link type="primary" @click="execute(row)">执行</el-button><el-button v-if="isDoctor&&row.status!=='stopped'" link type="danger" @click="stop(row)">停止</el-button></template></el-table-column></el-table>
          </el-tab-pane>
          <el-tab-pane :label="`临时医嘱 ${shortOrders.length}`" name="temp">
            <div class="editor-head"><div><h2>临时医嘱</h2><p>一次性执行，护士确认后归档</p></div></div>
            <div v-if="isDoctor" class="order-entry"><el-input v-model="orderForm.content" placeholder="医嘱内容，如：血常规"/><el-input v-model="orderForm.dosage" placeholder="剂量"/><el-input v-model="orderForm.frequency" placeholder="频次"/><el-button type="primary" :loading="saving" @click="addOrder('temp')">提交临时医嘱</el-button></div>
            <el-table :data="shortOrders" empty-text="暂无临时医嘱"><el-table-column prop="content" label="医嘱内容" min-width="220"/><el-table-column prop="dosage" label="剂量" width="100"/><el-table-column prop="frequency" label="频次" width="120"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="row.status==='completed'?'success':'warning'">{{row.status_display}}</el-tag></template></el-table-column><el-table-column label="执行" min-width="150"><template #default="{row}">{{row.executor_name||'—'}}<small v-if="row.executed_at" class="cell-sub">{{time(row.executed_at)}}</small></template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button v-if="isNurse&&row.status==='submitted'" link type="primary" @click="execute(row)">执行</el-button></template></el-table-column></el-table>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </template>
  </section>
</template>
