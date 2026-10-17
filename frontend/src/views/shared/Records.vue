<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import EventCard from'../../components/common/EventCard.vue'
import{useListState}from'../../composables/useListState'
import{statusInfo}from'../../utils/status'
import type{ViewMode}from'../../utils/view'
import{getAppointments}from'../../services/appointments'
import{addCorrection,completeVisit,confirmRecord,createRecord,getRecord,getRecords,updateRecord,type RecordPayload}from'../../services/records'
import type{Appointment,MedicalRecord}from'../../types/medical'

const auth=useAuthStore(),isDoctor=computed(()=>auth.user?.role==='doctor')
const state=useListState(`records-${auth.user?.role||'guest'}`,{page:1,view:'cards' as ViewMode})
const loading=ref(false),error=ref(''),rows=ref<MedicalRecord[]>([]),total=ref(0),editorOpen=ref(false),detailOpen=ref(false),saving=ref(false),current=ref<MedicalRecord|null>(null),appointments=ref<Appointment[]>([])
const blank=():RecordPayload=>({appointment_id:0,chief_complaint:'',present_illness:'',past_history:'',examination:'',diagnosis:'',treatment:''})
const form=reactive<RecordPayload>(blank())
async function load(){loading.value=true;error.value='';try{const data=await getRecords({page:state.page});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'病历加载失败'}finally{loading.value=false}}
async function openCreate(){current.value=null;Object.assign(form,blank());editorOpen.value=true;try{appointments.value=(await getAppointments({status:'in_progress',without_record:true})).rows}catch{appointments.value=[]}}
function openEdit(row:MedicalRecord){current.value=row;Object.assign(form,{appointment_id:row.appointment_id,chief_complaint:row.chief_complaint,present_illness:row.present_illness,past_history:row.past_history,examination:row.examination,diagnosis:row.diagnosis,treatment:row.treatment});editorOpen.value=true}
async function save(){if(!form.appointment_id){ElMessage.warning('请选择当前就诊');return}if(!form.chief_complaint.trim()||!form.diagnosis.trim()){ElMessage.warning('主诉和诊断不能为空');return}saving.value=true;try{const payload={chief_complaint:form.chief_complaint,present_illness:form.present_illness,past_history:form.past_history,examination:form.examination,diagnosis:form.diagnosis,treatment:form.treatment};if(current.value)await updateRecord(current.value.id,payload);else await createRecord(form);ElMessage.success('病历草稿已保存');editorOpen.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'病历保存失败')}finally{saving.value=false}}
async function confirm(row:MedicalRecord){try{await ElMessageBox.confirm('确认后原始内容将锁定，后续只能追加更正说明。','确认病历',{type:'warning'});await confirmRecord(row.id);ElMessage.success('病历已确认');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'确认失败')}}
async function complete(row:MedicalRecord){try{await ElMessageBox.confirm('完成后本次预约将归档为已完成。','完成诊疗',{type:'info'});await completeVisit(row.id);ElMessage.success('本次诊疗已完成');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'无法完成诊疗')}}
async function correct(row:MedicalRecord){try{const{value}=await ElMessageBox.prompt('请填写更正或补充说明，原始病历不会被覆盖。','追加更正',{inputType:'textarea',inputValidator:value=>Boolean(value.trim())||'内容不能为空'});await addCorrection(row.id,value.trim());ElMessage.success('更正说明已追加');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'追加失败')}}
async function view(row:MedicalRecord){try{current.value=await getRecord(row.id);detailOpen.value=true}catch{ElMessage.error('病历详情加载失败')}}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">ELECTRONIC MEDICAL RECORD</p><h1>{{isDoctor?'电子病历':'我的病历'}}</h1><p>{{isDoctor?'记录诊疗信息，确认病历后完成并归档本次诊疗':'查看医师已经确认的个人就诊记录'}}</p></div><div class="heading-actions"><router-link v-if="isDoctor" to="/doctor/records?tab=records"><el-button>诊疗档案</el-button></router-link><el-button v-if="isDoctor" type="primary" @click="openCreate">＋ 创建病历</el-button></div></div>
    <el-alert v-if="isDoctor" title="已确认病历不可直接覆盖；确认后可点击“完成诊疗”结束本次就诊" type="info" :closable="false" show-icon class="record-alert"/>
    <el-card class="table-card">
      <div class="table-tools"><span class="table-count">按就诊时间排列 · 共 {{total}} 条</span><ViewSwitch v-model="state.view"/></div>
      <div class="legend-row"><StatusLegend domain="record" title="病历状态"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="timeline-list">
        <EventCard v-for="row in rows" :key="row.id" :time="row.visit_at" :title="row.diagnosis||'未填写诊断'" :subtitle="`${row.record_no} · ${isDoctor?row.patient_name:row.doctor_name}`" :description="row.chief_complaint?`主诉：${row.chief_complaint}`:''">
          <template #status><el-tag :type="statusInfo('record',row.status).tone">{{statusInfo('record',row.status).label}}</el-tag></template>
          <template #actions><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="isDoctor"><el-button v-if="row.status==='draft'" link @click="openEdit(row)">编辑</el-button><el-button v-if="row.status==='draft'" link type="success" @click="confirm(row)">确认</el-button><template v-else><el-button link type="warning" @click="correct(row)">追加更正</el-button><el-button v-if="row.appointment_status==='in_progress'" link type="success" @click="complete(row)">完成诊疗</el-button></template></template></template>
        </EventCard>
        <el-empty v-if="!rows.length&&!loading" description="暂无病历记录"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows" empty-text="暂无病历记录" class="desktop-table">
          <el-table-column prop="record_no" label="病历编号" min-width="140"/>
          <el-table-column v-if="isDoctor" prop="patient_name" label="患者" min-width="110"/>
          <el-table-column v-else prop="doctor_name" label="医师" min-width="110"/>
          <el-table-column prop="visit_at" label="就诊时间" min-width="155"/>
          <el-table-column prop="diagnosis" label="诊断" min-width="200" show-overflow-tooltip/>
          <el-table-column label="状态" width="105"><template #default="{row}"><el-tag :type="statusInfo('record',row.status).tone">{{statusInfo('record',row.status).label}}</el-tag></template></el-table-column>
          <el-table-column label="操作" min-width="280" fixed="right"><template #default="{row}"><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="isDoctor"><el-button v-if="row.status==='draft'" link @click="openEdit(row)">编辑</el-button><el-button v-if="row.status==='draft'" link type="success" @click="confirm(row)">确认</el-button><template v-else><el-button link type="warning" @click="correct(row)">追加更正</el-button><el-button v-if="row.appointment_status==='in_progress'" link type="success" @click="complete(row)">完成诊疗</el-button></template></template></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in rows" :key="row.id" class="mobile-info-card">
            <header><h3>{{isDoctor?row.patient_name:row.doctor_name}}</h3><el-tag :type="statusInfo('record',row.status).tone">{{statusInfo('record',row.status).label}}</el-tag></header>
            <p class="mobile-sub">{{row.record_no}} · {{row.visit_at}}</p>
            <div class="mobile-line"><span>诊断</span><b>{{row.diagnosis}}</b></div>
            <div class="actions"><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="isDoctor"><el-button v-if="row.status==='draft'" link @click="openEdit(row)">编辑</el-button><el-button v-if="row.status==='draft'" link type="success" @click="confirm(row)">确认</el-button><template v-else><el-button link type="warning" @click="correct(row)">追加更正</el-button><el-button v-if="row.appointment_status==='in_progress'" link type="success" @click="complete(row)">完成诊疗</el-button></template></template></div>
          </article>
          <div v-if="!rows.length&&!loading" class="mobile-empty">暂无病历记录</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
    <el-dialog v-model="editorOpen" :title="current?'编辑病历草稿':'创建病历'" width="min(760px,95vw)" destroy-on-close><el-form label-position="top"><el-form-item label="当前就诊" required><el-select v-model="form.appointment_id" style="width:100%" :disabled="Boolean(current)" placeholder="选择就诊中的预约"><el-option v-for="item in appointments" :key="item.id" :label="`${item.patient_name} · ${item.slot.date} ${item.slot.start_time.slice(0,5)}`" :value="item.id"/></el-select></el-form-item><el-row :gutter="14"><el-col :md="12"><el-form-item label="主诉" required><el-input v-model="form.chief_complaint" type="textarea" :rows="3"/></el-form-item></el-col><el-col :md="12"><el-form-item label="现病史"><el-input v-model="form.present_illness" type="textarea" :rows="3"/></el-form-item></el-col><el-col :md="12"><el-form-item label="既往病史"><el-input v-model="form.past_history" type="textarea" :rows="3"/></el-form-item></el-col><el-col :md="12"><el-form-item label="检查情况"><el-input v-model="form.examination" type="textarea" :rows="3"/></el-form-item></el-col></el-row><el-form-item label="诊断" required><el-input v-model="form.diagnosis" type="textarea" :rows="2"/></el-form-item><el-form-item label="治疗建议"><el-input v-model="form.treatment" type="textarea" :rows="3"/></el-form-item></el-form><template #footer><el-button @click="editorOpen=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存草稿</el-button></template></el-dialog>
    <el-drawer v-model="detailOpen" title="病历详情" size="min(620px,94vw)"><div v-if="current" class="record-detail"><div><span>患者</span><b>{{current.patient_name}}</b></div><div><span>医师</span><b>{{current.doctor_name}}</b></div><div><span>主诉</span><p>{{current.chief_complaint||'—'}}</p></div><div><span>现病史</span><p>{{current.present_illness||'—'}}</p></div><div><span>既往病史</span><p>{{current.past_history||'—'}}</p></div><div><span>检查情况</span><p>{{current.examination||'—'}}</p></div><div><span>诊断</span><p>{{current.diagnosis||'—'}}</p></div><div><span>治疗建议</span><p>{{current.treatment||'—'}}</p></div><section v-if="current.corrections?.length"><h3>更正记录</h3><article v-for="item in current.corrections" :key="item.id"><b>{{item.author_name}} · {{item.created_at}}</b><p>{{item.content}}</p></article></section></div></el-drawer>
  </section>
</template>
