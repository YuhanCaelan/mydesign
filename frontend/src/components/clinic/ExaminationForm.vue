<script setup lang="ts">
import{computed,reactive,ref,watch}from'vue'
import{ElMessage}from'element-plus'
import{createExamination}from'../../services/examinations'
import{getExaminationCatalog}from'../../services/clinical'
import type{ExaminationItem}from'../../types/medical'

const props=defineProps<{modelValue:boolean;recordId:number;patientName?:string}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'saved'):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const items=ref<ExaminationItem[]>([]),loading=ref(false),saving=ref(false)
const form=reactive({item_id:0,type:'lab',clinical_question:''})
const types=[['blood','血液检查'],['lab','常规检验'],['xray','X-Ray'],['ct','CT'],['mri','MRI'],['other','其他检查']]
const selected=computed(()=>items.value.find(item=>item.id===form.item_id))
async function load(){loading.value=true;try{items.value=(await getExaminationCatalog({active:true,page_size:200})).results}catch{ElMessage.error('检查项目加载失败')}finally{loading.value=false}}
function chooseItem(id:number){const item=items.value.find(entry=>entry.id===id);if(!item)return;const name=item.name.toLowerCase();form.type=item.category==='lab'?(name.includes('血')?'blood':'lab'):item.category==='imaging'?(name.includes('mri')?'mri':name.includes('ct')?'ct':name.includes('x-ray')||name.includes('x光')?'xray':'other'):'other'}
async function submit(){
  if(!props.recordId){ElMessage.warning('请先保存本次病历草稿');return}
  if(!form.item_id||!form.clinical_question.trim()){ElMessage.warning('请选择检查项目并填写检查目的');return}
  saving.value=true
  try{await createExamination({record_id:props.recordId,item_id:form.item_id,type:form.type,clinical_question:form.clinical_question});ElMessage.success('检查已发送，费用已生成');visible.value=false;emit('saved')}
  catch(error:any){ElMessage.error(error.response?.data?.detail||JSON.stringify(error.response?.data?.errors||'检查发送失败'))}
  finally{saving.value=false}
}
watch(()=>props.modelValue,value=>{if(value){form.item_id=0;form.clinical_question='';load()}})
</script>

<template>
  <el-dialog v-model="visible" title="开具检查" width="min(560px,96vw)" destroy-on-close>
    <p class="clinic-dialog-sub">患者：{{patientName||'当前就诊患者'}} · 检查费用在发送后自动生成</p>
    <el-form label-position="top">
      <el-form-item label="检查项目" required>
        <el-select v-model="form.item_id" filterable style="width:100%" placeholder="选择检查项目" @change="chooseItem">
          <el-option v-for="item in items" :key="item.id" :value="item.id" :label="`${item.name} · ¥${item.price}`"/>
        </el-select>
        <small v-if="selected">费用 ¥{{selected.price}}，发送后生成待缴费账单。</small>
      </el-form-item>
      <el-form-item label="检查类型" required><el-select v-model="form.type" style="width:100%"><el-option v-for="item in types" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select></el-form-item>
      <el-form-item label="检查目的 / 临床问题" required><el-input v-model="form.clinical_question" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="如：排除颅内器质性病变"/></el-form-item>
    </el-form>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">发送检查</el-button></template>
  </el-dialog>
</template>
