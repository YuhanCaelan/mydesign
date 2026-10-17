<script setup lang="ts">
import{computed}from'vue'
import ListError from'../common/ListError.vue'
import{statusInfo}from'../../utils/status'
import type{MedicalRecord}from'../../types/medical'

const props=defineProps<{records:MedicalRecord[];loading:boolean;error:string}>()
const emit=defineEmits<{(event:'open',record:MedicalRecord):void;(event:'retry'):void}>()

const groups=computed(()=>{
  const map=new Map<string,MedicalRecord[]>()
  for(const record of props.records){
    const key=(record.visit_at||record.updated_at||'').slice(0,7)||'未知'
    map.set(key,[...(map.get(key)||[]),record])
  }
  return[...map.entries()].map(([key,items])=>({key,label:monthLabel(key),items}))
})
function monthLabel(key:string){
  if(!/^\d{4}-\d{2}$/.test(key))return'时间未记录'
  const[year,month]=key.split('-')
  return`${year} 年 ${Number(month)} 月`
}
function dateParts(value?:string){
  const date=(value||'').slice(0,10)
  return{day:date.slice(8,10)||'--',month:date.slice(5,7)||'--'}
}
function open(record:MedicalRecord){emit('open',record)}
</script>

<template>
  <ListError v-if="error" :message="error" @retry="emit('retry')"/>
  <div v-else-if="loading" class="archive-skeleton-list" aria-hidden="true">
    <article v-for="index in 3" :key="index" class="archive-skeleton-card">
      <span class="skeleton-block skeleton-date"/>
      <div class="archive-skeleton-body">
        <span class="skeleton-block skeleton-title"/>
        <span class="skeleton-block skeleton-line"/>
        <span class="skeleton-block skeleton-line short"/>
      </div>
    </article>
  </div>
  <div v-else-if="groups.length" class="archive-timeline">
    <section v-for="group in groups" :key="group.key" class="archive-month">
      <header class="archive-month-head">
        <h3>{{group.label}}</h3>
        <span>{{group.items.length}} 份病历</span>
      </header>
      <article
        v-for="record in group.items"
        :key="record.id"
        class="record-card"
        role="button"
        tabindex="0"
        :aria-label="`查看 ${record.visit_at} ${record.diagnosis||'未填写诊断'} 的病历`"
        @click="open(record)"
        @keydown.enter="open(record)"
        @keydown.space.prevent="open(record)">
        <div class="record-card-date" aria-hidden="true">
          <b>{{dateParts(record.visit_at).day}}</b>
          <span>{{dateParts(record.visit_at).month}} 月</span>
        </div>
        <div class="record-card-body">
          <header class="record-card-head">
            <h3>{{record.diagnosis||'未填写诊断'}}</h3>
            <el-tag :type="statusInfo('record',record.status).tone" effect="plain">{{statusInfo('record',record.status).label}}</el-tag>
          </header>
          <p class="record-card-sub">{{record.record_no}} · {{record.department_name||'科室未记录'}} · {{record.doctor_name}}</p>
          <p class="record-card-chief">{{record.chief_complaint||'未填写主诉'}}</p>
          <div class="record-card-chips">
            <span v-if="record.examinations?.length">检查 {{record.examinations.length}}</span>
            <span v-if="record.prescription_count">处方 {{record.prescription_count}}</span>
            <span v-if="record.admission_count">住院 {{record.admission_count}}</span>
            <span v-if="record.corrections?.length">更正 {{record.corrections.length}}</span>
          </div>
        </div>
        <span class="record-card-open" aria-hidden="true">查看病历 →</span>
      </article>
    </section>
  </div>
  <el-empty v-else description="暂无历史病历">
    <p class="archive-empty-hint">病历在医师确认后才会出现在这里；可调整筛选条件后重试。</p>
  </el-empty>
</template>
