<script setup lang="ts">
import{onMounted,ref}from'vue'
import{useRoute}from'vue-router'
import{getSharedReport}from'../../services/clinical'
import type{SharedReport}from'../../types/medical'

const route=useRoute(),data=ref<SharedReport|null>(null),error=ref(''),loading=ref(false)
function isImage(type:string){return['jpg','jpeg','png','webp'].includes(type.toLowerCase())}
function time(value?:string|null){return value?.replace('T',' ').slice(0,16)||'—'}
onMounted(async()=>{
  loading.value=true
  try{data.value=await getSharedReport(String(route.params.token))}
  catch(e:any){error.value=e.response?.data?.detail||'分享链接不存在或已失效'}
  finally{loading.value=false}
})
</script>

<template>
  <main v-loading="loading" class="shared-report-page">
    <div v-if="data" class="shared-report-card">
      <header class="shared-report-head"><div><p class="eyebrow">SHARED EXAMINATION REPORT</p><h1>{{data.order.item_name}}</h1><p>{{data.order.order_no}} · {{data.order.type_display}} · {{data.order.department_name||'—'}}</p></div><span class="shared-badge">扫码查看</span></header>
      <dl class="shared-meta"><div><dt>患者</dt><dd>{{data.order.patient_name}}（{{data.order.patient_no}}）</dd></div><div><dt>医师</dt><dd>{{data.order.doctor_name}}</dd></div><div><dt>发布时间</dt><dd>{{time(data.report.published_at)}}</dd></div><div><dt>链接有效期</dt><dd>{{time(data.expires_at)}}</dd></div></dl>
      <section><h2>检查所见</h2><p>{{data.report.findings}}</p></section>
      <section><h2>检查结论</h2><p class="shared-conclusion">{{data.report.conclusion}}</p></section>
      <section v-if="data.files.length"><h2>检查附件</h2><div class="shared-files"><a v-for="file in data.files" :key="file.id" :href="file.download_url" target="_blank" rel="noopener" class="shared-file"><img v-if="isImage(file.file_type)" :src="file.download_url" :alt="file.original_name"><span v-else class="shared-file-type">{{file.file_type.toUpperCase()}}</span><b>{{file.original_name}}</b><small>{{(file.size/1024).toFixed(1)}} KB</small></a></div></section>
      <footer class="shared-foot">{{data.notice}}</footer>
    </div>
    <el-empty v-else-if="error" :description="error"><el-button @click="$router.push('/')">返回首页</el-button></el-empty>
  </main>
</template>
