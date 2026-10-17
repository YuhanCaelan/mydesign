<script setup lang="ts">
import{computed,onBeforeUnmount,onMounted,ref,watch}from'vue'
import{useRoute,useRouter}from'vue-router'
import{ElMessage}from'element-plus'
import{Refresh}from'@element-plus/icons-vue'
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import PatientRail from'../../components/archive/PatientRail.vue'
import RecordTimeline from'../../components/archive/RecordTimeline.vue'
import RecordReader from'../../components/archive/RecordReader.vue'
import ReportTimeline from'../../components/reports/ReportTimeline.vue'
import ReportReader from'../../components/reports/ReportReader.vue'
import ListError from'../../components/common/ListError.vue'
import{useAuthStore}from'../../stores/auth'
import{getMyPatient,getPatient,searchPatients}from'../../services/archive'
import{getClinicalHistory}from'../../services/records'
import{getExaminations}from'../../services/examinations'
import type{ClinicalHistory,ExaminationOrder,MedicalRecord,PatientSummary}from'../../types/medical'

const auth=useAuthStore(),route=useRoute(),router=useRouter()
const role=computed(()=>auth.user!.role),isDoctor=computed(()=>role.value==='doctor')
const activeTab=computed<'records'|'reports'>(()=>route.query.tab==='reports'?'reports':'records')

const patient=ref<PatientSummary|null>(null),patientId=ref<number|null>(null),patientError=ref(''),booting=ref(true)
const patients=ref<PatientSummary[]>([]),patientKeyword=ref(''),patientLoading=ref(false)
const history=ref<ClinicalHistory|null>(null),historyLoading=ref(false),historyError=ref(''),historyPage=ref(1),historyLoaded=ref(false)
const historyRange=ref<[string,string]|null>(null),historyDiagnosis=ref(''),historyKeyword=ref('')
const reports=ref<ExaminationOrder[]>([]),reportTotal=ref(0),reportLoading=ref(false),reportError=ref(''),reportPage=ref(1),reportsLoaded=ref(false)
const reportRange=ref<[string,string]|null>(null),reportType=ref(''),reportStatus=ref(''),reportKeyword=ref('')
const recordOpen=ref(false),currentRecord=ref<MedicalRecord|null>(null)
const reportOpen=ref(false),currentReport=ref<ExaminationOrder|null>(null)
let patientTimer=0

const typeOptions=[['blood','血液检查'],['lab','常规检验'],['xray','X-Ray'],['ct','CT'],['mri','MRI'],['other','其他检查']]
const reportStatusOptions=[['','全部状态'],['published','已发布'],['completed','报告待发布'],['in_progress','检查中'],['requested','已申请']]
const tabDefs=computed<FolderTab[]>(()=>[
  {key:'records',label:'历史病历',hint:`${history.value?.count||0} 份`},
  {key:'reports',label:'检查报告',hint:`${reportTotal.value} 份`},
])
const reportIndex=computed(()=>{const index=reports.value.findIndex(order=>order.id===currentReport.value?.id);return index>=0?index+1:0})
const patientMeta=computed(()=>[patient.value?.patient_no,patient.value?.gender_display,ageText(patient.value?.birth_date)].filter(Boolean).join(' · '))
const lastVisit=computed(()=>history.value?.results[0]?.visit_at||'—')

function ageText(birth?:string|null){
  if(!birth)return''
  const born=new Date(birth)
  if(Number.isNaN(born.getTime()))return''
  const now=new Date();let years=now.getFullYear()-born.getFullYear()
  if(now.getMonth()<born.getMonth()||(now.getMonth()===born.getMonth()&&now.getDate()<born.getDate()))years-=1
  return years>=0?`${years} 岁`:''
}
function queryNumber(value:unknown){const raw=Array.isArray(value)?value[0]:value;const number=Number(raw);return Number.isFinite(number)&&number>0?number:null}
function queryString(value:unknown){return typeof value==='string'?value:''}
function errorText(error:any,fallback:string){return error?.response?.data?.detail||error?.response?.data?.errors?.detail||fallback}

async function searchPatientList(){
  patientLoading.value=true
  try{const data=await searchPatients({search:patientKeyword.value.trim()||undefined,page_size:20});patients.value=data.results}
  catch(error:any){ElMessage.error(errorText(error,'患者列表加载失败'))}
  finally{patientLoading.value=false}
}
async function loadHistory(target=1){
  if(!patientId.value)return
  historyLoading.value=true;historyError.value=''
  try{
    const params:Record<string,unknown>={page:target,page_size:10}
    if(historyRange.value){params.date_from=historyRange.value[0];params.date_to=historyRange.value[1]}
    if(historyDiagnosis.value.trim())params.diagnosis=historyDiagnosis.value.trim()
    if(historyKeyword.value.trim())params.search=historyKeyword.value.trim()
    history.value=await getClinicalHistory(patientId.value,params);historyPage.value=target;historyLoaded.value=true
    if(!patient.value)patient.value=history.value.patient
  }catch(error:any){historyError.value=errorText(error,'历史病历加载失败')}
  finally{historyLoading.value=false}
}
async function loadReports(target=1){
  if(!patientId.value)return
  reportLoading.value=true;reportError.value=''
  try{
    const params:Record<string,unknown>={patient:patientId.value,page:target,page_size:10,ordering:'-report__published_at'}
    if(reportRange.value){params.date_from=reportRange.value[0];params.date_to=reportRange.value[1]}
    if(reportType.value)params.type=reportType.value
    if(reportStatus.value)params.status=reportStatus.value
    if(reportKeyword.value.trim())params.search=reportKeyword.value.trim()
    const data=await getExaminations(params)
    reports.value=data.results;reportTotal.value=data.count;reportPage.value=target;reportsLoaded.value=true
    await applyReportQuery()
  }catch(error:any){reportError.value=errorText(error,'检查报告加载失败');reports.value=[];reportTotal.value=0}
  finally{reportLoading.value=false}
}
async function loadAll(){await Promise.all([loadHistory(1),loadReports(1)])}

function selectPatient(next:PatientSummary){
  if(patientId.value===next.id)return
  patient.value=next;patientId.value=next.id;history.value=null;reports.value=[];reportTotal.value=0
  historyLoaded.value=false;reportsLoaded.value=false;recordOpen.value=false;reportOpen.value=false;currentReport.value=null
  const query:Record<string,unknown>={...route.query,patient:next.id};delete query.report
  router.replace({query:query as any})
  void loadAll()
}
async function pickPatientById(id:number){
  try{
    const found=patients.value.find(item=>item.id===id)||await getPatient(id)
    patient.value=found;patientId.value=found.id
    await loadAll()
  }catch(error:any){patientError.value=errorText(error,'患者档案加载失败或无权限访问')}
}

async function openReportByNo(orderNo:string){
  recordOpen.value=false
  if(activeTab.value!=='reports')router.replace({query:{...route.query,tab:'reports'}})
  let found=reports.value.find(order=>order.order_no===orderNo)
  if(!found&&patientId.value){
    try{const data=await getExaminations({search:orderNo,patient:patientId.value,page_size:1});found=data.results[0]}
    catch{found=undefined}
  }
  if(found)openReport(found)
  else ElMessage.warning('报告尚未发布或无权访问')
}
function openReport(order:ExaminationOrder){
  currentReport.value=order;reportOpen.value=true
  router.replace({query:{...route.query,tab:'reports',report:order.order_no}})
}
function closeReport(){
  reportOpen.value=false
  if(route.query.report){const query:Record<string,unknown>={...route.query};delete query.report;router.replace({query:query as any})}
}
function stepReport(step:number){
  const index=reports.value.findIndex(order=>order.id===currentReport.value?.id)
  if(index<0)return
  const target=reports.value[index+step]
  if(target)openReport(target)
}
async function applyReportQuery(){
  const orderNo=queryString(route.query.report)
  if(!orderNo){reportOpen.value=false;currentReport.value=null;return}
  if(currentReport.value?.order_no===orderNo){reportOpen.value=true;return}
  let found=reports.value.find(order=>order.order_no===orderNo)
  if(!found&&patientId.value){
    try{const data=await getExaminations({search:orderNo,patient:patientId.value,page_size:1});found=data.results[0]}
    catch{found=undefined}
  }
  if(found){currentReport.value=found;reportOpen.value=true}
  else{reportOpen.value=false;ElMessage.warning('报告不存在或无权访问')}
}
function openRecord(record:MedicalRecord){currentRecord.value=record;recordOpen.value=true}

function setTab(tab:string){
  if(tab!==activeTab.value)router.replace({query:{...route.query,tab}})
  if(tab==='records'&&!historyLoaded.value)void loadHistory(1)
  if(tab==='reports'&&!reportsLoaded.value)void loadReports(1)
}
function searchRecords(){void loadHistory(1)}
function resetRecords(){historyRange.value=null;historyDiagnosis.value='';historyKeyword.value='';void loadHistory(1)}
function searchReports(){void loadReports(1)}
function resetReports(){reportRange.value=null;reportType.value='';reportStatus.value='';reportKeyword.value='';void loadReports(1)}
async function refresh(){
  if(isDoctor.value)await searchPatientList()
  if(!patientId.value)return
  if(isDoctor.value){try{patient.value=await getPatient(patientId.value)}catch{/* 保留现有患者信息 */}}
  else{try{patient.value=await getMyPatient()}catch{/* 保留现有患者信息 */}}
  await Promise.all([loadHistory(historyPage.value),loadReports(reportPage.value)])
}
async function init(){
  booting.value=true;patientError.value=''
  if(isDoctor.value){
    await searchPatientList()
    const id=queryNumber(route.query.patient)
    if(id)await pickPatientById(id)
  }else{
    try{const me=await getMyPatient();patient.value=me;patientId.value=me.id;await loadAll()}
    catch(error:any){patientError.value=errorText(error,'个人诊疗档案加载失败')}
  }
  booting.value=false
}

watch(patientKeyword,()=>{window.clearTimeout(patientTimer);patientTimer=window.setTimeout(()=>void searchPatientList(),280)})
watch(()=>route.query.patient,value=>{
  if(!isDoctor.value)return
  const id=queryNumber(value)
  if(id&&id!==patientId.value)void pickPatientById(id)
})
watch(()=>route.query.report,()=>void applyReportQuery())
watch(()=>route.query.tab,value=>{
  if(value==='reports'&&!reportsLoaded.value)void loadReports(1)
  if(value==='records'&&!historyLoaded.value)void loadHistory(1)
})
watch(reportOpen,value=>{if(!value)closeReport()})
onMounted(init)
onBeforeUnmount(()=>window.clearTimeout(patientTimer))
</script>

<template>
  <section v-loading="booting" class="archive-page">
    <div class="page-heading archive-heading">
      <div>
        <p class="eyebrow">PATIENT ARCHIVE</p>
        <h1>{{isDoctor?'患者诊疗档案':'我的诊疗档案'}}</h1>
        <p>{{isDoctor?'选择患者，在一个页面查看其历史病历与全部检查报告':'历史病历与检查报告集中在这里，一次找到'}}</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" @click="refresh">刷新</el-button>
      </div>
    </div>

    <ListError v-if="patientError" :message="patientError" @retry="init"/>
    <div v-else class="archive-layout" :class="{'archive-layout-patient':!isDoctor}">
      <PatientRail
        v-if="isDoctor"
        :items="patients"
        :selected="patientId"
        :keyword="patientKeyword"
        :loading="patientLoading"
        @update:keyword="patientKeyword=$event"
        @select="selectPatient"
        @search="searchPatientList"/>
      <div class="archive-main">
        <template v-if="patient">
          <section class="archive-patient" aria-label="患者基本信息">
            <div class="archive-patient-main">
              <span class="archive-avatar" aria-hidden="true">{{patient.full_name?.slice(0,1)||'患'}}</span>
              <div>
                <h2>{{patient.full_name}}</h2>
                <p>{{patientMeta||'未填写基础信息'}} <span v-if="patient.phone">· {{patient.phone}}</span></p>
              </div>
            </div>
            <dl class="archive-patient-facts">
              <div><dt>过敏史</dt><dd>{{patient.allergies||'无已知过敏'}}</dd></div>
              <div><dt>既往病史</dt><dd>{{patient.medical_history||'未记录'}}</dd></div>
              <div><dt>血型</dt><dd>{{patient.blood_group||'—'}}</dd></div>
            </dl>
            <div class="archive-counts">
              <div><b>{{history?.count||0}}</b><span>历史病历</span></div>
              <div><b>{{reportTotal}}</b><span>检查报告</span></div>
              <div><b>{{lastVisit}}</b><span>最近就诊</span></div>
            </div>
          </section>

          <div class="archive-tabs-bar">
            <FolderTabs :tabs="tabDefs" :model-value="activeTab" aria-label="诊疗档案页签" @update:model-value="setTab"/>
            <span class="archive-tabs-note">{{activeTab==='records'?'按就诊时间倒序，仅展示已确认病历':'按报告发布时间倒序；患者仅可见已发布报告'}}</span>
          </div>

          <section v-if="activeTab==='records'" class="archive-panel" aria-label="历史病历">
            <div class="archive-toolbar">
              <el-date-picker v-model="historyRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width:240px"/>
              <el-input v-model="historyDiagnosis" clearable placeholder="诊断" style="width:150px" @keyup.enter="searchRecords"/>
              <el-input v-model="historyKeyword" clearable placeholder="病历号 / 主诉" style="width:180px" @keyup.enter="searchRecords"/>
              <el-button type="primary" plain @click="searchRecords">查询</el-button>
              <el-button link @click="resetRecords">重置</el-button>
              <span class="workflow-hint">共 {{history?.count||0}} 份已确认病历</span>
            </div>
            <RecordTimeline :records="history?.results||[]" :loading="historyLoading" :error="historyError" @open="openRecord" @retry="loadHistory(historyPage)"/>
            <div class="pagination"><span>共 {{history?.count||0}} 份</span><el-pagination v-model:current-page="historyPage" layout="prev,pager,next" :total="history?.count||0" :page-size="10" @current-change="loadHistory"/></div>
          </section>

          <section v-else class="archive-panel" aria-label="检查报告">
            <div class="archive-toolbar">
              <el-date-picker v-model="reportRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width:240px"/>
              <el-select v-model="reportType" clearable placeholder="全部类型" style="width:140px" @change="searchReports">
                <el-option v-for="item in typeOptions" :key="item[0]" :label="item[1]" :value="item[0]"/>
              </el-select>
              <el-select v-if="isDoctor" v-model="reportStatus" placeholder="全部状态" style="width:150px" @change="searchReports">
                <el-option v-for="item in reportStatusOptions" :key="item[0]" :label="item[1]" :value="item[0]"/>
              </el-select>
              <el-input v-model="reportKeyword" clearable placeholder="项目 / 结论 / 单号" style="width:190px" @keyup.enter="searchReports"/>
              <el-button type="primary" plain @click="searchReports">查询</el-button>
              <el-button link @click="resetReports">重置</el-button>
              <span class="workflow-hint">共 {{reportTotal}} 份报告</span>
            </div>
            <ReportTimeline :orders="reports" :loading="reportLoading" :error="reportError" @open="openReport" @retry="loadReports(reportPage)"/>
            <div class="pagination"><span>共 {{reportTotal}} 份</span><el-pagination v-model:current-page="reportPage" layout="prev,pager,next" :total="reportTotal" :page-size="10" @current-change="loadReports"/></div>
          </section>
        </template>
        <div v-else class="archive-placeholder">
          <el-empty description="从左侧选择一位患者，查看其历史病历与检查报告">
            <p class="archive-empty-hint">支持姓名、患者号或手机号搜索；仅显示与您有预约关系的患者。</p>
          </el-empty>
        </div>
      </div>
    </div>

    <RecordReader v-model="recordOpen" :record="currentRecord" @open-report="openReportByNo"/>
    <ReportReader v-model="reportOpen" :order="currentReport" :index="reportIndex" :total="reports.length" @prev="stepReport(-1)" @next="stepReport(1)"/>
  </section>
</template>
