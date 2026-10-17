<script setup lang="ts">
import{computed,onMounted,reactive,ref}from'vue'
import{ElMessage,ElMessageBox}from'element-plus'
import{useAuthStore}from'../../stores/auth'
import ListError from'../../components/common/ListError.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import EntityCard from'../../components/common/EntityCard.vue'
import{useListState}from'../../composables/useListState'
import type{ViewMode}from'../../utils/view'
import{adjustMedicineStock,getMedicines,saveMedicine}from'../../services/operations'
import type{Medicine}from'../../types/medical'
const auth=useAuthStore(),isAdmin=computed(()=>auth.user?.role==='admin'),state=useListState(`medicines-${auth.user?.role||'guest'}`,{keyword:'',page:1,view:(isAdmin.value?'list':'cards') as ViewMode}),rows=ref<Medicine[]>([]),total=ref(0),loading=ref(false),error=ref(''),dialog=ref(false),saving=ref(false),current=ref<Medicine|null>(null)
const form=reactive({name:'',specification:'',unit:'盒',price:0,stock:0,is_active:true})
async function load(){loading.value=true;error.value='';try{const data=await getMedicines({search:state.keyword,page:state.page});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'药品加载失败'}finally{loading.value=false}}
function search(){state.page=1;load()}
function open(row?:Medicine){current.value=row||null;Object.assign(form,row?{name:row.name,specification:row.specification,unit:row.unit,price:Number(row.price),stock:row.stock,is_active:row.is_active}:{name:'',specification:'',unit:'盒',price:0,stock:0,is_active:true});dialog.value=true}
async function submit(){if(!form.name.trim()){ElMessage.warning('请填写药品名称');return}saving.value=true;try{await saveMedicine({...form,name:form.name.trim(),specification:form.specification.trim()},current.value?.id);ElMessage.success(current.value?'药品已更新':'药品已新增');dialog.value=false;await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'保存失败')}finally{saving.value=false}}
async function stock(row:Medicine){try{const{value}=await ElMessageBox.prompt('正数为入库，负数为出库','调整库存',{inputPattern:/^-?\d+$/,inputErrorMessage:'请输入整数'});await adjustMedicineStock(row.id,Number(value));ElMessage.success('库存已调整');await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e.response?.data?.detail||'库存调整失败')}}
onMounted(load)
</script>
<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">PHARMACY INVENTORY</p><h1>{{isAdmin?'药品管理':'药品目录'}}</h1><p>维护药品规格、价格、启用状态与实时库存</p></div><el-button v-if="isAdmin" type="primary" @click="open()">＋ 新增药品</el-button></div>
    <el-card class="table-card">
      <div class="table-tools"><el-input v-model="state.keyword" clearable placeholder="搜索药品或规格" @keyup.enter="search"/><el-button @click="search">查询</el-button><span class="table-count">共 {{total}} 条</span><ViewSwitch v-model="state.view"/></div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="card-grid">
        <EntityCard v-for="row in rows" :key="row.id" :title="row.name" :subtitle="`${row.specification||'无规格'} · ${row.unit}`" :avatar="row.name.slice(0,1)" :meta="[{label:'单价',value:`¥${row.price}`},{label:'库存',value:`${row.stock} ${row.unit}`},{label:'状态',value:row.is_active?'启用':'停用'}]">
          <template #status><el-tag :type="row.stock<=10?'danger':row.stock<=30?'warning':'success'">库存 {{row.stock}}</el-tag></template>
          <template #actions><el-button v-if="isAdmin" link @click="open(row)">编辑</el-button><el-button v-if="isAdmin" link type="primary" @click="stock(row)">出入库</el-button></template>
        </EntityCard>
        <el-empty v-if="!rows.length&&!loading" description="暂无药品"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows" class="desktop-table">
          <el-table-column prop="name" label="药品名称" min-width="160"/>
          <el-table-column prop="specification" label="规格" min-width="130"/>
          <el-table-column prop="unit" label="单位" width="80"/>
          <el-table-column label="单价" width="110"><template #default="{row}">¥{{row.price}}</template></el-table-column>
          <el-table-column prop="stock" label="库存" width="100"><template #default="{row}"><el-tag :type="row.stock<=10?'danger':row.stock<=30?'warning':'success'">{{row.stock}}</el-tag></template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{row}">{{row.is_active?'启用':'停用'}}</template></el-table-column>
          <el-table-column v-if="isAdmin" label="操作" width="150"><template #default="{row}"><el-button link @click="open(row)">编辑</el-button><el-button link type="primary" @click="stock(row)">出入库</el-button></template></el-table-column>
        </el-table>
        <div class="mobile-card-list">
          <article v-for="row in rows" :key="row.id" class="mobile-info-card">
            <header><h3>{{row.name}}</h3><el-tag :type="row.stock<=10?'danger':row.stock<=30?'warning':'success'">库存 {{row.stock}}</el-tag></header>
            <p class="mobile-sub">{{row.specification||'无规格'}} · {{row.unit}}</p>
            <div class="mobile-line"><span>单价</span><b>¥{{row.price}}</b></div>
            <div class="mobile-line"><span>状态</span><b>{{row.is_active?'启用':'停用'}}</b></div>
            <div class="actions"><el-button v-if="isAdmin" link @click="open(row)">编辑</el-button><el-button v-if="isAdmin" link type="primary" @click="stock(row)">出入库</el-button></div>
          </article>
          <div v-if="!rows.length&&!loading" class="mobile-empty">暂无药品</div>
        </div>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @current-change="load"/></div>
    </el-card>
    <el-dialog v-model="dialog" :title="current?'编辑药品':'新增药品'" width="min(580px,94vw)">
      <el-form label-position="top">
        <el-row :gutter="14">
          <el-col :span="12"><el-form-item label="药品名称" required><el-input v-model="form.name"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="规格"><el-input v-model="form.specification"/></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="单位"><el-input v-model="form.unit"/></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="单价"><el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%"/></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="初始库存"><el-input-number v-model="form.stock" :min="0" style="width:100%"/></el-form-item></el-col>
        </el-row>
        <el-switch v-model="form.is_active" active-text="启用药品"/>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">保存</el-button></template>
    </el-dialog>
  </section>
</template>
