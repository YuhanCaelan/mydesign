<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import ListError from'../../components/common/ListError.vue'
import StatusLegend from'../../components/common/StatusLegend.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import TaskCard from'../../components/common/TaskCard.vue'
import{useListState}from'../../composables/useListState'
import{statusInfo}from'../../utils/status'
import type{ViewMode}from'../../utils/view'
import{getRecords}from'../../services/records'
import{getActiveAdmissions,getExaminationItems}from'../../services/operations'
import{createExamination,downloadMedicalFile,getExaminations,publishReport,saveReport,startExamination,uploadMedicalFile}from'../../services/examinations'
import type{ExaminationItem,ExaminationOrder,InpatientAdmission,MedicalRecord}from'../../types/medical'

const auth=useAuthStore(),role=computed(()=>auth.user!.role)
const state=useListState(`examinations-${role.value}`,{page:1,search:'',status:'',view:'cards' as ViewMode})
const statusOrder=['requested','in_progress','completed','published','cancelled']
const groups=computed(()=>statusOrder.map(key=>({key,info:statusInfo('examination',key),items:rows.value.filter(item=>item.status===key)})).filter(group=>group.items.length))
const rows=ref<ExaminationOrder[]>([]),total=ref(0),loading=ref(false),error=ref(''),createOpen=ref(false),reportOpen=ref(false),detailOpen=ref(false),saving=ref(false),records=ref<MedicalRecord[]>([]),items=ref<ExaminationItem[]>([]),current=ref<ExaminationOrder|null>(null),selectedFile=ref<File|null>(null)
const form=reactive({record_id:0,item_id:0,type:'lab',clinical_question:'',admission_id:null as number|null}),admissions=ref<InpatientAdmission[]>([]),report=reactive({findings:'',conclusion:''})
const types=[['blood','血液检查'],['lab','常规检验'],['xray','X-Ray'],['ct','CT'],['mri','MRI'],['other','其他检查']]
async function load(){loading.value=true;error.value='';try{const data=await getExaminations({page:state.page,search:state.search||undefined,status:state.status||undefined});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'检查记录加载失败'}finally{loading.value=false}}
function searchOrders(){state.page=1;load()}
async function loadAdmissions(){admissions.value=[];form.admission_id=null;const record=records.value.find(item=>item.id===form.record_id);if(!record)return;try{admissions.value=await getActiveAdmissions(record.patient_id??undefined)}catch{admissions.value=[]}}
async function openCreate(){Object.assign(form,{record_id:0,item_id:0,type:'lab',clinical_question:'',admission_id:null});admissions.value=[];createOpen.value=true;try{const[recordResult,itemResult]=await Promise.all([getRecords({status:'confirmed'}),getExaminationItems({active:true})]);records.value=recordResult.results;items.value=itemResult.results}catch{records.value=[];items.value=[];ElMessage.error('病历或检查目录加载失败')}}
function chooseItem(id:number){const item=items.value.find(entry=>entry.id===id);if(!item)return;const name=item.name.toLowerCase();form.type=item.category==='lab'?(name.includes('血')?'blood':'lab'):item.category==='imaging'?(name.includes('mri')?'mri':name.includes('ct')?'ct':name.includes('x-ray')||name.includes('x光')?'xray':'other'):'other'}
async function submit(){if(!form.record_id||!form.item_id||!form.clinical_question.trim()){ElMessage.warning('请选择病历、检查项目并填写检查目的');return}saving.value=true;try{await createExamination(form);ElMessage.success('检查申请已创建并生成费用账单');createOpen.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||JSON.stringify(e.response?.data?.errors||'创建失败'))}finally{saving.value=false}}
async function start(row:ExaminationOrder){try{await startExamination(row.id);ElMessage.success('检查已开始处理');await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'无法开始检查')}}
function openReport(row:ExaminationOrder){current.value=row;report.findings=row.report?.findings||'';report.conclusion=row.report?.conclusion||'';selectedFile.value=null;reportOpen.value=true}
function chooseFile(event:Event){const input=event.target as HTMLInputElement;selectedFile.value=input.files?.[0]||null}
async function submitReport(){if(!current.value||!report.findings.trim()||!report.conclusion.trim()){ElMessage.warning('检查所见和结论不能为空');return}saving.value=true;try{await saveReport(current.value.id,report);if(selectedFile.value)await uploadMedicalFile(current.value.id,selectedFile.value);ElMessage.success('检查报告已保存');reportOpen.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'报告保存失败')}finally{saving.value=false}}
async function publish(row:ExaminationOrder){try{await ElMessageBox.confirm('发布后患者将可以查看报告和附件。','发布检查报告',{type:'warning'});await publishReport(row.id);ElMessage.success('报告已发布');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'发布失败')}}
async function download(id:number,name:string){try{await downloadMedicalFile(id,name)}catch{ElMessage.error('附件下载失败或无权访问')}}
function view(row:ExaminationOrder){current.value=row;detailOpen.value=true}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">MEDICAL EXAMINATION</p><h1>{{role==='doctor'?'医学检查':role==='patient'?'检查报告':'检查管理'}}</h1><p>{{role==='doctor'?'创建检查申请，录入检查结果并向患者发布报告':role==='patient'?'查看已经发布的个人检查结果和附件':'审核、录入并发布检查报告'}}</p></div><el-button v-if="role==='doctor'" type="primary" @click="openCreate">＋ 申请检查</el-button></div>
    <el-card class="table-card">
      <div class="table-tools"><el-input v-model="state.search" clearable placeholder="搜索申请单、患者或检查目的" @keyup.enter="searchOrders"/><el-select v-model="state.status" clearable placeholder="全部状态" @change="searchOrders"><el-option label="已申请" value="requested"/><el-option label="检查中" value="in_progress"/><el-option label="报告待发布" value="completed"/><el-option label="已发布" value="published"/><el-option label="已取消" value="cancelled"/></el-select><el-button @click="searchOrders">查询</el-button><span class="table-count">共 {{total}} 条</span><ViewSwitch v-model="state.view"/></div>
      <div class="legend-row"><StatusLegend domain="examination" title="检查状态"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="task-groups">
        <section v-for="group in groups" :key="group.key" class="task-group">
          <header class="task-group-head"><h2>{{group.info.label}}</h2><el-tag :type="group.info.tone" effect="plain">{{group.items.length}} 项</el-tag></header>
          <div class="task-card-grid">
            <TaskCard v-for="row in group.items" :key="row.id" :time="row.created_at?.replace('T',' ').slice(0,16)" :title="row.item_name_snapshot||'检查申请'" :subtitle="`${row.order_no} · ${role==='patient'?row.doctor_name:row.patient_name}`" :accent="group.info.tone" :highlight="row.status==='completed'" :meta="[{label:'检查类型',value:row.type_display},{label:'费用',value:row.price_snapshot?`¥${row.price_snapshot}`:'无目录费用'},{label:'检查目的',value:row.clinical_question}]">
              <template #status><el-tag :type="group.info.tone">{{group.info.label}}</el-tag></template>
              <template #actions><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="role==='admin'||role==='doctor'"><el-button v-if="row.status==='requested'" link @click="start(row)">开始检查</el-button><el-button v-if="row.status==='requested'||row.status==='in_progress'||row.status==='completed'" link @click="openReport(row)">{{row.report?'编辑报告':'录入报告'}}</el-button><el-button v-if="row.status==='completed'" link type="success" @click="publish(row)">发布</el-button></template></template>
            </TaskCard>
          </div>
        </section>
        <el-empty v-if="!rows.length&&!loading" description="暂无检查记录"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows" empty-text="暂无检查记录" class="desktop-table">
          <el-table-column type="expand"><template #default="{row}"><div class="record-detail exam-expand"><div><span>检查目的与临床问题</span><p>{{row.clinical_question}}</p></div><div><span>检查类型与费用</span><b>{{row.type_display}} · {{row.price_snapshot?`¥${row.price_snapshot}`:'无目录费用'}}</b></div><div><span>费用归属</span><b>{{row.admission_no?`住院 ${row.admission_no}`:'门诊费用'}}</b></div></div></template></el-table-column>
          <el-table-column prop="order_no" label="申请单号" min-width="145"/>
          <el-table-column v-if="role!=='patient'" prop="patient_name" label="患者" min-width="105"/>
          <el-table-column v-else prop="doctor_name" label="医师" min-width="105"/>
          <el-table-column prop="item_name_snapshot" label="检查项目" min-width="150"><template #default="{row}">{{row.item_name_snapshot||'未指定目录项目'}}</template></el-table-column>
          <el-table-column label="申请时间" min-width="150"><template #default="{row}">{{row.created_at?.replace('T',' ').slice(0,16)}}</template></el-table-column>
          <el-table-column label="状态" width="115"><template #default="{row}"><el-tag :type="statusInfo('examination',row.status).tone">{{statusInfo('examination',row.status).label}}</el-tag></template></el-table-column>
          <el-table-column label="操作" min-width="250" fixed="right"><template #default="{row}"><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="role==='admin'||role==='doctor'"><el-button v-if="row.status==='requested'" link @click="start(row)">开始检查</el-button><el-button v-if="row.status==='requested'||row.status==='in_progress'||row.status==='completed'" link @click="openReport(row)">{{row.report?'编辑报告':'录入报告'}}</el-button><el-button v-if="row.status==='completed'" link type="success" @click="publish(row)">发布</el-button></template></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in rows" :key="row.id" class="mobile-info-card">
            <header><h3>{{row.item_name_snapshot||'检查申请'}}</h3><el-tag :type="statusInfo('examination',row.status).tone">{{statusInfo('examination',row.status).label}}</el-tag></header>
            <p class="mobile-sub">{{row.order_no}} · {{role==='patient'?row.doctor_name:row.patient_name}}</p>
            <div class="mobile-line"><span>申请时间</span><b>{{row.created_at?.replace('T',' ').slice(0,16)}}</b></div>
            <div class="mobile-line"><span>检查目的</span><b>{{row.clinical_question}}</b></div>
            <div class="actions"><el-button link type="primary" @click="view(row)">查看</el-button><template v-if="role==='admin'||role==='doctor'"><el-button v-if="row.status==='requested'" link @click="start(row)">开始检查</el-button><el-button v-if="row.status==='requested'||row.status==='in_progress'||row.status==='completed'" link @click="openReport(row)">{{row.report?'编辑报告':'录入报告'}}</el-button><el-button v-if="row.status==='completed'" link type="success" @click="publish(row)">发布</el-button></template></div>
          </article>
          <div v-if="!rows.length&&!loading" class="mobile-empty">暂无检查记录</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
    <el-dialog v-model="createOpen" title="创建检查申请" width="min(620px,94vw)"><el-form label-position="top"><el-form-item label="关联已确认病历" required><el-select v-model="form.record_id" filterable style="width:100%" @change="loadAdmissions"><el-option v-for="item in records" :key="item.id" :label="`${item.patient_name} · ${item.record_no} · ${item.diagnosis}`" :value="item.id"/></el-select></el-form-item><el-form-item label="归集到住院（可选）"><el-select v-model="form.admission_id" clearable filterable style="width:100%" placeholder="选择在院记录，费用将计入该次住院清单"><el-option v-for="item in admissions" :key="item.id" :label="`${item.admission_no} · ${item.ward}${item.bed_no} · ${item.department_name}`" :value="item.id"/></el-select><small>仅显示所选病历患者的在院记录；患者一致性由后端再次校验。</small></el-form-item><el-form-item label="检查项目（自动计费）" required><el-select v-model="form.item_id" filterable style="width:100%" @change="chooseItem"><el-option v-for="item in items" :key="item.id" :label="`${item.name} · ¥${item.price}`" :value="item.id"/></el-select><small v-if="form.item_id">费用 ¥{{items.find(item=>item.id===form.item_id)?.price}}，创建申请后自动生成待缴费账单。</small><small v-else-if="!items.length">当前没有启用的检查项目，请联系管理员维护项目目录。</small></el-form-item><el-form-item label="检查类型" required><el-select v-model="form.type" style="width:100%"><el-option v-for="item in types" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select></el-form-item><el-form-item label="检查目的与临床问题" required><el-input v-model="form.clinical_question" type="textarea" :rows="4" maxlength="500" show-word-limit/></el-form-item></el-form><template #footer><el-button @click="createOpen=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!items.length" @click="submit">提交申请</el-button></template></el-dialog>
    <el-dialog v-model="reportOpen" title="录入检查报告" width="min(680px,94vw)"><el-form label-position="top"><el-form-item label="检查所见" required><el-input v-model="report.findings" type="textarea" :rows="5"/></el-form-item><el-form-item label="检查结论" required><el-input v-model="report.conclusion" type="textarea" :rows="4"/></el-form-item><el-form-item label="报告或影像附件"><input class="file-input" type="file" accept=".jpg,.jpeg,.png,.pdf,.dcm,.nii,.gz" @change="chooseFile"><small>支持 JPG、PNG、PDF、DICOM、NIfTI，单个文件不超过 10MB</small></el-form-item></el-form><template #footer><el-button @click="reportOpen=false">取消</el-button><el-button type="primary" :loading="saving" @click="submitReport">保存报告</el-button></template></el-dialog>
    <el-drawer v-model="detailOpen" title="检查详情" size="min(620px,94vw)"><div v-if="current" class="record-detail"><div><span>申请单号</span><b>{{current.order_no}}</b></div><div><span>检查项目</span><b>{{current.item_name_snapshot||'未指定目录项目'}} · {{current.price_snapshot?`¥${current.price_snapshot}`:'无目录费用'}}</b></div><div><span>检查类型</span><b>{{current.type_display}}</b></div><div><span>费用归属</span><b>{{current.admission_no?`住院 ${current.admission_no}`:'门诊费用'}}</b></div><div><span>检查目的</span><p>{{current.clinical_question}}</p></div><template v-if="current.report"><div><span>检查所见</span><p>{{current.report.findings}}</p></div><div><span>检查结论</span><p>{{current.report.conclusion}}</p></div></template><section v-if="current.files?.length"><h3>检查附件</h3><button v-for="file in current.files" :key="file.id" class="file-link" @click="download(file.id,file.original_name)">{{file.original_name}} <span>{{(file.size/1024).toFixed(1)}} KB</span></button></section><el-empty v-if="!current.report" description="检查报告尚未录入或发布"/></div></el-drawer>
  </section>
</template>
