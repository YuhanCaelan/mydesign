<script setup lang="ts">
import{computed,reactive,ref,watch}from'vue'
import{ElMessage}from'element-plus'
import{createProcedure,getProcedureItems}from'../../services/clinical'
import type{ProcedureItem}from'../../types/medical'

const props=defineProps<{modelValue:boolean;recordId:number;patientName?:string}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'saved'):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const items=ref<ProcedureItem[]>([]),loading=ref(false),saving=ref(false)
const form=reactive({item_id:0,clinical_note:''})
const selected=computed(()=>items.value.find(item=>item.id===form.item_id))
async function load(){loading.value=true;try{items.value=(await getProcedureItems({active:true,page_size:200})).results}catch{ElMessage.error('处置项目加载失败')}finally{loading.value=false}}
async function submit(){
  if(!props.recordId){ElMessage.warning('请先保存本次病历草稿');return}
  if(!form.item_id){ElMessage.warning('请选择处置项目');return}
  saving.value=true
  try{await createProcedure({record_id:props.recordId,item_id:form.item_id,clinical_note:form.clinical_note});ElMessage.success('处置已发送，费用已生成');visible.value=false;emit('saved')}
  catch(error:any){ElMessage.error(error.response?.data?.detail||JSON.stringify(error.response?.data?.errors||'处置发送失败'))}
  finally{saving.value=false}
}
watch(()=>props.modelValue,value=>{if(value){form.item_id=0;form.clinical_note='';load()}})
</script>

<template>
  <el-dialog v-model="visible" title="开具处置" width="min(560px,96vw)" destroy-on-close>
    <p class="clinic-dialog-sub">患者：{{patientName||'当前就诊患者'}} · 处置执行科室确认缴费后执行</p>
    <el-form label-position="top" v-loading="loading">
      <el-form-item label="处置项目" required>
        <el-select v-model="form.item_id" filterable style="width:100%" placeholder="选择处置项目">
          <el-option v-for="item in items" :key="item.id" :value="item.id" :label="`${item.name} · ${item.category_display} · ¥${item.price}`"/>
        </el-select>
        <small v-if="selected">{{selected.description||'无项目说明'}}；执行科室：{{selected.execution_department_name||'待分配'}}</small>
      </el-form-item>
      <el-form-item label="处置说明"><el-input v-model="form.clinical_note" type="textarea" :rows="3" placeholder="如：左踝打石膏，观察末梢循环"/></el-form-item>
    </el-form>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">发送处置</el-button></template>
  </el-dialog>
</template>
