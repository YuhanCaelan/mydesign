<script setup lang="ts">
import{computed,onMounted,reactive,ref,watch}from'vue'
import{useRoute,useRouter}from'vue-router'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import TaskCard from'../../components/common/TaskCard.vue'
import{useListState}from'../../composables/useListState'
import{statusInfo}from'../../utils/status'
import type{ViewMode}from'../../utils/view'
import type{Appointment,AppointmentSlot,Department,DoctorSummary}from'../../types/medical'
import{cancelAppointment,completeAppointment,createAppointment,getAppointments,getDepartments,getDoctors,getSlots,markNoShow,startAppointment}from'../../services/appointments'

const auth=useAuthStore(),route=useRoute(),router=useRouter()
const isPatient=computed(()=>auth.user?.role==='patient'),isDoctor=computed(()=>auth.user?.role==='doctor')
const title=computed(()=>isPatient.value?'我的预约':isDoctor.value?'接诊管理':'预约管理')
const description=computed(()=>isPatient.value?'按科室、医师、日期和号源完成预约，管理个人预约记录':isDoctor.value?'按规范状态推进本人负责的预约':'查看全院预约并监督业务状态')
const state=useListState(`appointments-${auth.user?.role||'guest'}`,{page:1,status:'',date:'',view:'cards' as ViewMode})
const loading=ref(false),error=ref(''),appointments=ref<Appointment[]>([]),total=ref(0)
const weekdays=['周日','周一','周二','周三','周四','周五','周六']
const dateOptions=computed(()=>Array.from({length:7},(_,offset)=>{const date=new Date();date.setDate(date.getDate()+offset);const value=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');return{value,weekday:offset===0?'今天':weekdays[date.getDay()],day:date.getDate(),month:date.getMonth()+1}}))
const queueFocus=computed(()=>{const active=appointments.value.find(item=>item.status==='in_progress');return active?.id??appointments.value.find(item=>item.status==='pending')?.id??0})
const bookingOpen=ref(false),submitting=ref(false),departments=ref<Department[]>([]),doctors=ref<DoctorSummary[]>([]),slots=ref<AppointmentSlot[]>([])
const booking=reactive({department:undefined as number|undefined,doctor:undefined as number|undefined,date:'',slot:undefined as number|undefined,reason:''})
const minDate=new Date().toISOString().slice(0,10)
const bookingStep=computed(()=>!booking.department?1:!booking.doctor?2:!booking.date?3:!booking.slot?4:5)
const selectedDoctor=computed(()=>doctors.value.find(item=>item.id===booking.doctor))
const selectedDepartment=computed(()=>departments.value.find(item=>item.id===booking.department))
const selectedSlot=computed(()=>slots.value.find(item=>item.id===booking.slot))

async function load(){loading.value=true;error.value='';try{const result=await getAppointments({page:state.page,status:state.status||undefined,date:state.date||undefined});appointments.value=result.rows;total.value=result.count}catch(e:any){appointments.value=[];total.value=0;error.value=e.response?.data?.detail||'预约加载失败'}finally{loading.value=false}}
function search(){state.page=1;load()}
function pickDate(date:string){if(state.date===date)return;state.date=date;search()}
async function openBooking(){Object.assign(booking,{department:undefined,doctor:undefined,date:'',slot:undefined,reason:''});slots.value=[];bookingOpen.value=true;if(!departments.value.length){try{departments.value=await getDepartments()}catch{departments.value=[];ElMessage.error('科室数据加载失败');return}}
  const department=Number(route.query.department),doctor=Number(route.query.doctor)
  if(department){booking.department=department;try{doctors.value=await getDoctors(department)}catch{doctors.value=[]}}
  if(doctor)booking.doctor=doctor
}
async function selectDepartment(){booking.doctor=undefined;booking.date='';booking.slot=undefined;slots.value=[];try{doctors.value=booking.department?await getDoctors(booking.department):[]}catch{doctors.value=[]}}
async function loadSlots(){try{slots.value=await getSlots(booking.doctor!,booking.date)}catch{slots.value=[];ElMessage.error('号源加载失败')}}
watch(()=>booking.doctor,()=>{booking.slot=undefined;if(booking.date&&booking.doctor)loadSlots();else slots.value=[]})
watch(()=>booking.date,()=>{booking.slot=undefined;if(booking.date&&booking.doctor)loadSlots();else slots.value=[]})
async function submitBooking(){
  if(!booking.slot){ElMessage.warning('请选择预约号源');return}
  if(!booking.reason.trim()){ElMessage.warning('请填写就诊原因');return}
  const summary=[`科室：${selectedDepartment.value?.name||'—'}`,`医师：${selectedDoctor.value?.full_name||'—'}`,`日期：${booking.date}`,`时间：${selectedSlot.value?.start_time.slice(0,5)}–${selectedSlot.value?.end_time.slice(0,5)}`,`就诊原因：${booking.reason.trim()}`].join('\n')
  try{await ElMessageBox.confirm(summary,'确认预约信息',{type:'info',confirmButtonText:'确认预约'})}catch{return}
  submitting.value=true;try{await createAppointment({slot_id:booking.slot,reason:booking.reason.trim()});ElMessage.success('预约成功');bookingOpen.value=false;Object.assign(booking,{department:undefined,doctor:undefined,date:'',slot:undefined,reason:''});slots.value=[];state.page=1;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'预约失败，请重新选择号源');booking.slot=undefined;await loadSlots()}finally{submitting.value=false}
}
async function action(row:Appointment,kind:'cancel'|'start'|'complete'|'no-show'){const wording={cancel:'取消预约',start:'开始接诊',complete:'完成诊疗','no-show':'标记爽约'}[kind];try{await ElMessageBox.confirm(`确定要${wording}吗？`,wording,{type:kind==='cancel'||kind==='no-show'?'warning':'info'});const fn={cancel:cancelAppointment,start:startAppointment,complete:completeAppointment,'no-show':markNoShow}[kind];await fn(row.id);ElMessage.success('状态已更新');if(kind==='start'){await router.push({path:`/doctor/visits/${row.id}`,query:{returnTo:route.fullPath}});return}await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}
function openWorkspace(row:Appointment){router.push({path:`/doctor/visits/${row.id}`,query:{returnTo:route.fullPath}})}
watch(()=>state.status,()=>search())
onMounted(async()=>{await load();if(isPatient.value&&(route.query.doctor||route.query.department))await openBooking()})
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">APPOINTMENT WORKFLOW</p><h1>{{title}}</h1><p>{{description}}</p></div><el-button v-if="isPatient" type="primary" @click="openBooking">＋ 预约挂号</el-button></div>
    <el-card class="table-card">
      <div class="date-axis" role="group" aria-label="按就诊日期筛选">
        <button type="button" :class="{active:!state.date}" :aria-pressed="!state.date" @click="pickDate('')"><span>日期</span><b>全部</b><small>不限</small></button>
        <button v-for="day in dateOptions" :key="day.value" type="button" :class="{active:state.date===day.value}" :aria-pressed="state.date===day.value" @click="pickDate(day.value)"><span>{{day.weekday}}</span><b>{{day.day}}</b><small>{{day.month}}月</small></button>
      </div>
      <div class="table-tools"><el-select v-model="state.status" clearable placeholder="全部状态" style="width:160px"><el-option v-for="item in [['pending','待就诊'],['in_progress','就诊中'],['completed','已完成'],['cancelled','已取消'],['no_show','爽约']]" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select><span class="workflow-hint">待就诊 → 就诊中 → 已完成</span><span v-if="isDoctor" class="table-count">当前队列 {{total}} 人</span><ViewSwitch v-model="state.view"/></div>
      <div class="legend-row"><StatusLegend domain="appointment" title="预约状态"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="task-card-grid">
        <TaskCard v-for="row in appointments" :key="row.id" :time="`${row.slot?.date} ${row.slot?.start_time?.slice(0,5)}–${row.slot?.end_time?.slice(0,5)}`" :title="isPatient?row.doctor_name:row.patient_name" :subtitle="`${row.appointment_no} · ${row.department_name}`" :accent="statusInfo('appointment',row.status).tone" :highlight="isDoctor&&row.id===queueFocus" :meta="isPatient?[{label:'医师',value:row.doctor_name},{label:'就诊原因',value:row.reason}]:[{label:'患者',value:row.patient_name},{label:'医师',value:row.doctor_name},{label:'就诊原因',value:row.reason}]">
          <template #status><div class="task-status"><el-tag v-if="isDoctor&&row.status==='in_progress'" effect="dark" type="primary">诊疗中</el-tag><el-tag v-else-if="isDoctor&&row.id===queueFocus" effect="plain" type="warning">下一位</el-tag><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></div></template>
          <template #actions><el-button v-if="isPatient&&row.status==='pending'" link type="danger" @click="action(row,'cancel')">取消</el-button><template v-if="isDoctor"><el-button v-if="row.status==='pending'" link type="primary" @click="action(row,'start')">接诊</el-button><el-button v-if="row.status==='pending'" link type="danger" @click="action(row,'no-show')">爽约</el-button><el-button v-if="row.status==='in_progress'" link type="primary" @click="openWorkspace(row)">工作区</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="action(row,'complete')">完成诊疗</el-button></template></template>
        </TaskCard>
        <el-empty v-if="!appointments.length&&!loading" description="暂无预约记录"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="appointments" empty-text="暂无预约记录" class="desktop-table">
          <el-table-column prop="appointment_no" label="预约编号" min-width="145"/>
          <el-table-column v-if="!isPatient" prop="patient_name" label="患者" min-width="110"/>
          <el-table-column v-if="!isDoctor" prop="doctor_name" label="医师" min-width="110"/>
          <el-table-column prop="department_name" label="科室" min-width="110"/>
          <el-table-column label="就诊时间" min-width="180"><template #default="{row}">{{row.slot?.date}} {{row.slot?.start_time?.slice(0,5)}}–{{row.slot?.end_time?.slice(0,5)}}</template></el-table-column>
          <el-table-column prop="reason" label="就诊原因" min-width="180" show-overflow-tooltip/>
          <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></template></el-table-column>
          <el-table-column label="操作" min-width="190" fixed="right"><template #default="{row}"><el-button v-if="isPatient&&row.status==='pending'" link type="danger" @click="action(row,'cancel')">取消</el-button><template v-if="isDoctor"><el-button v-if="row.status==='pending'" link type="primary" @click="action(row,'start')">接诊</el-button><el-button v-if="row.status==='pending'" link type="danger" @click="action(row,'no-show')">爽约</el-button><el-button v-if="row.status==='in_progress'" link type="primary" @click="openWorkspace(row)">工作区</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="action(row,'complete')">完成诊疗</el-button></template></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in appointments" :key="row.id" class="mobile-info-card">
            <header><h3>{{isPatient?row.doctor_name:row.patient_name}}</h3><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></header>
            <p class="mobile-sub">{{row.appointment_no}} · {{row.department_name}}</p>
            <div class="mobile-line"><span>就诊时间</span><b>{{row.slot?.date}} {{row.slot?.start_time?.slice(0,5)}}–{{row.slot?.end_time?.slice(0,5)}}</b></div>
            <div class="mobile-line" v-if="isPatient"><span>医师</span><b>{{row.doctor_name}}</b></div>
            <p class="mobile-sub">{{row.reason}}</p>
            <div class="actions"><el-button v-if="isPatient&&row.status==='pending'" link type="danger" @click="action(row,'cancel')">取消</el-button><template v-if="isDoctor"><el-button v-if="row.status==='pending'" link type="primary" @click="action(row,'start')">接诊</el-button><el-button v-if="row.status==='pending'" link type="danger" @click="action(row,'no-show')">爽约</el-button><el-button v-if="row.status==='in_progress'" link type="primary" @click="openWorkspace(row)">工作区</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="action(row,'complete')">完成诊疗</el-button></template></div>
          </article>
          <div v-if="!appointments.length&&!loading" class="mobile-empty">暂无预约记录</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>

    <el-dialog v-model="bookingOpen" title="预约挂号" width="min(620px,95vw)" destroy-on-close>
      <ol class="booking-steps" aria-label="预约步骤">
        <li v-for="(step,index) in [{key:1,label:'科室'},{key:2,label:'医师'},{key:3,label:'日期'},{key:4,label:'号源'}]" :key="step.key" :class="{done:bookingStep>step.key,current:bookingStep===step.key}"><b>{{index+1}}</b><span>{{step.label}}</span></li>
      </ol>
      <el-form label-position="top">
        <div class="booking-block" :class="{complete:Boolean(booking.department)}"><h3>1. 选择科室</h3><el-select v-model="booking.department" placeholder="选择科室" style="width:100%" @change="selectDepartment"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select></div>
        <div class="booking-block" :class="{complete:Boolean(booking.doctor),disabled:!booking.department}"><h3>2. 选择医师</h3><el-select v-model="booking.doctor" placeholder="选择医师" style="width:100%" :disabled="!booking.department"><el-option v-for="item in doctors" :key="item.id" :label="`${item.full_name} · ${item.title} · ${item.specialty||'综合'}`" :value="item.id"/></el-select></div>
        <div class="booking-block" :class="{complete:Boolean(booking.date),disabled:!booking.doctor}"><h3>3. 选择日期</h3><el-date-picker v-model="booking.date" type="date" value-format="YYYY-MM-DD" :disabled-date="(date:Date)=>date.getTime()<new Date(minDate).setHours(0,0,0,0)" style="width:100%" :disabled="!booking.doctor"/></div>
        <div class="booking-block" :class="{complete:Boolean(booking.slot),disabled:!booking.date}"><h3>4. 选择号源</h3><div v-if="slots.length" class="slot-list"><button v-for="item in slots" :key="item.id" type="button" :class="{selected:booking.slot===item.id}" @click="booking.slot=item.id">{{item.start_time.slice(0,5)}}–{{item.end_time.slice(0,5)}}</button></div><el-empty v-else :image-size="50" :description="booking.date?'该日期暂无可预约号源':'请先选择医师和日期'"/></div>
        <el-form-item label="就诊原因" required><el-input v-model="booking.reason" type="textarea" :rows="3" maxlength="300" show-word-limit placeholder="请简要描述症状或就诊需求"/></el-form-item>
        <div v-if="bookingStep===5" class="booking-summary"><span>预约摘要</span><p>{{selectedDepartment?.name}} · {{selectedDoctor?.full_name}} · {{booking.date}} {{selectedSlot?.start_time.slice(0,5)}}–{{selectedSlot?.end_time.slice(0,5)}}</p></div>
      </el-form>
      <template #footer><el-button @click="bookingOpen=false">取消</el-button><el-button type="primary" :loading="submitting" :disabled="bookingStep<5||!booking.reason.trim()" @click="submitBooking">确认预约</el-button></template>
    </el-dialog>
  </section>
</template>
