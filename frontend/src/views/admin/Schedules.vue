<script setup lang="ts">
import{computed,onMounted,reactive,ref,watch}from'vue'
import{useRouter}from'vue-router'
import{ElMessage}from'element-plus'
import{createSchedule,getDoctorsAdmin,getOutpatientVisits,getSchedules,updateSchedule,type Schedule}from'../../services/admin'
import{getOperationDepartments}from'../../services/operations'
import api from'../../services/api'
import{useAuthStore}from'../../stores/auth'
import{useListState}from'../../composables/useListState'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import{statusInfo,statusTone}from'../../utils/status'
import type{Department,DoctorSummary,MedicalRecord,OutpatientResult,OutpatientSlot}from'../../types/medical'

type ViewMode='schedules'|'visits'
const props=defineProps<{view?:ViewMode}>()
const auth=useAuthStore(),router=useRouter(),isDoctor=computed(()=>auth.user?.role==='doctor')
const showTabs=computed(()=>!props.view),active=ref<'settings'|'visits'>(props.view==='visits'?'visits':'settings')
const today=new Date().toISOString().slice(0,10)
const filters=useListState(`schedules-visits-${auth.user?.role||'guest'}`,{date:today,department:undefined as number|undefined,doctor:undefined as number|undefined,status:'',page:1,pageSize:10})
const rows=ref<Schedule[]>([]),doctors=ref<DoctorSummary[]>([]),departments=ref<Department[]>([]),loading=ref(false),error=ref(''),dialog=ref(false),saving=ref(false)
const form=reactive({doctor:0,date:'',start_time:'09:00',end_time:'12:00',slot_minutes:30})
const minDate=new Date().toISOString().slice(0,10)
const visitsLoading=ref(false),visits=ref<OutpatientResult|null>(null),visitsError=ref('')
const detailOpen=ref(false),selected=ref<OutpatientSlot|null>(null),recordDetail=ref<MedicalRecord|null>(null),recordLoading=ref(false)
const statusOptions=[['available','可预约'],['pending','待就诊'],['in_progress','就诊中'],['completed','已完成'],['cancelled','已取消'],['no_show','爽约'],['closed','已关闭']]
const canEnterWorkspace=computed(()=>isDoctor.value&&selected.value?.appointment&&['pending','in_progress'].includes(selected.value.appointment.status))
const weekdays=['周日','周一','周二','周三','周四','周五','周六']
const visitDates=computed(()=>Array.from({length:7},(_,offset)=>{const date=new Date();date.setDate(date.getDate()+offset);const value=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');return{value,weekday:offset===0?'今天':weekdays[date.getDay()],day:date.getDate(),month:date.getMonth()+1}}))
function pickVisitDate(value:string){if(filters.date===value)return;filters.date=value;searchVisits()}

function errorText(e:any,fallback:string){return e.response?.data?.detail||fallback}
function slotInfo(slot:OutpatientSlot){return slot.appointment?statusInfo('appointment',slot.state):statusInfo('slot',slot.slot_status)}
async function load(){loading.value=true;error.value='';try{rows.value=(await getSchedules()).results}catch(e:any){rows.value=[];error.value=errorText(e,'排班加载失败')}finally{loading.value=false}}
async function loadFilters(){try{departments.value=await getOperationDepartments()}catch{departments.value=[]}}
async function loadDoctorOptions(){if(isDoctor.value)return;try{doctors.value=await getDoctorsAdmin({department:filters.department})}catch{doctors.value=[]}}
async function loadVisits(){visitsLoading.value=true;visitsError.value='';try{visits.value=await getOutpatientVisits({date:filters.date,department:filters.department||undefined,doctor:filters.doctor||undefined,status:filters.status||undefined,page:filters.page,page_size:filters.pageSize})}catch(e:any){visits.value=null;visitsError.value=errorText(e,'门诊就诊视图加载失败')}finally{visitsLoading.value=false}}
function searchVisits(){filters.page=1;loadVisits()}
function resetVisits(){Object.assign(filters,{date:today,department:undefined,doctor:undefined,status:'',page:1});loadDoctorOptions();loadVisits()}
function changeTab(name:string|number){active.value=name==='visits'?'visits':'settings';if(active.value==='visits'){if(!departments.value.length)loadFilters();loadDoctorOptions();loadVisits()}}
function ensureView(){if(active.value==='visits'){loadFilters();loadDoctorOptions();loadVisits()}else load()}
async function open(){Object.assign(form,{doctor:0,date:'',start_time:'09:00',end_time:'12:00',slot_minutes:30});dialog.value=true;if(isDoctor.value)form.doctor=(await api.get('doctors/me/')).data.id;else doctors.value=await getDoctorsAdmin()}
async function submit(){if(!form.doctor||!form.date){ElMessage.warning('请选择医师和日期');return}if(form.start_time>=form.end_time){ElMessage.warning('结束时间必须晚于开始时间');return}saving.value=true;try{await createSchedule({...form,start_time:`${form.start_time}:00`,end_time:`${form.end_time}:00`});ElMessage.success('排班和号源已生成');dialog.value=false;await load()}catch(e:any){ElMessage.error(errorText(e,'排班创建失败'))}finally{saving.value=false}}
async function toggle(row:Schedule){try{await updateSchedule(row.id,{is_active:!row.is_active});await load()}catch(e:any){ElMessage.error(errorText(e,'排班状态更新失败'))}}
async function openSlot(slot:OutpatientSlot){if(!slot.appointment)return;selected.value=slot;recordDetail.value=null;detailOpen.value=true;const record=slot.appointment.record;if(!record)return;recordLoading.value=true;try{recordDetail.value=(await api.get(`medical-records/${record.id}/`)).data}catch{recordDetail.value=null}finally{recordLoading.value=false}}
function enterWorkspace(){const appointment=selected.value?.appointment;if(appointment)router.push({path:`/doctor/visits/${appointment.id}`,query:{returnTo:'/doctor/outpatient?tab=visits'}})}
function recordStatus(row:OutpatientSlot){const record=row.appointment?.record;if(!record)return'未建立';return record.status==='confirmed'?'已确认':'草稿'}
function shortTime(value?:string){return value?value.slice(0,5):'—'}
watch(()=>props.view,value=>{active.value=value==='visits'?'visits':'settings';ensureView()})
onMounted(async()=>{await Promise.all([loadFilters(),ensureView()])})
</script>

<template>
  <section>
    <div class="page-heading">
      <div><p class="eyebrow">SCHEDULE & OUTPATIENT VISITS</p><h1>{{active==='visits'?'门诊就诊':isDoctor?'我的排班':'排班设置'}}</h1><p>{{active==='visits'?'按“医师 → 排班 → 号源 → 患者”追踪预约与接诊状态':'设置医师出诊时段，系统自动生成可预约号源'}}</p></div>
      <el-button v-if="active!=='visits'" type="primary" @click="open">＋ 新建排班</el-button>
    </div>
    <div v-if="showTabs" class="inline-tabs"><el-tabs v-model="active" @tab-change="changeTab"><el-tab-pane label="排班设置" name="settings"/><el-tab-pane label="门诊就诊" name="visits"/></el-tabs></div>

    <div v-if="active==='settings'">
      <ListError v-if="error" :message="error" @retry="load"/>
      <el-card v-else class="table-card">
        <el-table v-loading="loading" :data="rows" empty-text="暂无排班">
          <el-table-column prop="doctor_name" label="医师"/>
          <el-table-column prop="date" label="日期"/>
          <el-table-column prop="time_range" label="出诊时间"/>
          <el-table-column prop="slot_minutes" label="每号分钟"/>
          <el-table-column prop="total_slots" label="总号源"/>
          <el-table-column prop="available_slots" label="剩余"/>
          <el-table-column label="状态"><template #default="{row}"><el-tag :type="row.is_active?'success':'info'">{{row.is_active?'开放':'关闭'}}</el-tag></template></el-table-column>
          <el-table-column label="操作"><template #default="{row}"><el-button link @click="toggle(row)">{{row.is_active?'关闭':'开放'}}</el-button></template></el-table-column>
        </el-table>
      </el-card>
    </div>

    <div v-else>
      <el-card class="table-card">
        <div class="date-axis" role="group" aria-label="按出诊日期查看">
          <button v-for="day in visitDates" :key="day.value" type="button" :class="{active:filters.date===day.value}" :aria-pressed="filters.date===day.value" @click="pickVisitDate(day.value)"><span>{{day.weekday}}</span><b>{{day.day}}</b><small>{{day.month}}月</small></button>
        </div>
        <div class="table-tools outpatient-tools">
          <el-date-picker v-model="filters.date" type="date" value-format="YYYY-MM-DD" :clearable="false" style="width:140px" @change="searchVisits"/>
          <el-select v-if="!isDoctor" v-model="filters.department" clearable placeholder="全部科室" style="width:170px" @change="filters.doctor=undefined;loadDoctorOptions();searchVisits()"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
          <el-select v-if="!isDoctor" v-model="filters.doctor" clearable filterable placeholder="全部医师" style="width:170px" @change="searchVisits"><el-option v-for="item in doctors" :key="item.id" :label="`${item.full_name} · ${item.department_name}`" :value="item.id"/></el-select>
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width:150px" @change="searchVisits"><el-option v-for="item in statusOptions" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select>
          <el-button @click="searchVisits">查询</el-button>
          <el-button link @click="resetVisits">重置</el-button>
        </div>
        <div class="legend-row"><StatusLegend domain="appointment" title="预约状态"/><StatusLegend domain="slot" title="号源状态"/></div>
        <ListError v-if="visitsError" :message="visitsError" @retry="loadVisits"/>
        <div v-else v-loading="visitsLoading" class="outpatient-board">
          <template v-if="visits&&visits.results.length">
            <article v-for="group in visits.results" :key="group.doctor.id" class="outpatient-doctor-card">
              <header class="outpatient-doctor-head">
                <div class="outpatient-doctor-avatar">{{group.doctor.full_name?.slice(0,1)}}</div>
                <div class="outpatient-doctor-main"><h3>{{group.doctor.full_name}}<el-tag size="small">{{group.doctor.title||'医师'}}</el-tag></h3><p>{{group.doctor.department_name}} · {{group.doctor.specialty||'暂无专业方向'}}</p><small>{{group.doctor.introduction||'暂无医师简介'}}</small></div>
                <span class="outpatient-schedule-count">{{group.schedules.length}} 个出诊时段</span>
              </header>
              <section v-for="schedule in group.schedules" :key="schedule.id" class="outpatient-schedule">
                <div class="outpatient-schedule-head"><b>{{schedule.date}} · {{schedule.time_range}}</b><span>每号 {{schedule.slot_minutes}} 分钟 · 共 {{schedule.slots.length}} 个号源</span></div>
                <div class="outpatient-slots">
                  <button v-for="slot in schedule.slots" :key="slot.id" type="button" class="outpatient-slot" :data-state="slot.state" :disabled="!slot.appointment&&slot.slot_status!=='available'" @click="openSlot(slot)">
                    <span class="outpatient-slot-time">{{shortTime(slot.start_time)}}–{{shortTime(slot.end_time)}}</span>
                    <span class="outpatient-slot-state">{{slotInfo(slot).label}}</span>
                    <template v-if="slot.appointment">
                      <strong>{{slot.appointment.patient.full_name}}</strong>
                      <small>{{slot.appointment.patient.patient_no}} · {{slot.appointment.patient.gender_display}}</small>
                      <span class="outpatient-slot-reason">{{slot.appointment.reason}}</span>
                      <small class="outpatient-slot-record">病历 {{recordStatus(slot)}}</small>
                    </template>
                    <template v-else><strong class="muted">{{slot.slot_status==='closed'?'号源已关闭':'空号源'}}</strong><small>可继续预约</small></template>
                  </button>
                </div>
              </section>
            </article>
          </template>
          <el-empty v-else-if="!visitsLoading" description="该筛选条件下没有排班或号源"/>
        </div>
        <div class="pagination"><span>共 {{visits?.count||0}} 个排班 · {{visits?.slot_count||0}} 个号源</span><el-pagination v-model:current-page="filters.page" v-model:page-size="filters.pageSize" layout="sizes,prev,pager,next" :page-sizes="[10,20,50]" :total="visits?.count||0" @current-change="loadVisits" @size-change="()=>searchVisits()"/></div>
      </el-card>
    </div>

    <el-dialog v-model="dialog" title="新建医师排班" width="min(560px,94vw)">
      <el-form label-position="top">
        <el-form-item v-if="!isDoctor" label="出诊医师" required><el-select v-model="form.doctor" filterable style="width:100%"><el-option v-for="item in doctors" :key="item.id" :label="`${item.full_name} · ${item.department_name}`" :value="item.id"/></el-select></el-form-item>
        <el-form-item label="出诊日期" required><el-date-picker v-model="form.date" value-format="YYYY-MM-DD" style="width:100%" :disabled-date="(d:Date)=>d.getTime()<new Date(minDate).setHours(0,0,0,0)"/></el-form-item>
        <el-row :gutter="12"><el-col :span="8"><el-form-item label="开始时间"><el-time-select v-model="form.start_time" start="07:00" step="00:30" end="20:00"/></el-form-item></el-col><el-col :span="8"><el-form-item label="结束时间"><el-time-select v-model="form.end_time" start="07:30" step="00:30" end="21:00"/></el-form-item></el-col><el-col :span="8"><el-form-item label="每号时长"><el-select v-model="form.slot_minutes"><el-option label="15 分钟" :value="15"/><el-option label="20 分钟" :value="20"/><el-option label="30 分钟" :value="30"/></el-select></el-form-item></el-col></el-row>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">生成排班</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="selected?.appointment?`就诊详情 · ${selected.appointment.appointment_no}`:'就诊详情'" size="min(620px,94vw)">
      <div v-if="selected?.appointment" class="record-detail">
        <div><span>患者</span><b>{{selected.appointment.patient.full_name}} · {{selected.appointment.patient.patient_no}}</b></div>
        <div><span>联系方式 / 性别</span><b>{{selected.appointment.patient.phone||'—'}} · {{selected.appointment.patient.gender_display}}</b></div>
        <div><span>过敏史</span><b>{{selected.appointment.patient.allergies||'无已知过敏'}}</b></div>
        <div><span>就诊科室 / 医师</span><b>{{selected.appointment.department_name}} · {{selected.appointment.doctor_name}}</b></div>
        <div><span>预约时间</span><b>{{selected.appointment.appointment_no}} · {{visits?.date_from}} {{shortTime(selected.start_time)}}–{{shortTime(selected.end_time)}}</b></div>
        <div><span>就诊原因</span><p>{{selected.appointment.reason}}</p></div>
        <div><span>预约状态</span><el-tag :type="statusTone('appointment',selected.appointment.status)">{{statusInfo('appointment',selected.appointment.status).label}}</el-tag></div>
        <div><span>病历状态</span><b>{{recordStatus(selected)}}{{selected.appointment.record?.record_no?` · ${selected.appointment.record.record_no}`:''}}</b></div>
        <template v-if="recordLoading"><el-skeleton :rows="3" animated/></template>
        <template v-else-if="recordDetail"><div><span>主诉</span><p>{{recordDetail.chief_complaint}}</p></div><div><span>现病史 / 既往史</span><p>{{recordDetail.present_illness||'—'}} / {{recordDetail.past_history||'—'}}</p></div><div><span>诊断</span><p>{{recordDetail.diagnosis}}</p></div><div><span>处理意见</span><p>{{recordDetail.treatment||'—'}}</p></div></template>
        <el-alert v-else-if="selected.appointment.record" :title="selected.appointment.record.status==='draft'?'病历草稿仅主诊医师可编辑。':'该病历暂不可读取。'" type="info" :closable="false"/>
        <div v-if="canEnterWorkspace" class="drawer-actions"><el-button type="primary" @click="enterWorkspace">进入接诊工作区</el-button></div>
      </div>
    </el-drawer>
  </section>
</template>
