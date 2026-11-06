<script setup lang="ts">
import{computed,onMounted,ref,watch}from'vue'
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
import type{Appointment}from'../../types/medical'
import{cancelAppointment,completeAppointment,getAppointments,markNoShow,startAppointment}from'../../services/appointments'

const auth=useAuthStore(),route=useRoute(),router=useRouter()
const isPatient=computed(()=>auth.user?.role==='patient'),isDoctor=computed(()=>auth.user?.role==='doctor')
const title=computed(()=>isPatient.value?'我的预约':isDoctor.value?'接诊管理':'预约管理')
const description=computed(()=>isPatient.value?'按科室、医师、日期和号源完成预约，管理个人预约记录':isDoctor.value?'按规范状态推进本人负责的预约':'查看全院预约并监督业务状态')
const state=useListState(`appointments-${auth.user?.role||'guest'}`,{page:1,status:'',date:'',view:'cards' as ViewMode})
const loading=ref(false),error=ref(''),appointments=ref<Appointment[]>([]),total=ref(0)
const weekdays=['周日','周一','周二','周三','周四','周五','周六']
const dateOptions=computed(()=>Array.from({length:7},(_,offset)=>{const date=new Date();date.setDate(date.getDate()+offset);const value=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');return{value,weekday:offset===0?'今天':weekdays[date.getDay()],day:date.getDate(),month:date.getMonth()+1}}))
const queueFocus=computed(()=>{const active=appointments.value.find(item=>item.status==='in_progress');return active?.id??appointments.value.find(item=>item.status==='pending')?.id??0})
async function load(){loading.value=true;error.value='';try{const result=await getAppointments({page:state.page,status:state.status||undefined,date:state.date||undefined});appointments.value=result.rows;total.value=result.count}catch(e:any){appointments.value=[];total.value=0;error.value=e.response?.data?.detail||'预约加载失败'}finally{loading.value=false}}
function search(){state.page=1;load()}
function pickDate(date:string){if(state.date===date)return;state.date=date;search()}
async function openBooking(){await router.push({path:'/patient/visits',query:{tab:'doctors',...(route.query.department?{department:route.query.department}:{}),...(route.query.doctor?{doctor:route.query.doctor}:{})}})}
async function action(row:Appointment,kind:'cancel'|'start'|'complete'|'no-show'){const wording={cancel:'取消预约',start:'开始接诊',complete:'完成诊疗','no-show':'标记爽约'}[kind];try{await ElMessageBox.confirm(`确定要${wording}吗？`,wording,{type:kind==='cancel'||kind==='no-show'?'warning':'info'});const fn={cancel:cancelAppointment,start:startAppointment,complete:completeAppointment,'no-show':markNoShow}[kind];await fn(row.id);ElMessage.success('状态已更新');if(kind==='start'){await router.push({path:`/doctor/visits/${row.id}`,query:{returnTo:route.fullPath}});return}await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'操作失败')}}
function openWorkspace(row:Appointment){router.push({path:`/doctor/visits/${row.id}`,query:{returnTo:route.fullPath}})}
watch(()=>state.status,()=>search())
onMounted(async()=>{await load();if(isPatient.value&&(route.query.doctor||route.query.department))await openBooking()})
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">APPOINTMENT WORKFLOW</p><h1>{{title}}</h1><p>{{description}}</p></div><el-button v-if="isPatient" type="primary" @click="openBooking">＋ 预约挂号</el-button></div>
    <el-alert v-if="isPatient" title="急诊不支持预约，请直接到急诊科现场分诊" type="warning" :closable="false" show-icon class="record-alert"/>
    <el-card class="table-card">
      <div class="date-axis" role="group" aria-label="按就诊日期筛选">
        <button type="button" :class="{active:!state.date}" :aria-pressed="!state.date" @click="pickDate('')"><span>日期</span><b>全部</b><small>不限</small></button>
        <button v-for="day in dateOptions" :key="day.value" type="button" :class="{active:state.date===day.value}" :aria-pressed="state.date===day.value" @click="pickDate(day.value)"><span>{{day.weekday}}</span><b>{{day.day}}</b><small>{{day.month}}月</small></button>
      </div>
      <div class="table-tools"><el-select v-model="state.status" clearable placeholder="全部状态" style="width:160px"><el-option v-for="item in [['pending','待就诊'],['in_progress','就诊中'],['completed','已完成'],['cancelled','已取消'],['no_show','爽约']]" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select><span class="workflow-hint">待就诊 → 就诊中 → 已完成</span><span v-if="isDoctor" class="table-count">当前队列 {{total}} 人</span><ViewSwitch v-model="state.view"/></div>
      <div class="legend-row"><StatusLegend domain="appointment" title="预约状态"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="task-card-grid">
        <TaskCard v-for="row in appointments" :key="row.id" :time="`${row.visit_date||row.slot?.date||''} ${row.visit_time||row.slot?.start_time?.slice(0,5)||''}${row.slot?'–'+(row.slot.end_time?.slice(0,5)||''):'（急诊）'}`" :title="isPatient?row.doctor_name:row.patient_name" :subtitle="`${row.appointment_no} · ${row.department_name}`" :accent="statusInfo('appointment',row.status).tone" :highlight="isDoctor&&row.id===queueFocus" :meta="isPatient?[{label:'医师',value:row.doctor_name},{label:'就诊原因',value:row.reason}]:[{label:'患者',value:row.patient_name},{label:'医师',value:row.doctor_name},{label:'就诊原因',value:row.reason}]">
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
          <el-table-column label="就诊时间" min-width="180"><template #default="{row}">{{row.visit_date||row.slot?.date}} {{row.visit_time||row.slot?.start_time?.slice(0,5)}}<template v-if="row.slot">–{{row.slot.end_time?.slice(0,5)}}</template><el-tag v-else type="danger" size="small" style="margin-left:6px">急诊</el-tag></template></el-table-column>
          <el-table-column prop="reason" label="就诊原因" min-width="180" show-overflow-tooltip/>
          <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></template></el-table-column>
          <el-table-column label="操作" min-width="190" fixed="right"><template #default="{row}"><el-button v-if="isPatient&&row.status==='pending'" link type="danger" @click="action(row,'cancel')">取消</el-button><template v-if="isDoctor"><el-button v-if="row.status==='pending'" link type="primary" @click="action(row,'start')">接诊</el-button><el-button v-if="row.status==='pending'" link type="danger" @click="action(row,'no-show')">爽约</el-button><el-button v-if="row.status==='in_progress'" link type="primary" @click="openWorkspace(row)">工作区</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="action(row,'complete')">完成诊疗</el-button></template></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in appointments" :key="row.id" class="mobile-info-card">
            <header><h3>{{isPatient?row.doctor_name:row.patient_name}}</h3><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></header>
            <p class="mobile-sub">{{row.appointment_no}} · {{row.department_name}}</p>
            <div class="mobile-line"><span>就诊时间</span><b>{{row.visit_date||row.slot?.date}} {{row.visit_time||row.slot?.start_time?.slice(0,5)}}<template v-if="row.slot">–{{row.slot.end_time?.slice(0,5)}}</template><template v-else>（急诊）</template></b></div>
            <div class="mobile-line" v-if="isPatient"><span>医师</span><b>{{row.doctor_name}}</b></div>
            <p class="mobile-sub">{{row.reason}}</p>
            <div class="actions"><el-button v-if="isPatient&&row.status==='pending'" link type="danger" @click="action(row,'cancel')">取消</el-button><template v-if="isDoctor"><el-button v-if="row.status==='pending'" link type="primary" @click="action(row,'start')">接诊</el-button><el-button v-if="row.status==='pending'" link type="danger" @click="action(row,'no-show')">爽约</el-button><el-button v-if="row.status==='in_progress'" link type="primary" @click="openWorkspace(row)">工作区</el-button><el-button v-if="row.status==='in_progress'" link type="success" @click="action(row,'complete')">完成诊疗</el-button></template></div>
          </article>
          <div v-if="!appointments.length&&!loading" class="mobile-empty">暂无预约记录</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
  </section>
</template>
