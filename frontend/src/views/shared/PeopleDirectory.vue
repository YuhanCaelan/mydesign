<script setup lang="ts">
import{computed,onMounted,ref}from'vue'
import{useRouter}from'vue-router'
import api from'../../services/api'
import ListError from'../../components/common/ListError.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import EntityCard from'../../components/common/EntityCard.vue'
import{useListState}from'../../composables/useListState'
import type{ViewMode}from'../../utils/view'
import type{PageResult}from'../../types/medical'

type Mode='doctors'|'patients'
type Audience='admin'|'doctor'|'patient'
const props=defineProps<{mode:Mode;audience?:Audience}>()
const router=useRouter(),rows=ref<any[]>([]),total=ref(0),loading=ref(false),error=ref(''),detail=ref<any>(null),drawer=ref(false),departments=ref<any[]>([])
const state=useListState(`directory-${props.mode}-${props.audience||'admin'}`,{page:1,keyword:'',department:'',view:'cards' as ViewMode})
const isDoctors=computed(()=>props.mode==='doctors'),isPatientSearch=computed(()=>isDoctors.value&&props.audience==='patient')
const title=computed(()=>isDoctors.value?(isPatientSearch.value?'医师查询':'医师管理'):props.audience==='doctor'?'我的患者':'患者管理')
const description=computed(()=>isPatientSearch.value?'按科室与专长查找医师，直接进入预约挂号':props.audience==='doctor'?'查看与本人存在预约关系的患者档案和就诊状态':'搜索、查看档案与当前业务状态')
async function load(){loading.value=true;error.value='';try{const endpoint=isDoctors.value?'doctors/':'patients/';const{data}=await api.get<any[]|PageResult<any>>(endpoint,{params:{page:state.page,search:state.keyword,department:state.department||undefined}});rows.value=Array.isArray(data)?data:data.results;total.value=Array.isArray(data)?data.length:data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'资料加载失败'}finally{loading.value=false}}
function search(){state.page=1;load()}
function view(row:any){detail.value=row;drawer.value=true}
function book(row:any){router.push({path:'/patient/visits',query:{tab:'appointments',department:row.department_id,doctor:row.id}})}
onMounted(async()=>{try{const{data}=await api.get('departments/',{params:{status:'active'}});departments.value=Array.isArray(data)?data:data.results}catch{departments.value=[]}await load()})
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">{{isDoctors?'DOCTOR DIRECTORY':'PATIENT DIRECTORY'}}</p><h1>{{title}}</h1><p>{{description}}</p></div></div>
    <el-card class="table-card">
      <div class="table-tools">
        <el-input v-model="state.keyword" clearable placeholder="搜索姓名、编号或专业方向" @keyup.enter="search"/>
        <el-select v-if="isDoctors" v-model="state.department" clearable placeholder="全部科室" style="width:190px" @change="search"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-button @click="search">查询</el-button>
        <span class="table-count">共 {{total}} 条</span>
        <ViewSwitch v-if="props.audience==='admin'" v-model="state.view"/>
      </div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="card-grid">
        <EntityCard v-for="row in rows" :key="row.id" :title="row.full_name" :subtitle="isDoctors?`${row.department_name} · ${row.title||'未填写职称'}`:`${row.patient_no} · ${row.gender_display||'未填写性别'}`" :avatar="row.full_name?.slice(0,1)" :meta="isDoctors?[{label:'医师编号',value:row.doctor_no},{label:'专业方向',value:row.specialty||'—'},{label:'状态',value:row.is_available?'可接诊':'暂停接诊'}]:[{label:'手机号',value:row.phone||'—'},{label:'出生日期',value:row.birth_date||'—'},{label:'血型',value:row.blood_group||'—'}]" @open="view(row)">
          <template #status><el-tag v-if="isDoctors" :type="row.is_available?'success':'info'">{{row.is_available?'可接诊':'暂停接诊'}}</el-tag><el-tag v-else :type="row.is_active?'success':'info'">{{row.is_active?'启用':'禁用'}}</el-tag></template>
          <template #actions><el-button link type="primary" @click.stop="view(row)">查看详情</el-button><el-button v-if="isPatientSearch&&row.is_available" link type="success" @click.stop="book(row)">预约</el-button></template>
        </EntityCard>
        <el-empty v-if="!rows.length&&!loading" description="暂无匹配资料"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows" empty-text="暂无匹配资料" class="desktop-table">
          <template v-if="isDoctors">
            <el-table-column prop="doctor_no" label="医师编号"/>
            <el-table-column prop="full_name" label="姓名"/>
            <el-table-column prop="department_name" label="主科室"/>
            <el-table-column prop="title" label="职称"/>
            <el-table-column prop="specialty" label="专业方向" min-width="220" show-overflow-tooltip/>
            <el-table-column label="状态"><template #default="{row}"><el-tag :type="row.is_available?'success':'info'">{{row.is_available?'可接诊':'暂停接诊'}}</el-tag></template></el-table-column>
          </template>
          <template v-else>
            <el-table-column prop="patient_no" label="患者编号"/>
            <el-table-column prop="full_name" label="姓名"/>
            <el-table-column prop="gender_display" label="性别"/>
            <el-table-column prop="birth_date" label="出生日期"/>
            <el-table-column prop="phone" label="手机号"/>
            <el-table-column prop="blood_group" label="血型"/>
          </template>
          <el-table-column label="操作" width="170" fixed="right"><template #default="{row}"><el-button link type="primary" @click="view(row)">查看详情</el-button><el-button v-if="isPatientSearch&&row.is_available" link type="success" @click="book(row)">预约</el-button></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in rows" :key="row.id" class="mobile-info-card">
            <header><h3>{{row.full_name}}</h3><el-tag v-if="isDoctors" :type="row.is_available?'success':'info'">{{row.is_available?'可接诊':'暂停接诊'}}</el-tag></header>
            <p class="mobile-sub">{{isDoctors?`${row.doctor_no} · ${row.department_name} · ${row.title}`:`${row.patient_no} · ${row.gender_display||'—'} · ${row.phone||'—'}`}}</p>
            <div class="mobile-line" v-if="isDoctors"><span>专业方向</span><b>{{row.specialty||'—'}}</b></div>
            <div class="mobile-line" v-else><span>血型</span><b>{{row.blood_group||'—'}}</b></div>
            <div class="actions"><el-button link type="primary" @click="view(row)">查看详情</el-button><el-button v-if="isPatientSearch&&row.is_available" link type="success" @click="book(row)">预约</el-button></div>
          </article>
          <div v-if="!rows.length&&!loading" class="mobile-empty">暂无匹配资料</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
    <el-drawer v-model="drawer" :title="isDoctors?'医师详情':'患者档案'" size="min(520px,94vw)">
      <el-descriptions v-if="detail" :column="1" border>
        <template v-if="isDoctors"><el-descriptions-item label="姓名">{{detail.full_name}}</el-descriptions-item><el-descriptions-item label="科室">{{detail.department_names?.join('、')||detail.department_name}}</el-descriptions-item><el-descriptions-item label="职称">{{detail.title||'—'}}</el-descriptions-item><el-descriptions-item label="专业方向">{{detail.specialty||'—'}}</el-descriptions-item><el-descriptions-item label="简介">{{detail.introduction||'—'}}</el-descriptions-item></template>
        <template v-else><el-descriptions-item label="姓名">{{detail.full_name}}</el-descriptions-item><el-descriptions-item label="手机号">{{detail.phone||'—'}}</el-descriptions-item><el-descriptions-item label="过敏史">{{detail.allergies||'无已知过敏'}}</el-descriptions-item><el-descriptions-item label="既往病史">{{detail.medical_history||'—'}}</el-descriptions-item><el-descriptions-item label="地址">{{detail.address||'—'}}</el-descriptions-item></template>
      </el-descriptions>
    </el-drawer>
  </section>
</template>
