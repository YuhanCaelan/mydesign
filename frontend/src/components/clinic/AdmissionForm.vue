<script setup lang="ts">
import{computed,reactive,ref,watch}from'vue'
import{ElMessage}from'element-plus'
import{createInpatientRequest,getWardBedsAvailable}from'../../services/clinical'
import type{WardBed}from'../../types/medical'

const props=defineProps<{modelValue:boolean;patientId:number;patientName?:string;doctorId:number;departmentId?:number;departmentName?:string;appointmentId?:number}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'saved'):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const beds=ref<WardBed[]>([]),loading=ref(false),saving=ref(false)
const form=reactive({bed_id:null as number|null,admission_diagnosis:''})
async function load(){if(!props.departmentId)return;loading.value=true;try{beds.value=(await getWardBedsAvailable(props.departmentId)).results}catch{beds.value=[]}finally{loading.value=false}}
async function submit(){
  if(!form.admission_diagnosis.trim()){ElMessage.warning('请填写入院诊断');return}
  saving.value=true
  try{
    await createInpatientRequest({patient_id:props.patientId,doctor_id:props.doctorId,department_id:props.departmentId,appointment_id:props.appointmentId,bed_id:form.bed_id||undefined,admission_diagnosis:form.admission_diagnosis})
    ElMessage.success('住院申请已提交，等待住院处办理')
    visible.value=false;emit('saved')
  }catch(error:any){ElMessage.error(error.response?.data?.detail||JSON.stringify(error.response?.data?.errors||'住院申请提交失败'))}
  finally{saving.value=false}
}
watch(()=>props.modelValue,value=>{if(value){form.bed_id=null;form.admission_diagnosis='';load()}})
</script>

<template>
  <el-dialog v-model="visible" title="申请住院" width="min(560px,96vw)" destroy-on-close>
    <p class="clinic-dialog-sub">患者：{{patientName||'当前患者'}} · {{departmentName||'本科室'}} · 提交后由住院处分配床位并办理入院</p>
    <el-form label-position="top" v-loading="loading">
      <el-form-item label="入院诊断" required><el-input v-model="form.admission_diagnosis" type="textarea" :rows="3" placeholder="如：急性阑尾炎，建议住院治疗"/></el-form-item>
      <el-form-item label="预选床位（可选）">
        <el-select v-model="form.bed_id" clearable filterable style="width:100%" placeholder="可留空，由住院处分配">
          <el-option v-for="bed in beds" :key="bed.id" :value="bed.id" :label="`${bed.ward_name} · ${bed.bed_no} · ¥${bed.daily_rate}/日`"/>
        </el-select>
        <small v-if="!beds.length">本科室暂无可选床位，住院处可稍后分配。</small>
      </el-form-item>
    </el-form>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交住院申请</el-button></template>
  </el-dialog>
</template>
