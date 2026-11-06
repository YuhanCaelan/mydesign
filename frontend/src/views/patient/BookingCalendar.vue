<script setup lang="ts">
import {computed,onMounted,reactive,ref} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {ElMessage,ElMessageBox} from 'element-plus'
import ScheduleCalendar from '../../components/schedules/ScheduleCalendar.vue'
import ListError from '../../components/common/ListError.vue'
import {getAllSchedules,getAllScheduleDoctors,getAllScheduleDepartments,type Schedule} from '../../services/admin'
import {createAppointment,getSlots} from '../../services/appointments'
import {clearListState} from '../../composables/useListState'
import {localDate} from '../../utils/scheduleCalendar'
import type {Appointment,AppointmentSlot,Department,DoctorSummary} from '../../types/medical'

const route=useRoute(),router=useRouter(),today=localDate()
function queryId(value:unknown){const id=Number(value);return Number.isInteger(id)&&id>0?id:undefined}
const calendar=reactive({month:today.slice(0,7),selectedDate:today,department:queryId(route.query.department),doctor:queryId(route.query.doctor),status:''})
const rows=ref<Schedule[]>([]),doctors=ref<DoctorSummary[]>([]),departments=ref<Department[]>([])
const loading=ref(false),error=ref(''),dialog=ref(false),submitting=ref(false),slotsLoading=ref(false),slotsError=ref('')
const selectedSchedule=ref<Schedule|null>(null),slots=ref<AppointmentSlot[]>([]),success=ref<Appointment|null>(null)
const booking=reactive({slot:undefined as number|undefined,reason:''})
const selectedSlot=computed(()=>slots.value.find(slot=>slot.id===booking.slot))
let loadVersion=0,slotsVersion=0

function errorText(error:any,fallback:string){
  function messages(value:unknown):string[]{
    if(typeof value==='string')return[value]
    if(Array.isArray(value))return value.flatMap(messages)
    if(value&&typeof value==='object')return Object.values(value).flatMap(messages)
    return[]
  }
  return messages(error.response?.data?.errors).join('；')||error.response?.data?.detail||fallback
}
async function load(){
  const version=++loadVersion;loading.value=true;error.value=''
  try{
    const [schedules,doctorOptions,departmentOptions]=await Promise.all([getAllSchedules(),getAllScheduleDoctors(),getAllScheduleDepartments()])
    if(version!==loadVersion)return
    rows.value=schedules;doctors.value=doctorOptions.filter(doctor=>doctor.is_available!==false);departments.value=departmentOptions
  }catch(e){if(version===loadVersion){rows.value=[];error.value=errorText(e,'排班日历加载失败，请重试')}}
  finally{if(version===loadVersion)loading.value=false}
}
function isFutureSlot(slot:AppointmentSlot){return new Date(`${slot.date}T${slot.start_time}`).getTime()>Date.now()}
async function loadSlots(){
  const schedule=selectedSchedule.value;if(!schedule)return
  const version=++slotsVersion;slotsLoading.value=true;slotsError.value='';slots.value=[];booking.slot=undefined
  try{
    const result=await getSlots(schedule.doctor,schedule.date,schedule.id)
    if(version===slotsVersion)slots.value=result.filter(slot=>slot.schedule_id===schedule.id&&slot.status==='available'&&isFutureSlot(slot))
  }catch(e){if(version===slotsVersion)slotsError.value=errorText(e,'号源加载失败，请重试')}
  finally{if(version===slotsVersion)slotsLoading.value=false}
}
async function reserve(schedule:Schedule){
  if(submitting.value)return
  selectedSchedule.value=schedule;booking.reason='';success.value=null;dialog.value=true
  await loadSlots()
}
function closeDialog(){slotsVersion++;slots.value=[];slotsLoading.value=false;booking.slot=undefined}
function viewAppointments(){if(success.value)clearListState('appointments-patient');router.push({path:'/patient/visits',query:{tab:'appointments'}})}
async function submit(){
  const slot=selectedSlot.value,schedule=selectedSchedule.value
  if(submitting.value||!slot||!schedule||!booking.reason.trim())return
  if(!isFutureSlot(slot)){ElMessage.warning('该号源已开始，请重新选择');await loadSlots();await load();return}
  submitting.value=true
  try{
    try{await ElMessageBox.confirm(`${schedule.department_name} · ${schedule.doctor_name}\n${schedule.date} ${slot.start_time.slice(0,5)}–${slot.end_time.slice(0,5)}\n就诊原因：${booking.reason.trim()}`,'确认预约信息',{confirmButtonText:'确认预约',cancelButtonText:'返回修改',type:'info'})}catch{return}
    try{
      success.value=await createAppointment({slot_id:slot.id,reason:booking.reason.trim()})
      dialog.value=false;ElMessage.success('预约成功');await load()
    }catch(e){ElMessage.error(errorText(e,'预约失败，请重新选择号源'));await Promise.all([loadSlots(),load()])}
  }finally{submitting.value=false}
}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading"><div><h1>排班预约</h1><p>选择科室与日期，查看医师出诊安排，再选择具体号源预约</p></div><el-button @click="viewAppointments">我的预约</el-button></div>
    <el-alert v-if="success" class="booking-success" type="success" :closable="false" show-icon>
      <template #title>预约成功 · {{success.appointment_no}}</template>
      <p>{{success.department_name}} · {{success.doctor_name}} · {{success.visit_date||success.slot?.date}} {{success.visit_time||success.slot?.start_time.slice(0,5)}}–{{success.slot?.end_time.slice(0,5)}}</p>
      <el-button link type="primary" @click="viewAppointments">查看我的预约 →</el-button>
    </el-alert>
    <ListError v-if="error" :message="error" @retry="load"/>
    <ScheduleCalendar v-else v-model:month="calendar.month" v-model:selected-date="calendar.selectedDate" v-model:department="calendar.department" v-model:doctor="calendar.doctor" v-model:status="calendar.status" :rows="rows" :departments="departments" :doctors="doctors" :is-doctor="false" :loading="loading" :options-loading="loading" :pending-ids="[]" booking-mode @reserve="reserve" @refresh="load"/>

    <el-dialog v-model="dialog" title="选择号源并预约" width="min(600px,95vw)" :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" destroy-on-close @closed="closeDialog">
      <template v-if="selectedSchedule">
        <div class="patient-booking-context"><span>{{selectedSchedule.department_name}} · {{selectedSchedule.doctor_title}}</span><h2>{{selectedSchedule.doctor_name}}</h2><p>{{selectedSchedule.date}} · {{selectedSchedule.time_range}} · 每号 {{selectedSchedule.slot_minutes}} 分钟</p></div>
        <div class="patient-slot-heading"><h3>选择就诊时间</h3><el-button link :disabled="submitting" :loading="slotsLoading" @click="loadSlots">刷新号源</el-button></div>
        <ListError v-if="slotsError" :message="slotsError" @retry="loadSlots"/>
        <div v-else v-loading="slotsLoading" class="patient-slot-options" aria-label="可预约号源">
          <div v-if="slots.length" class="slot-list"><button v-for="slot in slots" :key="slot.id" type="button" :class="{selected:booking.slot===slot.id}" :aria-pressed="booking.slot===slot.id" :disabled="submitting" @click="booking.slot=slot.id">{{slot.start_time.slice(0,5)}}–{{slot.end_time.slice(0,5)}}</button></div>
          <el-empty v-else-if="!slotsLoading" :image-size="64" description="此出诊时段暂无可预约号源，请选择其他时段"/>
        </div>
        <el-form label-position="top"><el-form-item label="就诊原因" required><el-input v-model="booking.reason" type="textarea" :disabled="submitting" :rows="3" maxlength="300" show-word-limit placeholder="请简要描述症状或就诊需求"/></el-form-item></el-form>
        <div v-if="selectedSlot" class="booking-summary"><span>预约摘要</span><p>{{selectedSchedule.department_name}} · {{selectedSchedule.doctor_name}} · {{selectedSchedule.date}} {{selectedSlot.start_time.slice(0,5)}}–{{selectedSlot.end_time.slice(0,5)}}</p></div>
      </template>
      <template #footer><el-button :disabled="submitting" @click="dialog=false">取消</el-button><el-button type="primary" :loading="submitting" :disabled="!selectedSlot||!booking.reason.trim()||slotsLoading" @click="submit">确认预约</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.booking-success{margin-bottom:18px}.booking-success p{margin:6px 0}.patient-booking-context{background:var(--surface-soft);border-left:3px solid var(--teal);border-radius:8px;padding:16px;margin-bottom:20px}.patient-booking-context span,.patient-booking-context p{font-size:13px;color:var(--muted)}.patient-booking-context h2{margin:8px 0;font-size:23px;color:var(--blue-deep)}.patient-booking-context p{margin:0;line-height:1.8}.patient-slot-heading{display:flex;align-items:center;justify-content:space-between}.patient-slot-heading h3{font-size:15px;margin:0}.patient-slot-options{min-height:90px;margin:12px 0 24px}.slot-list button:disabled{cursor:default;opacity:.65}
</style>
