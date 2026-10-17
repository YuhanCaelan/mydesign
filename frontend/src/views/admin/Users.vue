<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage}from'element-plus'
import{createUser,getDepartmentsAdmin,getUsers,updateUser,type ManagedUser}from'../../services/admin'
import api from'../../services/api'
import ListError from'../../components/common/ListError.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import EntityCard from'../../components/common/EntityCard.vue'
import{useListState}from'../../composables/useListState'
import type{ViewMode}from'../../utils/view'
import type{Department}from'../../types/medical'

type AccountRole='doctor'|'patient'
const props=defineProps<{role?:AccountRole}>()
const role:AccountRole=props.role||'doctor'
const ui=useListState(`admin-users-${role}`,{keyword:'',status:'',page:1,pageSize:10,view:'cards' as ViewMode})
const rows=ref<ManagedUser[]>([]),total=ref(0),loading=ref(false)
const departments=ref<Department[]>([]),dialog=ref(false),saving=ref(false),profileOpen=ref(false),profileLoading=ref(false),profile=ref<any>(null),error=ref('')
const form=reactive({full_name:'',username:'',password:'',phone:'',email:'',department_id:undefined as number|undefined,title:'',specialty:'',gender:'unknown',birth_date:'',address:''})
const isDoctorTab=computed(()=>role==='doctor')

function errorText(e:any,fallback:string){const errors=e.response?.data?.errors;if(errors){const first=Object.values(errors)[0] as string|string[]|undefined;if(first)return Array.isArray(first)?first.join('；'):String(first)}return e.response?.data?.detail||fallback}
async function load(){loading.value=true;error.value='';try{const data=await getUsers({role,search:ui.keyword.trim()||undefined,is_active:ui.status||undefined,page:ui.page,page_size:ui.pageSize});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=errorText(e,'账户加载失败')}finally{loading.value=false}}
function search(){ui.page=1;load()}
function changePage(page:number){ui.page=page;load()}
function changeSize(size:number){ui.pageSize=size;ui.page=1;load()}
async function openCreate(){if(isDoctorTab.value&&!departments.value.length){try{departments.value=(await getDepartmentsAdmin({status:'active'})).results}catch{departments.value=[]}}
  Object.assign(form,{full_name:'',username:'',password:'',phone:'',email:'',department_id:undefined,title:'',specialty:'',gender:'unknown',birth_date:'',address:''});dialog.value=true}
async function submit(){
  if(!form.full_name.trim()||!form.username.trim()||!form.password){ElMessage.warning('请完整填写姓名、用户名和初始密码');return}
  if(isDoctorTab.value&&!form.department_id){ElMessage.warning('医师必须选择所属科室');return}
  const payload:Record<string,unknown>=isDoctorTab.value
    ?{username:form.username.trim(),full_name:form.full_name.trim(),password:form.password,role:'doctor',phone:form.phone.trim(),email:form.email.trim(),department_id:form.department_id,title:form.title.trim(),specialty:form.specialty.trim()}
    :{username:form.username.trim(),full_name:form.full_name.trim(),password:form.password,role:'patient',phone:form.phone.trim(),email:form.email.trim(),gender:form.gender,birth_date:form.birth_date||null,address:form.address.trim()}
  saving.value=true;try{const created=await createUser(payload);ElMessage.success(isDoctorTab.value?`医师创建成功，编号 ${created.doctor_no}`:`患者创建成功，编号 ${created.patient_no}`);dialog.value=false;ui.page=1;await load()}catch(e:any){ElMessage.error(errorText(e,'创建失败'))}finally{saving.value=false}}
async function toggle(row:ManagedUser){try{await updateUser(row.id,{is_active:!row.is_active});ElMessage.success(row.is_active?'账户已禁用，历史记录仍可查询':'账户已启用');await load()}catch(e:any){ElMessage.error(errorText(e,'状态更新失败'))}}
async function openProfile(row:ManagedUser){profileOpen.value=true;profileLoading.value=true;profile.value=row;try{const endpoint=row.role==='doctor'?`doctors/${row.doctor_id}/`:`patients/${row.patient_id}/`;profile.value={...row,...(await api.get(endpoint)).data}}catch(e:any){ElMessage.error(errorText(e,'档案加载失败'))}finally{profileLoading.value=false}}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading">
      <div><p class="eyebrow">{{isDoctorTab?'DOCTOR ACCOUNTS':'PATIENT ACCOUNTS'}}</p><h1>{{isDoctorTab?'医师账户':'患者账户'}}</h1><p>{{isDoctorTab?'查看医师编号、科室、职称、专业方向与启用状态；点击行查看医师档案':'查看患者编号、联系方式、建档时间与启用状态；点击行查看患者档案'}}</p></div>
      <el-button type="primary" @click="openCreate">＋ 新增{{isDoctorTab?'医师':'患者'}}</el-button>
    </div>
    <el-card class="table-card">
      <div class="table-tools">
        <el-input v-model="ui.keyword" clearable :placeholder="isDoctorTab?'搜索姓名、用户名、编号、手机号、职称或专业方向':'搜索姓名、用户名、患者编号或手机号'" @keyup.enter="search"/>
        <el-select v-model="ui.status" clearable placeholder="全部启用状态" style="width:160px" @change="search"><el-option label="启用" value="true"/><el-option label="禁用" value="false"/></el-select>
        <el-button @click="search">查询</el-button>
        <span class="table-count">共 {{total}} 个{{isDoctorTab?'医师':'患者'}}账户</span>
        <ViewSwitch v-model="ui.view"/>
      </div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="ui.view==='cards'" class="card-grid compact">
        <EntityCard v-for="row in rows" :key="row.id" :title="row.full_name" :subtitle="isDoctorTab?`${row.department_name||'未分配科室'} · ${row.doctor_title||'未填写职称'}`:`${row.patient_no||'—'} · ${row.created_at?.slice(0,10)||'—'}`" :avatar="row.full_name?.slice(0,1)" :meta="isDoctorTab?[{label:'医师编号',value:row.doctor_no},{label:'联系方式',value:row.phone||'—'},{label:'专业方向',value:row.doctor_specialty||'—'},{label:'账户状态',value:row.is_active_display}]:[{label:'患者编号',value:row.patient_no},{label:'联系方式',value:row.phone||'—'},{label:'建档时间',value:row.created_at?.slice(0,10)},{label:'账户状态',value:row.is_active_display}]" @open="openProfile(row)">
          <template #status><el-tag :type="row.is_active?'success':'info'">{{row.is_active_display}}</el-tag></template>
          <template #actions><el-button link type="primary" @click.stop="openProfile(row)">查看档案</el-button><el-button link :type="row.is_active?'danger':'success'" @click.stop="toggle(row)">{{row.is_active?'禁用':'启用'}}</el-button></template>
        </EntityCard>
        <el-empty v-if="!rows.length&&!loading" :description="`暂无${isDoctorTab?'医师':'患者'}账户`"/>
      </div>
      <el-table v-else v-loading="loading" :data="rows" :empty-text="`暂无${isDoctorTab?'医师':'患者'}账户`" @row-click="openProfile">
        <template v-if="isDoctorTab">
          <el-table-column prop="doctor_no" label="医师编号" min-width="115"/>
          <el-table-column prop="full_name" label="姓名" min-width="100"/>
          <el-table-column prop="department_name" label="科室" min-width="150"/>
          <el-table-column prop="doctor_title" label="职称" min-width="110"><template #default="{row}">{{row.doctor_title||'—'}}</template></el-table-column>
          <el-table-column prop="doctor_specialty" label="专业方向" min-width="190" show-overflow-tooltip><template #default="{row}">{{row.doctor_specialty||'—'}}</template></el-table-column>
          <el-table-column prop="phone" label="联系方式" min-width="130"/>
        </template>
        <template v-else>
          <el-table-column prop="patient_no" label="患者编号" min-width="115"/>
          <el-table-column prop="full_name" label="姓名" min-width="100"/>
          <el-table-column prop="phone" label="联系方式" min-width="130"/>
          <el-table-column label="建档时间" min-width="160"><template #default="{row}">{{row.created_at?.replace('T',' ').slice(0,16)||'—'}}</template></el-table-column>
        </template>
        <el-table-column label="状态" width="95"><template #default="{row}"><el-tag :type="row.is_active?'success':'info'">{{row.is_active_display}}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button link :type="row.is_active?'danger':'success'" @click.stop="toggle(row)">{{row.is_active?'禁用':'启用'}}</el-button></template></el-table-column>
      </el-table>
      <div class="pagination">
        <span>共 {{total}} 条 · 点击行查看{{isDoctorTab?'医师档案':'患者档案'}}</span>
        <el-pagination v-model:current-page="ui.page" v-model:page-size="ui.pageSize" layout="sizes,prev,pager,next" :page-sizes="[10,20,50]" :total="total" @current-change="changePage" @size-change="changeSize"/>
      </div>
    </el-card>

    <el-dialog v-model="dialog" :title="`新增${isDoctorTab?'医师账户':'患者账户'}`" width="min(640px,94vw)" destroy-on-close>
      <el-form label-position="top">
        <el-row :gutter="14">
          <el-col :md="12"><el-form-item label="姓名" required><el-input v-model="form.full_name"/></el-form-item></el-col>
          <el-col :md="12"><el-form-item label="用户名" required><el-input v-model="form.username"/></el-form-item></el-col>
          <el-col :md="12"><el-form-item label="初始密码" required><el-input v-model="form.password" type="password" show-password/></el-form-item></el-col>
          <el-col :md="12"><el-form-item label="手机号"><el-input v-model="form.phone"/></el-form-item></el-col>
          <el-col :md="12"><el-form-item label="邮箱"><el-input v-model="form.email"/></el-form-item></el-col>
          <template v-if="isDoctorTab">
            <el-col :md="12"><el-form-item label="所属科室" required><el-select v-model="form.department_id" style="width:100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select></el-form-item></el-col>
            <el-col :md="12"><el-form-item label="职称"><el-input v-model="form.title"/></el-form-item></el-col>
            <el-col :md="24"><el-form-item label="专业方向"><el-input v-model="form.specialty"/></el-form-item></el-col>
          </template>
          <template v-else>
            <el-col :md="12"><el-form-item label="性别"><el-select v-model="form.gender" style="width:100%"><el-option label="男" value="male"/><el-option label="女" value="female"/><el-option label="其他" value="other"/><el-option label="未填写" value="unknown"/></el-select></el-form-item></el-col>
            <el-col :md="12"><el-form-item label="出生日期"><el-date-picker v-model="form.birth_date" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item></el-col>
            <el-col :md="24"><el-form-item label="联系地址"><el-input v-model="form.address"/></el-form-item></el-col>
          </template>
        </el-row>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">创建{{isDoctorTab?'医师':'患者'}}</el-button></template>
    </el-dialog>

    <el-drawer v-model="profileOpen" :title="isDoctorTab?'医师档案':'患者档案'" size="min(560px,94vw)">
      <div v-if="profile" v-loading="profileLoading" class="record-detail">
        <div><span>{{isDoctorTab?'医师编号':'患者编号'}}</span><b>{{isDoctorTab?profile.doctor_no:profile.patient_no}}</b></div>
        <div><span>姓名</span><b>{{profile.full_name}}</b></div>
        <div><span>账户状态</span><b>{{profile.is_active?'启用':'禁用'}}</b></div>
        <div><span>联系方式</span><b>{{profile.phone||'—'}}{{profile.email?` · ${profile.email}`:''}}</b></div>
        <template v-if="isDoctorTab">
          <div><span>所属科室</span><b>{{profile.department_name||'—'}}</b></div>
          <div><span>职称 / 专业方向</span><b>{{profile.doctor_title||profile.title||'—'}} · {{profile.doctor_specialty||profile.specialty||'—'}}</b></div>
          <div><span>个人简介</span><p>{{profile.introduction||'暂无简介'}}</p></div>
        </template>
        <template v-else>
          <div><span>性别 / 出生日期</span><b>{{profile.gender_display||'—'}} · {{profile.birth_date||'—'}}</b></div>
          <div><span>血型 / 过敏史</span><b>{{profile.blood_group||'—'}} · {{profile.allergies||'无已知过敏'}}</b></div>
          <div><span>既往病史</span><p>{{profile.medical_history||'—'}}</p></div>
          <div><span>联系地址</span><p>{{profile.address||'—'}}</p></div>
          <div><span>建档时间</span><b>{{profile.created_at?.replace('T',' ').slice(0,16)||'—'}}</b></div>
        </template>
      </div>
    </el-drawer>
  </section>
</template>
