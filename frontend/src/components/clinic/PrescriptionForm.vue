<script setup lang="ts">
import{computed,ref,watch}from'vue'
import{ElMessage}from'element-plus'
import{Plus,Delete}from'@element-plus/icons-vue'
import{createPrescription}from'../../services/prescriptions'
import{getMedicineCatalog}from'../../services/clinical'
import type{Medicine,PrescriptionItem}from'../../types/medical'

const props=defineProps<{modelValue:boolean;recordId:number;patientName?:string}>()
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'saved'):void}>()
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const medicines=ref<Medicine[]>([]),saving=ref(false),loading=ref(false),notes=ref('')
const lines=ref<PrescriptionItem[]>([{medicine_id:0,dosage:'',frequency:'',duration:'',quantity:1}])
const total=computed(()=>lines.value.reduce((sum,line)=>sum+(Number(medicines.value.find(item=>item.id===line.medicine_id)?.price)||0)*Number(line.quantity||0),0))
const shortages=computed(()=>lines.value.filter(line=>isShort(line)))
function medicineOf(id:number){return medicines.value.find(item=>item.id===id)}
function stockOf(id:number){return medicineOf(id)?.stock??0}
function isShort(line:PrescriptionItem){return Boolean(line.medicine_id)&&Number(line.quantity)>stockOf(line.medicine_id)}
async function load(){loading.value=true;try{medicines.value=(await getMedicineCatalog({active:true,page_size:200})).results}catch{ElMessage.error('药品目录加载失败')}finally{loading.value=false}}
function addLine(){lines.value.push({medicine_id:0,dosage:'',frequency:'',duration:'',quantity:1})}
function removeLine(index:number){if(lines.value.length>1)lines.value.splice(index,1)}
async function submit(){
  if(!props.recordId){ElMessage.warning('请先保存本次病历草稿');return}
  const items=lines.value.filter(line=>line.medicine_id)
  if(!items.length){ElMessage.warning('请至少选择一种药品');return}
  if(items.some(line=>!line.dosage.trim()||!line.frequency.trim()||Number(line.quantity)<1)){ElMessage.warning('请完整填写用法、频次和数量');return}
  saving.value=true
  try{
    await createPrescription({record_id:props.recordId,notes:notes.value,items:items.map(line=>({...line,quantity:Number(line.quantity)}))})
    ElMessage.success('处方已发送，费用已生成，等待患者缴费')
    visible.value=false;emit('saved')
  }catch(error:any){ElMessage.error(error.response?.data?.detail||JSON.stringify(error.response?.data?.errors||'处方发送失败'))}
  finally{saving.value=false}
}
watch(()=>props.modelValue,value=>{if(value)load()})
</script>

<template>
  <el-dialog v-model="visible" title="开具处方" width="min(760px,96vw)" destroy-on-close>
    <div class="clinic-form-head">
      <span>患者：{{patientName||'当前就诊患者'}}</span>
      <span class="clinic-form-total">预计 ¥{{total.toFixed(2)}}</span>
    </div>
    <div v-loading="loading" class="prescription-lines">
      <div v-for="(line,index) in lines" :key="index" class="prescription-line">
        <el-select v-model="line.medicine_id" filterable placeholder="选择药品" class="medicine-select">
          <el-option v-for="medicine in medicines" :key="medicine.id" :value="medicine.id" :label="`${medicine.name} · ${medicine.specification} · ¥${medicine.price}`">
            <div class="medicine-option"><span>{{medicine.name}} <small>{{medicine.specification}}</small></span><span>¥{{medicine.price}} <em :class="{danger:medicine.stock<=0}">库存 {{medicine.stock}}</em></span></div>
          </el-option>
        </el-select>
        <el-input v-model="line.dosage" placeholder="用法，如 0.5g"/>
        <el-input v-model="line.frequency" placeholder="频次，如 每日两次"/>
        <el-input v-model="line.duration" placeholder="疗程，如 3 天"/>
        <el-input-number v-model="line.quantity" :min="1" :max="999" controls-position="right"/>
        <el-button :icon="Delete" circle text :disabled="lines.length===1" @click="removeLine(index)"/>
        <div v-if="line.medicine_id" class="medicine-stock" :class="{danger:isShort(line)}">库存 {{stockOf(line.medicine_id)}}</div>
      </div>
    </div>
    <el-button :icon="Plus" plain @click="addLine">添加药品</el-button>
    <el-alert v-if="shortages.length" type="warning" :closable="false" show-icon class="stock-alert" title="部分药品库存不足，处方仍可发送；药房发药时会再次校验库存。"/>
    <el-form-item label="处方备注" class="notes-field"><el-input v-model="notes" type="textarea" :rows="2" placeholder="如：饭后服用、避免饮酒"/></el-form-item>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">发送处方</el-button></template>
  </el-dialog>
</template>
