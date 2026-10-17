<script setup lang="ts">
import {computed,onMounted,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getExaminationItems,getOperationDepartments,getMedicines,getStockMovements,getWardBeds,saveExaminationItem,saveWardBed} from '../../services/operations'
import {useListState} from '../../composables/useListState'
import ListError from '../../components/common/ListError.vue'
import type {Department,ExaminationItem,Medicine,StockMovement,WardBed} from '../../types/medical'

type Tab='beds'|'exams'|'movements'
const props=defineProps<{view?:Tab}>()
const showTabs=computed(()=>!props.view)
const active=ref<Tab>(props.view||'beds')
const ui=useListState(`clinical-resources-${props.view||'all'}`,{search:'',enabled:'',page:1,movementType:'',medicineId:undefined as number|undefined,dateRange:null as [string,string]|null})
const loading=ref(false),saving=ref(false),dialog=ref(false),error=ref(''),total=ref(0)
const rows=ref<(WardBed|ExaminationItem|StockMovement)[]>([]),departments=ref<Department[]>([]),medicines=ref<Medicine[]>([])
const editing=ref<WardBed|ExaminationItem|null>(null)
const bedForm=reactive({department:0,ward_name:'',bed_no:'',daily_rate:0,is_active:true})
const itemForm=reactive({name:'',category:'lab' as ExaminationItem['category'],price:0,is_active:true,description:''})
const categories=[['lab','检验'],['imaging','影像'],['function','功能检查'],['other','其他']]
const types=[['receipt','入库'],['adjustment','人工调整'],['dispense','处方发药']]
const titles:Record<Tab,{title:string;desc:string;eyebrow:string}>={beds:{title:'床位配置',desc:'维护床位所属科室、病区、床位号、日费和启停状态',eyebrow:'BED CONFIGURATION'},exams:{title:'检查项目',desc:'维护检查项目名称、类别、价格与启用状态',eyebrow:'EXAMINATION CATALOG'},movements:{title:'库存流水',desc:'按药品、流水类型与日期追踪库存变动来源',eyebrow:'STOCK MOVEMENTS'}}
const heading=computed(()=>titles[active.value])

function errorText(e:any,fallback:string){return e.response?.data?.detail||fallback}
async function load(){loading.value=true;error.value='';try{
  const params:Record<string,unknown>={page:ui.page,search:ui.search||undefined}
  if(active.value==='beds'){if(ui.enabled)params.active=ui.enabled==='true';const data=await getWardBeds(params);rows.value=data.results;total.value=data.count}
  else if(active.value==='exams'){if(ui.enabled)params.active=ui.enabled==='true';const data=await getExaminationItems(params);rows.value=data.results;total.value=data.count}
  else{if(ui.movementType)params.movement_type=ui.movementType;if(ui.medicineId)params.medicine=ui.medicineId;if(ui.dateRange){params.date_from=ui.dateRange[0];params.date_to=ui.dateRange[1]}const data=await getStockMovements(params);rows.value=data.results;total.value=data.count}
}catch(e:any){rows.value=[];total.value=0;error.value=errorText(e,'资源数据加载失败')}finally{loading.value=false}}
watch([active,()=>ui.enabled,()=>ui.movementType,()=>ui.medicineId,()=>ui.dateRange],()=>{ui.page=1;load()})
watch(()=>props.view,value=>{if(value){active.value=value;ui.page=1;load()}})
function open(row?:WardBed|ExaminationItem){editing.value=row||null;if(active.value==='beds'){const bed=row as WardBed|undefined;Object.assign(bedForm,bed?{department:bed.department,ward_name:bed.ward_name,bed_no:bed.bed_no,daily_rate:Number(bed.daily_rate),is_active:bed.is_active}:{department:departments.value[0]?.id||0,ward_name:'',bed_no:'',daily_rate:0,is_active:true})}else{const item=row as ExaminationItem|undefined;Object.assign(itemForm,item?{name:item.name,category:item.category,price:Number(item.price),is_active:item.is_active,description:item.description}:{name:'',category:'lab',price:0,is_active:true,description:''})}dialog.value=true}
async function save(){saving.value=true;try{if(active.value==='beds'){if(!bedForm.department||!bedForm.ward_name.trim()||!bedForm.bed_no.trim()){ElMessage.warning('请填写科室、病区和床位号');return}await saveWardBed({...bedForm},editing.value?.id)}else{if(!itemForm.name.trim()){ElMessage.warning('请填写检查项目名称');return}await saveExaminationItem({...itemForm,name:itemForm.name.trim()},editing.value?.id)}ElMessage.success('资源信息已保存');dialog.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||JSON.stringify(e.response?.data?.errors||'保存失败'))}finally{saving.value=false}}
async function toggle(row:WardBed|ExaminationItem){try{if(active.value==='beds'){const item=row as WardBed;await saveWardBed({is_active:!item.is_active},item.id)}else{const item=row as ExaminationItem;await saveExaminationItem({is_active:!item.is_active},item.id)}ElMessage.success('状态已更新');await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'更新失败')}}
function pageChange(value:number){ui.page=value;load()}
onMounted(async()=>{try{departments.value=await getOperationDepartments();medicines.value=(await getMedicines()).results}catch{departments.value=[];medicines.value=[]}await load()})
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">{{heading.eyebrow}}</p><h1>{{heading.title}}</h1><p>{{heading.desc}}</p></div></div>
    <el-card>
      <div v-if="showTabs" class="inline-tabs"><el-tabs v-model="active"><el-tab-pane label="床位配置" name="beds"/><el-tab-pane label="检查项目" name="exams"/><el-tab-pane label="库存流水" name="movements"/></el-tabs></div>
      <div class="table-tools resource-tools">
        <el-input v-model="ui.search" clearable placeholder="搜索名称、病区、床位或流水备注" @keyup.enter="ui.page=1;load()"/>
        <el-select v-if="active!=='movements'" v-model="ui.enabled" clearable placeholder="全部启停状态" style="width:160px"><el-option label="启用" value="true"/><el-option label="停用" value="false"/></el-select>
        <el-select v-if="active==='movements'" v-model="ui.medicineId" clearable filterable placeholder="全部药品" style="width:180px"><el-option v-for="item in medicines" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-select v-if="active==='movements'" v-model="ui.movementType" clearable placeholder="全部流水类型" style="width:170px"><el-option v-for="item in types" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select>
        <el-date-picker v-if="active==='movements'" v-model="ui.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期"/>
        <el-button @click="ui.page=1;load()">查询</el-button>
        <el-button v-if="active!=='movements'" type="primary" @click="open()">＋ 新增{{active==='beds'?'床位':'检查项目'}}</el-button>
      </div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <template v-else>
        <el-table v-loading="loading" :data="rows" empty-text="暂无符合条件的资源记录">
          <template v-if="active==='beds'"><el-table-column prop="department_name" label="科室"/><el-table-column label="病区 / 床位" min-width="180"><template #default="{row}">{{row.ward_name}} · {{row.bed_no}}</template></el-table-column><el-table-column label="日费" width="120"><template #default="{row}">¥{{row.daily_rate}}</template></el-table-column><el-table-column label="占用状态" width="110"><template #default="{row}"><el-tag :type="row.is_occupied?'warning':'success'">{{row.is_occupied?'住院中':'空闲'}}</el-tag></template></el-table-column><el-table-column label="启用状态" width="100"><template #default="{row}">{{row.is_active?'启用':'停用'}}</template></el-table-column><el-table-column label="操作" width="160" fixed="right"><template #default="{row}"><el-button link type="primary" @click="open(row)">编辑</el-button><el-button link :disabled="row.is_occupied" :type="row.is_active?'danger':'success'" @click="toggle(row)">{{row.is_active?'停用':'启用'}}</el-button></template></el-table-column></template>
          <template v-else-if="active==='exams'"><el-table-column prop="name" label="项目名称" min-width="180"/><el-table-column prop="category_display" label="类别" width="120"/><el-table-column label="价格" width="120"><template #default="{row}">¥{{row.price}}</template></el-table-column><el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip/><el-table-column label="启用状态" width="100"><template #default="{row}">{{row.is_active?'启用':'停用'}}</template></el-table-column><el-table-column label="操作" width="160" fixed="right"><template #default="{row}"><el-button link type="primary" @click="open(row)">编辑</el-button><el-button link :type="row.is_active?'danger':'success'" @click="toggle(row)">{{row.is_active?'停用':'启用'}}</el-button></template></el-table-column></template>
          <template v-else><el-table-column prop="created_at" label="时间" min-width="175"/><el-table-column prop="medicine_name" label="药品" min-width="160"/><el-table-column prop="movement_type_display" label="流水类型" width="120"/><el-table-column label="变动数量" width="110"><template #default="{row}"><b :style="{color:row.quantity<0?'#c82014':'#006241'}">{{row.quantity>0?'+':''}}{{row.quantity}}</b></template></el-table-column><el-table-column prop="balance_after" label="变动后库存" width="120"/><el-table-column prop="operator_name" label="操作人" width="120"/><el-table-column prop="note" label="说明" min-width="180"/><el-table-column prop="prescription" label="处方 ID" width="100"><template #default="{row}">{{row.prescription||'—'}}</template></el-table-column></template>
        </el-table>
        <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="ui.page" layout="prev,pager,next" :total="total" @current-change="pageChange"/></div>
      </template>
    </el-card>
    <el-dialog v-model="dialog" :title="`${editing?'编辑':'新增'}${active==='beds'?'床位':'检查项目'}`" width="min(620px,94vw)">
      <el-form v-if="active==='beds'" label-position="top"><el-row :gutter="14"><el-col :span="12"><el-form-item label="所属科室" required><el-select v-model="bedForm.department" style="width:100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="病区名称" required><el-input v-model="bedForm.ward_name"/></el-form-item></el-col><el-col :span="12"><el-form-item label="床位号" required><el-input v-model="bedForm.bed_no"/></el-form-item></el-col><el-col :span="12"><el-form-item label="床位日费" required><el-input-number v-model="bedForm.daily_rate" :min="0" :precision="2" style="width:100%"/></el-form-item></el-col></el-row><el-switch v-model="bedForm.is_active" active-text="启用床位"/></el-form>
      <el-form v-else label-position="top"><el-row :gutter="14"><el-col :span="12"><el-form-item label="项目名称" required><el-input v-model="itemForm.name"/></el-form-item></el-col><el-col :span="12"><el-form-item label="项目类别" required><el-select v-model="itemForm.category" style="width:100%"><el-option v-for="item in categories" :key="item[0]" :label="item[1]" :value="item[0]"/></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="项目价格" required><el-input-number v-model="itemForm.price" :min="0" :precision="2" style="width:100%"/></el-form-item></el-col><el-col :span="24"><el-form-item label="项目说明"><el-input v-model="itemForm.description" maxlength="300"/></el-form-item></el-col></el-row><el-switch v-model="itemForm.is_active" active-text="启用项目"/></el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>
