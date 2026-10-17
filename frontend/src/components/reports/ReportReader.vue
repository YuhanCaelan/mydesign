<script setup lang="ts">
import{computed,onBeforeUnmount,onMounted}from'vue'
import{ElMessage}from'element-plus'
import{ArrowLeft,ArrowRight,Close,Download,Printer}from'@element-plus/icons-vue'
import{downloadMedicalFile}from'../../services/examinations'
import{statusInfo}from'../../utils/status'
import type{ExaminationOrder}from'../../types/medical'

const props=defineProps<{modelValue:boolean;order:ExaminationOrder|null;index?:number;total?:number}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'prev'):void;(event:'next'):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const date=computed(()=>props.order?.published_at||props.order?.completed_at||props.order?.created_at||'')
const canPrev=computed(()=>Number(props.index||0)>1)
const canNext=computed(()=>Number(props.index||0)>0&&Number(props.index||0)<Number(props.total||0))
const escapeMap:Record<string,string>={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}
const abnormalPattern=/(偏高|偏低|升高|降低|阳性|增大|结节|钙化|积液|↑|↓)/g

function escapeHtml(value:string){return value.replace(/[&<>"']/g,ch=>escapeMap[ch]||ch)}
function highlight(value?:string|null){
  if(!value)return'—'
  return escapeHtml(value).replace(abnormalPattern,'<mark class="report-abnormal">$1</mark>')
}
function dateText(value?:string|null){return(value||'').replace('T',' ').slice(0,16)||'—'}
function fileBadge(type:string){
  const labels:Record<string,string>={pdf:'PDF',jpg:'影像',jpeg:'影像',png:'影像',dcm:'DICOM',nii:'NIfTI',gz:'压缩包'}
  return labels[type]||type.toUpperCase()
}
async function download(id:number,name:string){
  try{await downloadMedicalFile(id,name)}
  catch{ElMessage.error('附件下载失败或无权访问')}
}
function printReport(){
  document.body.classList.add('printing-report')
  window.setTimeout(()=>window.print(),30)
}
function cleanupPrint(){document.body.classList.remove('printing-report')}
onMounted(()=>window.addEventListener('afterprint',cleanupPrint))
onBeforeUnmount(()=>{window.removeEventListener('afterprint',cleanupPrint);cleanupPrint()})
</script>

<template>
  <el-drawer v-model="visible" size="min(820px,96vw)" class="report-reader" :with-header="false" destroy-on-close>
    <div v-if="order" class="report-reader-inner">
      <div class="report-reader-toolbar">
        <div>
          <span class="report-reader-kicker">EXAMINATION REPORT</span>
          <b>{{order.order_no}}</b>
        </div>
        <div class="report-reader-tools">
          <el-button :icon="ArrowLeft" :disabled="!canPrev" circle aria-label="上一份报告" @click="emit('prev')"/>
          <span class="report-reader-index">{{index||1}} / {{total||1}}</span>
          <el-button :icon="ArrowRight" :disabled="!canNext" circle aria-label="下一份报告" @click="emit('next')"/>
          <el-button :icon="Printer" @click="printReport">打印</el-button>
          <el-button :icon="Close" circle aria-label="关闭报告" @click="visible=false"/>
        </div>
      </div>

      <article class="report-paper">
        <header class="report-paper-head">
          <div class="report-paper-brand">
            <span class="report-paper-logo" aria-hidden="true">慧</span>
            <div><b>慧医云 · 医学检查报告</b><small>SMART MEDICAL EXAMINATION REPORT</small></div>
          </div>
          <el-tag :type="statusInfo('examination',order.status).tone" effect="plain">{{statusInfo('examination',order.status).label}}</el-tag>
        </header>

        <h2 class="report-paper-title">{{order.item_name_snapshot||'检查报告'}}</h2>
        <p class="report-paper-sub">{{order.type_display}} · {{order.department_name||'科室未记录'}}</p>

        <dl class="report-paper-meta">
          <div><dt>患者</dt><dd>{{order.patient_name}}</dd></div>
          <div><dt>患者号</dt><dd>{{order.patient_no||'—'}}</dd></div>
          <div><dt>申请医师</dt><dd>{{order.doctor_name}}</dd></div>
          <div><dt>科室</dt><dd>{{order.department_name||'—'}}</dd></div>
          <div><dt>检查类型</dt><dd>{{order.type_display}}</dd></div>
          <div><dt>发布时间</dt><dd>{{dateText(order.published_at)}}</dd></div>
        </dl>

        <section class="report-paper-section">
          <h3>检查目的</h3>
          <p class="report-paper-text">{{order.clinical_question||'—'}}</p>
        </section>
        <section class="report-paper-section">
          <h3>检查所见</h3>
          <p class="report-paper-text report-paper-findings" v-html="highlight(order.report?.findings)"></p>
        </section>
        <section class="report-paper-section">
          <h3>检查结论</h3>
          <p class="report-paper-conclusion">{{order.report?.conclusion||'报告尚未录入或发布'}}</p>
        </section>

        <section v-if="order.files?.length" class="report-paper-section">
          <h3>检查附件 <span>{{order.files.length}} 个</span></h3>
          <div class="report-file-grid">
            <button v-for="file in order.files" :key="file.id" type="button" class="report-file-card" @click="download(file.id,file.original_name)">
              <span class="report-file-badge">{{fileBadge(file.file_type)}}</span>
              <span class="report-file-copy"><b>{{file.original_name}}</b><small>{{(file.size/1024).toFixed(1)}} KB · 点击下载</small></span>
              <el-icon><Download/></el-icon>
            </button>
          </div>
        </section>

        <footer class="report-paper-foot">
          <span>报告生成时间：{{dateText(date)}}</span>
          <span>高亮仅为阅读提示，不替代临床判断</span>
        </footer>
      </article>

      <div class="report-reader-actions">
        <el-button :disabled="!canPrev" @click="emit('prev')">上一份</el-button>
        <el-button :disabled="!canNext" @click="emit('next')">下一份</el-button>
        <el-button :icon="Printer" type="primary" @click="printReport">打印报告</el-button>
        <el-button @click="visible=false">关闭</el-button>
      </div>
    </div>
    <el-empty v-else description="未选择报告"/>
  </el-drawer>
</template>
