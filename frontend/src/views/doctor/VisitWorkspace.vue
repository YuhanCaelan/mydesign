<script setup lang="ts">
import{computed,onBeforeUnmount,onMounted,reactive,ref}from'vue'
import{onBeforeRouteLeave,useRoute,useRouter}from'vue-router'
import{ElMessage,ElMessageBox}from'element-plus'
import api from'../../services/api'
import{confirmRecord,createRecord,completeVisit,getClinicalHistory,updateRecord}from'../../services/records'
import{getDepartments,startAppointment}from'../../services/appointments'
import{downloadMedicalFile,getExaminations}from'../../services/examinations'
import{statusInfo}from'../../utils/status'
import type{Appointment,ClinicalHistory,Department,ExaminationOrder,InpatientAdmission,MedicalRecord,PageResult,PatientSummary,Prescription}from'../../types/medical'

interface Workspace{appointment:Appointment;patient:PatientSummary&Record<string,any>;current_record:MedicalRecord|null;history:MedicalRecord[];history_count:number;prescriptions:Prescription[];examinations:ExaminationOrder[];admissions:InpatientAdmission[]}
type TabName='current'|'history'|'examinations'|'care'
const route=useRoute(),router=useRouter(),loading=ref(false),saving=ref(false),data=ref<Workspace|null>(null),activeTab=ref<TabName>('current')
const form=reactive({chief_complaint:'',present_illness:'',past_history:'',examination:'',diagnosis:'',treatment:''})
const baseline=ref(''),lastSaved=ref(''),departments=ref<Department[]>([])
const history=ref<ClinicalHistory|null>(null),historyLoading=ref(false),historyPage=ref(1),historyFilters=reactive({range:null as [string,string]|null,department:'' as string|number,diagnosis:'',search:''})
const exams=ref<PageResult<ExaminationOrder>|null>(null),examLoading=ref(false),examPage=ref(1),examStatus=ref('')
const appointmentId=computed(()=>Number(route.params.appointmentId))
const patientId=computed(()=>data.value?.patient?.id)
const returnPath=computed(()=>typeof route.query.returnTo==='string'&&route.query.returnTo.startsWith('/')?route.query.returnTo:'/doctor/outpatient?tab=appointments')
const currentLocked=computed(()=>data.value?.appointment.status!=='in_progress'||data.value?.current_record?.status==='confirmed')
const dirty=computed(()=>Boolean(data.value)&&snapshot()!==baseline.value&&!currentLocked.value)

function snapshot(){return JSON.stringify(form)}
function errorText(e:any,fallback:string){const body=e.response?.data;if(body?.errors){const first=Object.values(body.errors)[0] as any;return Array.isArray(first)?first.join('；'):String(first)}return body?.detail||fallback}
function fill(record:MedicalRecord|null){Object.assign(form,{chief_complaint:record?.chief_complaint||'',present_illness:record?.present_illness||'',past_history:record?.past_history||'',examination:record?.examination||'',diagnosis:record?.diagnosis||'',treatment:record?.treatment||''});baseline.value=snapshot();lastSaved.value=record?.updated_at?record.updated_at.replace('T',' ').slice(0,16):''}
async function load(){loading.value=true;try{data.value=(await api.get(`appointments/${appointmentId.value}/workspace/`)).data;fill(data.value?.current_record||null)}catch(e:any){ElMessage.error(errorText(e,'诊疗工作区加载失败'))}finally{loading.value=false}}
async function loadHistory(target=1){if(!patientId.value)return;historyLoading.value=true;historyPage.value=target;try{const params:Record<string,unknown>={page:target,page_size:10};if(historyFilters.range){params.date_from=historyFilters.range[0];params.date_to=historyFilters.range[1]}if(historyFilters.department)params.department=historyFilters.department;if(historyFilters.diagnosis.trim())params.diagnosis=historyFilters.diagnosis.trim();if(historyFilters.search.trim())params.search=historyFilters.search.trim();history.value=await getClinicalHistory(patientId.value,params)}catch(e:any){history.value=null;ElMessage.error(errorText(e,'历史病历加载失败'))}finally{historyLoading.value=false}}
async function loadExams(target=1){if(!patientId.value)return;examLoading.value=true;examPage.value=target;try{exams.value=await getExaminations({patient:patientId.value,page:target,page_size:10,status:examStatus.value||undefined})}catch(e:any){exams.value=null;ElMessage.error(errorText(e,'历史检查加载失败'))}finally{examLoading.value=false}}
async function changeTab(name:string|number){if(name==='history'&&!history.value)await loadHistory(1);if(name==='examinations'&&!exams.value)await loadExams(1)}
async function begin(){try{await startAppointment(appointmentId.value);ElMessage.success('已开始接诊');await load()}catch(e:any){ElMessage.error(errorText(e,'无法开始接诊'))}}
async function save(){if(!form.chief_complaint.trim()||!form.diagnosis.trim()){ElMessage.warning('主诉和诊断不能为空');return}saving.value=true;try{const current=data.value?.current_record;if(current)await updateRecord(current.id,{...form});else await createRecord({appointment_id:appointmentId.value,...form});ElMessage.success('病历草稿已保存');await load()}catch(e:any){ElMessage.error(errorText(e,'病历保存失败'))}finally{saving.value=false}}
async function confirm(){const record=data.value?.current_record;if(!record)return;try{await ElMessageBox.confirm(`诊断：${form.diagnosis}\n处理意见：${form.treatment||'—'}\n\n确认后原始病历将锁定，只能追加更正。`,'确认前核对',{type:'warning',confirmButtonText:'确认病历'});await confirmRecord(record.id);ElMessage.success('病历已确认');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'确认失败'))}}
async function finish(){const record=data.value?.current_record;if(!record)return;try{await ElMessageBox.confirm('完成后本次预约将归档为已完成。','完成诊疗');await completeVisit(record.id);ElMessage.success('诊疗已完成');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(errorText(e,'无法完成诊疗'))}}
async function download(id:number,name:string){try{await downloadMedicalFile(id,name)}catch{ElMessage.error('附件下载失败或无权访问')}}
function resetHistory(){Object.assign(historyFilters,{range:null,department:'',diagnosis:'',search:''});loadHistory(1)}
function prescriptionNames(row:Prescription){return row.items?.map(item=>item.medicine_name).filter(Boolean).join('、')||row.notes||'—'}
function jumpToRecord(recordNo?:string){if(!recordNo)return;activeTab.value='history';historyFilters.search=recordNo;loadHistory(1)}
async function guardLeave(){if(!dirty.value)return true;try{await ElMessageBox.confirm('本次病历有未保存的修改，离开后将丢失。确定离开吗？','未保存的修改',{type:'warning',confirmButtonText:'仍然离开'});return true}catch{return false}}
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue=''}}
onBeforeRouteLeave(async()=>await guardLeave())
onMounted(async()=>{window.addEventListener('beforeunload',beforeUnload);await load();try{departments.value=await getDepartments()}catch{departments.value=[]}})
onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload))
</script>

<template>
  <section v-loading="loading">
    <div class="page-heading visit-heading">
      <div><el-button link @click="router.push(returnPath)">← {{returnPath==='/dashboard'?'返回工作台':'返回接诊列表'}}</el-button><h1>诊疗工作区</h1><p v-if="data">{{data.appointment.appointment_no}} · {{data.appointment.slot.date}} {{data.appointment.slot.start_time.slice(0,5)}} · {{data.appointment.department_name}}</p></div>
      <div v-if="data" class="visit-actions"><el-tag size="large" :type="statusInfo('appointment',data.appointment.status).tone">{{statusInfo('appointment',data.appointment.status).label}}</el-tag><el-button v-if="data.appointment.status==='pending'" type="primary" @click="begin">开始接诊</el-button><el-button v-if="data.current_record?.status==='confirmed'&&data.appointment.status==='in_progress'" type="success" @click="finish">完成诊疗</el-button></div>
    </div>
    <template v-if="data">
      <div class="patient-band">
        <div><span>患者</span><strong>{{data.patient.full_name}}</strong><small>{{data.patient.patient_no}} · {{data.patient.gender_display||'未填写'}} · {{data.patient.phone||'无手机号'}}</small></div>
        <div><span>过敏史</span><b>{{data.patient.allergies||'无已知过敏'}}</b></div>
        <div><span>既往病史</span><b>{{data.patient.medical_history||'未记录'}}</b></div>
        <div><span>本次就诊原因</span><b>{{data.appointment.reason}}</b></div>
      </div>

      <el-card class="visit-tabs-card">
        <el-tabs v-model="activeTab" @tab-change="changeTab">
          <el-tab-pane label="本次病历" name="current">
            <template #label><span>本次病历</span></template>
            <div class="editor-head">
              <div><h2>本次病历</h2><p>{{data.current_record?data.current_record.record_no:'本次就诊尚未建立病历'}}<template v-if="lastSaved"> · 草稿保存于 {{lastSaved}}</template></p></div>
              <el-tag v-if="data.current_record" :type="statusInfo('record',data.current_record.status).tone">{{statusInfo('record',data.current_record.status).label}}</el-tag>
            </div>
            <el-alert v-if="data.appointment.status==='pending'" title="请先开始接诊，再建立本次病历。" type="warning" :closable="false"/>
            <el-alert v-else-if="dirty" title="病历有未保存修改；离开页面前请保存草稿。" type="warning" :closable="false" show-icon/>
            <el-form label-position="top" :disabled="currentLocked">
              <section class="editor-section"><h3>主诉与病史</h3><el-row :gutter="14"><el-col :md="12"><el-form-item label="主诉" required><el-input v-model="form.chief_complaint" type="textarea" :rows="3" placeholder="患者本次就诊的主要症状与持续时间"/></el-form-item></el-col><el-col :md="12"><el-form-item label="现病史"><el-input v-model="form.present_illness" type="textarea" :rows="3" placeholder="起病、演变、伴随症状与诊疗经过"/></el-form-item></el-col><el-col :md="24"><el-form-item label="既往病史"><el-input v-model="form.past_history" type="textarea" :rows="2" placeholder="慢性病、手术史、过敏史等；可参考历史但不自动覆盖"/></el-form-item></el-col></el-row></section>
              <section class="editor-section"><h3>检查与诊断</h3><el-row :gutter="14"><el-col :md="12"><el-form-item label="体格 / 辅助检查"><el-input v-model="form.examination" type="textarea" :rows="3"/></el-form-item></el-col><el-col :md="12"><el-form-item label="诊断" required><el-input v-model="form.diagnosis" type="textarea" :rows="3" placeholder="本次诊断结论"/></el-form-item></el-col></el-row></section>
              <section class="editor-section"><h3>处理意见</h3><el-form-item label="治疗方案 / 随访建议"><el-input v-model="form.treatment" type="textarea" :rows="3"/></el-form-item></section>
            </el-form>
            <div v-if="!currentLocked" class="editor-actions"><el-button type="primary" :loading="saving" @click="save">保存草稿</el-button><el-button v-if="data.current_record" type="success" plain @click="confirm">确认病历</el-button></div>
            <el-alert v-if="data.current_record?.status==='confirmed'" title="病历已确认，原始内容不可覆盖；如需补充请在电子病历页追加更正。" type="success" :closable="false"/>
          </el-tab-pane>

          <el-tab-pane label="历次就诊" name="history">
            <div class="table-tools history-tools">
              <el-date-picker v-model="historyFilters.range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width:240px"/>
              <el-select v-model="historyFilters.department" clearable placeholder="全部科室" style="width:160px"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
              <el-input v-model="historyFilters.diagnosis" clearable placeholder="诊断" style="width:140px" @keyup.enter="loadHistory(1)"/>
              <el-input v-model="historyFilters.search" clearable placeholder="病历号 / 主诉" style="width:180px" @keyup.enter="loadHistory(1)"/>
              <el-button @click="loadHistory(1)">查询</el-button><el-button link @click="resetHistory">重置</el-button>
              <span class="workflow-hint">已确认病历 {{history?.count||0}} 份</span>
            </div>
            <div v-loading="historyLoading" class="history-board">
              <el-collapse v-if="history?.results.length">
                <el-collapse-item v-for="record in history.results" :key="record.id" :name="record.id">
                  <template #title><div class="history-title"><b>{{record.visit_at}} · {{record.department_name||'—'}}</b><span>{{record.doctor_name}} · {{record.record_no}}</span><strong>{{record.diagnosis}}</strong></div></template>
                  <div class="record-detail">
                    <div><span>主诉</span><p>{{record.chief_complaint}}</p></div>
                    <div><span>现病史 / 既往史</span><p>{{record.present_illness||'—'}} / {{record.past_history||'—'}}</p></div>
                    <div><span>体格 / 辅助检查</span><p>{{record.examination||'—'}}</p></div>
                    <div><span>处理意见</span><p>{{record.treatment||'—'}}</p></div>
                    <div><span>确认时间</span><b>{{record.confirmed_at?.replace('T',' ').slice(0,16)||'—'}}</b></div>
                    <div><span>关联事项</span><b>{{record.prescription_count||0}} 张处方 · {{record.admission_count||0}} 条住院记录</b></div>
                    <section v-if="record.examinations?.length"><h3>关联检查</h3>
                      <article v-for="exam in record.examinations" :key="exam.id">
                        <b>{{exam.order_no}} · {{exam.item_name}} · {{statusInfo('examination',exam.status).label}}</b>
                        <p v-if="exam.report">结论：{{exam.report.conclusion}}<template v-if="exam.report.published_at">（发布 {{exam.report.published_at.replace('T',' ').slice(0,16)}}）</template></p>
                        <p v-else>尚未发布报告。</p>
                        <button v-for="file in exam.files" :key="file.id" class="file-link" @click="download(file.id,file.original_name)">{{file.original_name}} <span>{{(file.size/1024).toFixed(1)}} KB</span></button>
                      </article>
                    </section>
                    <section v-if="record.corrections?.length"><h3>更正记录</h3><article v-for="item in record.corrections" :key="item.id"><b>{{item.author_name}} · {{item.created_at.replace('T',' ').slice(0,16)}}</b><p>{{item.content}}</p></article></section>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-empty v-else-if="!historyLoading" description="暂无符合条件的已确认病历"/>
            </div>
            <div class="pagination"><span>共 {{history?.count||0}} 份</span><el-pagination v-model:current-page="historyPage" layout="prev,pager,next" :total="history?.count||0" :page-size="10" @current-change="loadHistory"/></div>
          </el-tab-pane>

          <el-tab-pane label="历次检查" name="examinations">
            <div class="table-tools">
              <el-select v-model="examStatus" clearable placeholder="全部状态" style="width:160px" @change="loadExams(1)"><el-option label="已申请" value="requested"/><el-option label="检查中" value="in_progress"/><el-option label="报告待发布" value="completed"/><el-option label="已发布" value="published"/><el-option label="已取消" value="cancelled"/></el-select>
              <el-button @click="loadExams(1)">刷新</el-button>
              <span class="workflow-hint">报告与附件按当前业务权限展示；未发布报告不会向患者提前展示。</span>
            </div>
            <el-table v-loading="examLoading" :data="exams?.results||[]" empty-text="暂无历史检查">
              <el-table-column type="expand"><template #default="{row}"><div class="record-detail exam-expand"><div><span>检查目的</span><p>{{row.clinical_question}}</p></div><template v-if="row.report"><div><span>检查所见</span><p>{{row.report.findings}}</p></div><div><span>检查结论</span><p>{{row.report.conclusion}}</p></div><div><span>报告发布时间</span><b>{{row.report.published_at?.replace('T',' ').slice(0,16)||row.report.updated_at?.replace('T',' ').slice(0,16)||'未发布'}}</b></div></template><section v-if="row.files?.length"><h3>授权附件</h3><button v-for="file in row.files" :key="file.id" class="file-link" @click="download(file.id,file.original_name)">{{file.original_name}} <span>{{(file.size/1024).toFixed(1)}} KB</span></button></section><el-empty v-if="!row.report" :image-size="50" description="报告尚未录入或发布"/></div></template></el-table-column>
              <el-table-column prop="order_no" label="申请单号" min-width="140"/>
              <el-table-column prop="item_name_snapshot" label="检查项目" min-width="150"/>
              <el-table-column prop="visit_date" label="就诊日期" width="110"/>
              <el-table-column prop="record_no" label="对应病历" min-width="130"><template #default="{row}"><el-button v-if="row.record_no" link type="primary" @click="jumpToRecord(row.record_no)">{{row.record_no}} ↗</el-button><span v-else class="cell-empty">—</span></template></el-table-column>
              <el-table-column prop="department_name" label="科室" min-width="110"/>
              <el-table-column prop="created_at" label="申请时间" min-width="150"><template #default="{row}">{{row.created_at?.replace('T',' ').slice(0,16)}}</template></el-table-column>
              <el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusInfo('examination',row.status).tone">{{statusInfo('examination',row.status).label}}</el-tag></template></el-table-column>
            </el-table>
            <div class="pagination"><span>共 {{exams?.count||0}} 条</span><el-pagination v-model:current-page="examPage" layout="prev,pager,next" :total="exams?.count||0" :page-size="10" @current-change="loadExams"/></div>
          </el-tab-pane>

          <el-tab-pane label="处方与住院" name="care">
            <div class="care-grid">
              <el-card><template #header><div class="section-head"><div><h2>本次处方</h2><p>{{data.prescriptions.length}} 张处方</p></div><router-link to="/doctor/clinical?tab=prescriptions"><el-button link type="primary">全部处方</el-button></router-link></div></template>
                <el-table :data="data.prescriptions" empty-text="本次就诊暂无处方"><el-table-column prop="prescription_no" label="处方号" min-width="140"/><el-table-column label="药品"><template #default="{row}">{{prescriptionNames(row)}}</template></el-table-column><el-table-column label="金额" width="100"><template #default="{row}">¥{{row.total_amount}}</template></el-table-column><el-table-column prop="status" label="状态" width="110"><template #default="{row}">{{row.status==='dispensed'?'已取药':row.status==='cancelled'?'已作废':'待缴费取药'}}</template></el-table-column></el-table>
              </el-card>
              <el-card><template #header><div class="section-head"><div><h2>住院记录</h2><p>该患者最近住院情况</p></div><router-link to="/doctor/inpatient?tab=admissions"><el-button link type="primary">住院管理</el-button></router-link></div></template>
                <el-table :data="data.admissions" empty-text="暂无住院记录"><el-table-column prop="admission_no" label="住院号" min-width="140"/><el-table-column prop="department_name" label="科室" min-width="110"/><el-table-column label="床位" min-width="100"><template #default="{row}">{{row.ward}} {{row.bed_no}}</template></el-table-column><el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="statusInfo('inpatient',row.status).tone">{{statusInfo('inpatient',row.status).label}}</el-tag></template></el-table-column><el-table-column label="操作" width="90"><template #default="{row}"><router-link :to="{path:`/doctor/inpatients/${row.id}`,query:{returnTo:route.fullPath}}"><el-button link type="primary">详情</el-button></router-link></template></el-table-column></el-table>
              </el-card>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </template>
  </section>
</template>
