<script setup lang="ts">
import{computed,reactive,ref,watch}from'vue'
import type{RecordTemplate}from'../../types/medical'

const props=defineProps<{modelValue:boolean;templates:RecordTemplate[]}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'apply',payload:{diagnosis:string;chief_complaint:string;present_illness:string;past_history:string;examination:string;treatment:string}):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const selectedId=ref<number|null>(null),values=reactive<Record<string,string>>({})
const selected=computed(()=>props.templates.find(item=>item.id===selectedId.value)||null)
const variableKeys=computed(()=>Object.keys(selected.value?.variables||{}))
function choose(id:number){
  selectedId.value=id
  for(const key of Object.keys(values))delete values[key]
  const template=props.templates.find(item=>item.id===id)
  for(const[key,options]of Object.entries(template?.variables||{}))values[key]=options[0]||''
}
function fill(text?:string){
  return(text||'').replace(/\{\{(\w+)\}\}/g,(_match,key)=>values[key]||`【${key}】`)
}
const preview=computed(()=>selected.value?{chief:fill(selected.value.chief_complaint),present:fill(selected.value.present_illness),exam:fill(selected.value.examination),treatment:fill(selected.value.treatment)}:null)
function apply(){
  if(!selected.value||!preview.value)return
  emit('apply',{diagnosis:selected.value.diagnosis,chief_complaint:preview.value.chief,present_illness:preview.value.present,past_history:selected.value.past_history,examination:preview.value.exam,treatment:preview.value.treatment})
  visible.value=false
}
watch(()=>props.modelValue,value=>{if(value&&props.templates.length&&!selectedId.value)choose(props.templates[0].id)})
</script>

<template>
  <el-drawer v-model="visible" title="套用病历模板" size="min(620px,96vw)" destroy-on-close>
    <p class="template-hint">选择疾病模板，只填写左右、轻重、病程等变量；应用后仍可自由修改。</p>
    <el-select :model-value="selectedId" filterable style="width:100%" placeholder="选择疾病模板" @update:model-value="choose(Number($event))">
      <el-option v-for="template in templates" :key="template.id" :value="template.id" :label="`${template.name} · ${template.department_name||'通用'}`"/>
    </el-select>
    <div v-if="selected" class="template-variables">
      <div v-for="key in variableKeys" :key="key" class="template-variable">
        <label>{{key==='side'?'部位/侧别':key==='severity'?'程度':key==='duration'?'病程':'变量'}}</label>
        <el-radio-group v-model="values[key]" size="small">
          <el-radio-button v-for="option in selected.variables[key]" :key="option" :value="option">{{option}}</el-radio-button>
        </el-radio-group>
      </div>
    </div>
    <div v-if="preview" class="template-preview">
      <h3>{{selected?.name}} · {{selected?.diagnosis}}</h3>
      <p><b>主诉</b>{{preview.chief}}</p>
      <p><b>现病史</b>{{preview.present}}</p>
      <p><b>查体</b>{{preview.exam}}</p>
      <p><b>处理</b>{{preview.treatment}}</p>
    </div>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :disabled="!selected" @click="apply">应用到本次病历</el-button></template>
  </el-drawer>
</template>
