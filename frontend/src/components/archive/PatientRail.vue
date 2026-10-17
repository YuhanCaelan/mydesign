<script setup lang="ts">
import{ArrowRight,Search}from'@element-plus/icons-vue'
import type{PatientSummary}from'../../types/medical'

const props=defineProps<{items:PatientSummary[];selected:number|null;keyword:string;loading:boolean}>()
const emit=defineEmits<{(event:'update:keyword',value:string):void;(event:'select',patient:PatientSummary):void;(event:'search'):void}>()

function age(birth?:string|null){
  if(!birth)return''
  const born=new Date(birth)
  if(Number.isNaN(born.getTime()))return''
  const now=new Date()
  let years=now.getFullYear()-born.getFullYear()
  if(now.getMonth()<born.getMonth()||(now.getMonth()===born.getMonth()&&now.getDate()<born.getDate()))years-=1
  return years>=0?`${years} 岁`:''
}
function meta(patient:PatientSummary){
  return[patient.patient_no,patient.gender_display,age(patient.birth_date)].filter(Boolean).join(' · ')
}
</script>

<template>
  <aside class="patient-rail" aria-label="患者选择">
    <header class="patient-rail-head">
      <div>
        <h2>患者</h2>
        <p>仅显示与您有预约关系的患者</p>
      </div>
      <span class="patient-rail-count">{{items.length}}</span>
    </header>
    <el-input
      :model-value="keyword"
      clearable
      placeholder="搜索姓名 / 患者号 / 手机"
      aria-label="搜索患者"
      @update:model-value="emit('update:keyword',$event)"
      @keyup.enter="emit('search')"
      @clear="emit('search')">
      <template #prefix><el-icon><Search/></el-icon></template>
    </el-input>
    <div v-loading="loading" class="patient-rail-list">
      <button
        v-for="patient in items"
        :key="patient.id"
        type="button"
        class="patient-rail-item"
        :class="{active:patient.id===selected}"
        :aria-pressed="patient.id===selected"
        @click="emit('select',patient)">
        <span class="patient-rail-avatar" aria-hidden="true">{{patient.full_name?.slice(0,1)||'患'}}</span>
        <span class="patient-rail-copy">
          <b>{{patient.full_name}}</b>
          <small>{{meta(patient)||'未填写基础信息'}}</small>
        </span>
        <el-icon v-if="patient.id===selected" class="patient-rail-arrow"><ArrowRight/></el-icon>
      </button>
      <div v-if="!loading&&!items.length" class="patient-rail-empty">
        <b>未找到患者</b>
        <p>可尝试姓名、患者号或手机号</p>
      </div>
    </div>
  </aside>
</template>
