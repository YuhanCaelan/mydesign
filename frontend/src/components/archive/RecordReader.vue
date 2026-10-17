<script setup lang="ts">
import{computed}from'vue'
import{ElMessage}from'element-plus'
import{Download}from'@element-plus/icons-vue'
import{downloadMedicalFile}from'../../services/examinations'
import{statusInfo}from'../../utils/status'
import type{MedicalRecord}from'../../types/medical'

const props=defineProps<{modelValue:boolean;record:MedicalRecord|null}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'open-report',orderNo:string):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})

function dateText(value?:string|null){return(value||'').replace('T',' ').slice(0,16)||'—'}
async function download(id:number,name:string){
  try{await downloadMedicalFile(id,name)}
  catch{ElMessage.error('附件下载失败或无权访问')}
}
</script>

<template>
  <el-drawer v-model="visible" title="病历详情" size="min(720px,96vw)" class="record-reader" destroy-on-close>
    <div v-if="record" class="record-paper">
      <header class="record-paper-head">
        <div>
          <p class="record-paper-eyebrow">MEDICAL RECORD</p>
          <h2>{{record.diagnosis||'未填写诊断'}}</h2>
          <p class="record-paper-sub">{{record.record_no}} · {{record.visit_at}} · {{record.department_name||'科室未记录'}}</p>
        </div>
        <el-tag :type="statusInfo('record',record.status).tone" effect="plain">{{statusInfo('record',record.status).label}}</el-tag>
      </header>

      <dl class="record-paper-meta">
        <div><dt>患者</dt><dd>{{record.patient_name||'—'}}</dd></div>
        <div><dt>医师</dt><dd>{{record.doctor_name||'—'}}<small v-if="record.doctor_title">{{record.doctor_title}}</small></dd></div>
        <div><dt>就诊日期</dt><dd>{{record.visit_at||'—'}}</dd></div>
        <div><dt>确认时间</dt><dd>{{dateText(record.confirmed_at)}}</dd></div>
      </dl>

      <section class="record-paper-section">
        <h3>主诉</h3>
        <p>{{record.chief_complaint||'—'}}</p>
      </section>
      <section class="record-paper-section">
        <h3>现病史</h3>
        <p>{{record.present_illness||'—'}}</p>
      </section>
      <section class="record-paper-section">
        <h3>既往史</h3>
        <p>{{record.past_history||'—'}}</p>
      </section>
      <section class="record-paper-section">
        <h3>体格 / 辅助检查</h3>
        <p>{{record.examination||'—'}}</p>
      </section>
      <section class="record-paper-section">
        <h3>诊断</h3>
        <p class="record-paper-diagnosis">{{record.diagnosis||'—'}}</p>
      </section>
      <section class="record-paper-section">
        <h3>处理意见</h3>
        <p>{{record.treatment||'—'}}</p>
      </section>

      <section v-if="record.examinations?.length" class="record-paper-section">
        <h3>关联检查 <span>{{record.examinations.length}} 项</span></h3>
        <article v-for="exam in record.examinations" :key="exam.id" class="record-exam">
          <header>
            <b>{{exam.item_name||'检查项目'}}</b>
            <el-tag size="small" :type="statusInfo('examination',exam.status).tone" effect="plain">{{statusInfo('examination',exam.status).label}}</el-tag>
          </header>
          <p v-if="exam.report">结论：{{exam.report.conclusion}}</p>
          <p v-else class="muted">报告尚未录入或发布。</p>
          <div class="record-exam-actions">
            <button v-for="file in exam.files" :key="file.id" type="button" class="report-file-chip" @click="download(file.id,file.original_name)">
              <el-icon><Download/></el-icon>{{file.original_name}}
            </button>
            <el-button v-if="exam.report" link type="primary" @click="emit('open-report',exam.order_no)">查看检查报告 →</el-button>
          </div>
        </article>
      </section>

      <section v-if="record.corrections?.length" class="record-paper-section">
        <h3>更正记录 <span>{{record.corrections.length}} 条</span></h3>
        <article v-for="item in record.corrections" :key="item.id" class="record-correction">
          <b>{{item.author_name}} · {{dateText(item.created_at)}}</b>
          <p>{{item.content}}</p>
        </article>
      </section>
    </div>
    <el-empty v-else description="未选择病历"/>
  </el-drawer>
</template>
