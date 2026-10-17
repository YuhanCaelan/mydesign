<script setup lang="ts">
import{computed}from'vue'
import{Paperclip}from'@element-plus/icons-vue'
import{statusInfo}from'../../utils/status'
import type{ExaminationOrder}from'../../types/medical'

const props=defineProps<{order:ExaminationOrder}>()
const emit=defineEmits<{(event:'open',order:ExaminationOrder):void}>()

const date=computed(()=>props.order.published_at||props.order.completed_at||props.order.created_at)
const status=computed(()=>statusInfo('examination',props.order.status))
const conclusion=computed(()=>props.order.report?.conclusion?.trim()||'')
const fileTypes=computed(()=>{
  const labels:Record<string,string>={pdf:'PDF',jpg:'影像',jpeg:'影像',png:'影像',dcm:'DICOM',nii:'NIfTI',gz:'压缩包'}
  return[...new Set((props.order.files||[]).map(file=>labels[file.file_type]||file.file_type.toUpperCase()))]
})
function open(){emit('open',props.order)}
</script>

<template>
  <article
    class="report-card"
    :data-status="order.status"
    role="button"
    tabindex="0"
    :aria-label="`打开 ${date?.slice(0,10)} ${order.item_name_snapshot||'检查报告'}`"
    @click="open"
    @keydown.enter="open"
    @keydown.space.prevent="open">
    <div class="report-card-date" aria-hidden="true">
      <b>{{(date||'').slice(8,10)||'--'}}</b>
      <span>{{(date||'').slice(5,7)||'--'}} 月</span>
    </div>
    <div class="report-card-body">
      <header class="report-card-head">
        <div>
          <h3>{{order.item_name_snapshot||'检查项目'}}</h3>
          <p>{{order.order_no}} · {{order.department_name||'科室未记录'}} · {{order.doctor_name}}</p>
        </div>
        <el-tag :type="status.tone" effect="plain">{{status.label}}</el-tag>
      </header>
      <p class="report-card-conclusion" :class="{empty:!conclusion}">
        <template v-if="conclusion">{{conclusion}}</template>
        <template v-else>报告尚未录入或发布</template>
      </p>
      <footer class="report-card-foot">
        <span v-if="order.files?.length" class="report-attachments">
          <el-icon><Paperclip/></el-icon>{{order.files.length}} 个附件
          <em v-for="type in fileTypes" :key="type">{{type}}</em>
        </span>
        <span v-else class="muted">无附件</span>
        <span class="report-card-open">{{order.report?'阅读报告 →':'查看详情 →'}}</span>
      </footer>
    </div>
  </article>
</template>
