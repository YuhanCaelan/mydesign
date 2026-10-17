<script setup lang="ts">
import{computed,onMounted,reactive,ref,watch}from'vue'
import{ElMessage}from'element-plus'
import{createDepartment,getDepartmentDoctors,getDepartmentHistoryPatients,getDepartmentOverview,getDepartmentVisits,updateDepartment}from'../../services/admin'
import api from'../../services/api'
import{useListState}from'../../composables/useListState'
import ListError from'../../components/common/ListError.vue'
import{statusInfo}from'../../utils/status'
import type{Appointment,Department,DepartmentDoctor,DepartmentHistoryPatient,DepartmentOverview}from'../../types/medical'

const today=new Date().toISOString().slice(0,10)
const ui=useListState('departments-overview',{date:today})
const selectedDate=computed({get:()=>ui.date,set:(value:string)=>{ui.date=value}})
const rows=ref<DepartmentOverview[]>([]),notes=ref<Record<string,string>>({}),loading=ref(false),error=ref('')
const dialog=ref(false),saving=ref(false),current=ref<Department|null>(null),form=reactive({name:'',description:''})
const drawer=ref(false),detail=ref<DepartmentOverview|null>(null),detailTab=ref('overview')
const visits=ref<Appointment[]>([]),visitTotal=ref(0),visitPage=ref(1),visitLoading=ref(false),visitError=ref(''),currentVisits=ref<Appointment[]>([])
const doctors=ref<DepartmentDoctor[]>([]),doctorsLoading=ref(false),doctorsError=ref('')
const historyRows=ref<DepartmentHistoryPatient[]>([]),historyTotal=ref(0),historyPage=ref(1),historyLoading=ref(false),historyError=ref(''),historySearch=ref(''),historyRange=ref<[string,string]|null>(null)
const patientDrawer=ref(false),patientProfile=ref<any>(null),patientLoading=ref(false)
const stats=computed(()=>detail.value?.stats)
function errorText(e:any,fallback:string){return e.response?.data?.detail||fallback}
async function load(){loading.value=true;error.value='';try{const data=await getDepartmentOverview({date:selectedDate.value});rows.value=data.results;notes.value=data.notes}catch(e:any){rows.value=[];error.value=errorText(e,'科室概览加载失败')}finally{loading.value=false}}
async function loadVisits(page=1){if(!detail.value)return;visitLoading.value=true;visitError.value='';visitPage.value=page;try{const data=await getDepartmentVisits(detail.value.id,{date:selectedDate.value,page,page_size:10});visits.value=data.results;visitTotal.value=data.count}catch(e:any){visits.value=[];visitTotal.value=0;visitError.value=errorText(e,'当日就诊加载失败')}finally{visitLoading.value=false}}
async function loadCurrentVisits(){if(!detail.value)return;try{currentVisits.value=(await getDepartmentVisits(detail.value.id,{date:selectedDate.value,status:'in_progress',page:1,page_size:100})).results}catch{currentVisits.value=[]}}
async function loadDoctors(){if(!detail.value)return;doctorsLoading.value=true;doctorsError.value='';try{doctors.value=(await getDepartmentDoctors(detail.value.id,{date:selectedDate.value})).results}catch(e:any){doctors.value=[];doctorsError.value=errorText(e,'医师排班加载失败')}finally{doctorsLoading.value=false}}
async function loadHistory(page=1){if(!detail.value)return;historyLoading.value=true;historyError.value='';historyPage.value=page;try{const params:Record<string,unknown>={page,page_size:10,search:historySearch.value.trim()||undefined};if(historyRange.value){params.date_from=historyRange.value[0];params.date_to=historyRange.value[1]}const data=await getDepartmentHistoryPatients(detail.value.id,params);historyRows.value=data.results;historyTotal.value=data.count}catch(e:any){historyRows.value=[];historyTotal.value=0;historyError.value=errorText(e,'历史患者加载失败')}finally{historyLoading.value=false}}
async function openDetail(row:DepartmentOverview){detail.value=row;drawer.value=true;detailTab.value='overview';visits.value=[];currentVisits.value=[];visitPage.value=1;doctors.value=[];historyRows.value=[];historyPage.value=1;await Promise.all([loadVisits(),loadCurrentVisits(),loadDoctors(),loadHistory()])}
function changeDetailTab(name:string|number){if(name==='visits')loadVisits();else if(name==='doctors')loadDoctors();else if(name==='history')loadHistory()}
async function refreshDetail(){await load();const row=rows.value.find(item=>item.id===detail.value?.id);if(row)detail.value=row;await loadCurrentVisits();if(detailTab.value==='visits')await loadVisits(visitPage.value);else if(detailTab.value==='doctors')await loadDoctors();else if(detailTab.value==='history')await loadHistory(historyPage.value)}
function open(row?:Department){current.value=row||null;Object.assign(form,{name:row?.name||'',description:row?.description||''});dialog.value=true}
async function submit(){if(!form.name.trim()){ElMessage.warning('科室名称不能为空');return}saving.value=true;try{current.value?await updateDepartment(current.value.id,form):await createDepartment(form);ElMessage.success('科室信息已保存');dialog.value=false;await load()}catch(e:any){ElMessage.error(errorText(e,'保存失败'))}finally{saving.value=false}}
async function toggle(row:Department){try{await updateDepartment(row.id,{status:row.status==='active'?'inactive':'active'});ElMessage.success(row.status==='active'?'科室已停用':'科室已启用');await load()}catch(e:any){ElMessage.error(errorText(e,'状态更新失败'))}}
async function openPatient(patientId:number,extra:Record<string,unknown>={}){patientDrawer.value=true;patientLoading.value=true;patientProfile.value={patient_id:patientId,...extra};try{patientProfile.value={patient_id:patientId,...extra,...(await api.get(`patients/${patientId}/`)).data}}catch(e:any){ElMessage.error(errorText(e,'患者档案加载失败'))}finally{patientLoading.value=false}}
function openHistoryPatient(row:DepartmentHistoryPatient){openPatient(row.patient_id,{visit_count:row.visit_count,last_visit:row.last_visit})}
function openVisitPatient(row:Appointment){openPatient(row.patient_id)}
watch(selectedDate,()=>{load();if(drawer.value)refreshDetail()})
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading">
      <div><p class="eyebrow">DEPARTMENT OPERATIONS</p><h1>科室管理</h1><p>按日期查看科室预约、当前接诊、当班医师与历史患者；科室归属以预约时的科室快照为准。</p></div>
      <div class="intro-actions">
        <el-date-picker v-model="selectedDate" type="date" value-format="YYYY-MM-DD" :clearable="false" style="width:150px"/>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="open()">＋ 新增科室</el-button>
      </div>
    </div>
    <ListError v-if="error" :message="error" @retry="load"/>
    <div v-else v-loading="loading" class="department-grid">
      <el-card v-for="row in rows" :key="row.id" class="department-card" @click="openDetail(row)">
        <div class="department-head"><h3>{{row.name}}</h3><el-tag :type="row.status==='active'?'success':'info'">{{row.status==='active'?'启用':'停用'}}</el-tag></div>
        <p>{{row.description||'暂无科室介绍'}}</p>
        <div class="department-stats">
          <div><span>预约总数</span><b>{{row.stats.total}}</b></div>
          <div><span>待就诊</span><b>{{row.stats.pending}}</b></div>
          <div><span>就诊中</span><b class="active">{{row.stats.in_progress}}</b></div>
          <div><span>已完成</span><b>{{row.stats.completed}}</b></div>
          <div><span>当班医师</span><b>{{row.stats.active_doctors}}</b></div>
          <div><span>历史患者</span><b>{{row.stats.history_patients}}</b></div>
        </div>
        <div class="department-actions">
          <el-button link type="primary" @click.stop="openDetail(row)">查看详情 {{row.stats.in_progress?`（${row.stats.in_progress} 人在诊）`:''}}</el-button>
          <el-button link @click.stop="open(row)">编辑</el-button>
          <el-button link :type="row.status==='active'?'danger':'success'" @click.stop="toggle(row)">{{row.status==='active'?'停用':'启用'}}</el-button>
        </div>
      </el-card>
      <el-empty v-if="!loading&&!rows.length" description="暂无科室"/>
    </div>
    <div class="data-footnote"><span>统计口径</span><p>{{notes.history_patients||''}} {{notes.active_doctors||''}} {{notes.department_basis||''}}</p></div>

    <el-drawer v-model="drawer" :title="detail?`${detail.name} · ${selectedDate}`:'科室详情'" size="min(920px,96vw)">
      <div v-if="detail" class="department-detail">
        <div class="department-detail-head">
          <div><h2>{{detail.name}}</h2><p>{{detail.description||'暂无科室介绍'}}</p></div>
          <el-tag :type="detail.status==='active'?'success':'info'">{{detail.status==='active'?'启用':'停用'}}</el-tag>
        </div>
        <div v-if="stats" class="department-stats detail-stats">
          <div><span>预约总数</span><b>{{stats.total}}</b></div>
          <div><span>待就诊</span><b>{{stats.pending}}</b></div>
          <div><span>就诊中</span><b class="active">{{stats.in_progress}}</b></div>
          <div><span>已完成</span><b>{{stats.completed}}</b></div>
          <div><span>当班医师</span><b>{{stats.active_doctors}}</b></div>
          <div><span>历史患者</span><b>{{stats.history_patients}}</b></div>
        </div>
        <el-tabs v-model="detailTab" @tab-change="changeDetailTab">
          <el-tab-pane label="概览" name="overview">
            <div class="department-overview">
              <div><span>当前接诊患者</span><b>{{stats?.in_progress||0}} 人</b><small>预约状态为“就诊中”，可能同时多位</small></div>
              <div><span>待就诊</span><b>{{stats?.pending||0}} 人</b><small>已预约、尚未开始接诊</small></div>
              <div><span>历史患者</span><b>{{stats?.history_patients||0}} 人</b><small>该科室曾有未取消预约的去重患者</small></div>
            </div>
            <el-empty v-if="!currentVisits.length" :image-size="60" description="当前没有正在接诊的患者"/>
            <div v-else class="current-visits">
              <article v-for="item in currentVisits" :key="item.id">
                <b>{{item.patient_name}}</b><span>{{item.doctor_name}} · {{item.slot?.start_time?.slice(0,5)}}</span><small>{{item.reason}}</small>
              </article>
            </div>
          </el-tab-pane>
          <el-tab-pane label="当日就诊" name="visits">
            <ListError v-if="visitError" :message="visitError" @retry="loadVisits(visitPage)"/>
            <el-table v-else v-loading="visitLoading" :data="visits" empty-text="当日暂无预约" class="clickable-rows" @row-click="openVisitPatient">
              <el-table-column label="时间" width="95"><template #default="{row}">{{row.slot?.start_time?.slice(0,5)}}</template></el-table-column>
              <el-table-column prop="patient_name" label="患者" min-width="100"/>
              <el-table-column prop="doctor_name" label="主诊医师" min-width="100"/>
              <el-table-column prop="reason" label="就诊原因" min-width="180" show-overflow-tooltip/>
              <el-table-column label="病历" width="95"><template #default="{row}"><span v-if="row.record_id">{{row.record_status==='confirmed'?'已确认':'草稿'}}</span><span v-else class="cell-empty">未建立</span></template></el-table-column>
              <el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="statusInfo('appointment',row.status).tone">{{statusInfo('appointment',row.status).label}}</el-tag></template></el-table-column>
            </el-table>
            <div class="pagination"><span>共 {{visitTotal}} 条</span><el-pagination v-model:current-page="visitPage" layout="prev,pager,next" :total="visitTotal" :page-size="10" @current-change="loadVisits"/></div>
          </el-tab-pane>
          <el-tab-pane label="医师与排班" name="doctors">
            <ListError v-if="doctorsError" :message="doctorsError" @retry="loadDoctors"/>
            <div v-else v-loading="doctorsLoading" class="doctor-schedule-list">
              <article v-for="doctor in doctors" :key="doctor.id" class="doctor-schedule-card">
                <header><div><h3>{{doctor.full_name}}</h3><p>{{doctor.title||'—'}} · {{doctor.specialty||'暂无专业方向'}}</p></div><el-tag>{{doctor.schedule_count}} 个时段</el-tag></header>
                <p class="muted">{{doctor.introduction||'暂无医师简介'}}</p>
                <div class="schedule-chip-row">
                  <span v-for="schedule in doctor.schedules" :key="schedule.id" class="schedule-chip">{{schedule.time_range}} · 可约 {{schedule.available_slots}} / {{schedule.total_slots}}</span>
                </div>
              </article>
              <el-empty v-if="!doctorsLoading&&!doctors.length" description="该日期没有开放排班的医师"/>
            </div>
          </el-tab-pane>
          <el-tab-pane label="历史患者" name="history">
            <div class="table-tools history-tools">
              <el-date-picker v-model="historyRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期"/>
              <el-input v-model="historySearch" clearable placeholder="搜索姓名、患者编号或手机号" @keyup.enter="loadHistory(1)"/>
              <el-button @click="loadHistory(1)">查询</el-button>
            </div>
            <ListError v-if="historyError" :message="historyError" @retry="loadHistory(historyPage)"/>
            <el-table v-else v-loading="historyLoading" :data="historyRows" empty-text="暂无历史患者" class="clickable-rows" @row-click="openHistoryPatient">
              <el-table-column prop="patient_no" label="患者编号" width="120"/>
              <el-table-column prop="full_name" label="姓名" min-width="100"/>
              <el-table-column prop="phone" label="联系方式" min-width="130"/>
              <el-table-column prop="gender_display" label="性别" width="80"/>
              <el-table-column prop="visit_count" label="有效预约次数" width="120"/>
              <el-table-column label="最近就诊" width="120"><template #default="{row}">{{row.last_visit||'—'}}</template></el-table-column>
            </el-table>
            <div class="pagination"><span>共 {{historyTotal}} 位患者</span><el-pagination v-model:current-page="historyPage" layout="prev,pager,next" :total="historyTotal" :page-size="10" @current-change="loadHistory"/></div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>

    <el-drawer v-model="patientDrawer" title="患者档案" size="min(520px,94vw)">
      <div v-if="patientProfile" v-loading="patientLoading" class="record-detail">
        <div><span>患者编号</span><b>{{patientProfile.patient_no}}</b></div>
        <div><span>姓名</span><b>{{patientProfile.full_name}}</b></div>
        <div><span>联系方式 / 性别</span><b>{{patientProfile.phone||'—'}} · {{patientProfile.gender_display||'—'}}</b></div>
        <div><span>出生日期 / 血型</span><b>{{patientProfile.birth_date||'—'}} · {{patientProfile.blood_group||'—'}}</b></div>
        <div><span>过敏史</span><p>{{patientProfile.allergies||'无已知过敏'}}</p></div>
        <div><span>既往病史</span><p>{{patientProfile.medical_history||'—'}}</p></div>
        <div><span>本科室有效预约次数 / 最近就诊</span><b>{{patientProfile.visit_count||'—'}} 次 · {{patientProfile.last_visit||'—'}}</b></div>
        <div><span>建档时间</span><b>{{patientProfile.created_at?.replace('T',' ').slice(0,16)||'—'}}</b></div>
      </div>
    </el-drawer>

    <el-dialog v-model="dialog" :title="current?'编辑科室':'新增科室'" width="min(520px,94vw)">
      <el-form label-position="top"><el-form-item label="科室名称" required><el-input v-model="form.name"/></el-form-item><el-form-item label="科室介绍"><el-input v-model="form.description" type="textarea" :rows="5" maxlength="500" show-word-limit/></el-form-item></el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">保存</el-button></template>
    </el-dialog>
  </section>
</template>
