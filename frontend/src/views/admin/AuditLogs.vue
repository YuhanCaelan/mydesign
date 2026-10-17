<script setup lang="ts">
import{onMounted,ref}from'vue'
import api from'../../services/api'
import ListError from'../../components/common/ListError.vue'
import ViewSwitch from'../../components/common/ViewSwitch.vue'
import EventCard from'../../components/common/EventCard.vue'
import{useListState} from'../../composables/useListState'
import type{ViewMode}from'../../utils/view'
import type{PageResult}from'../../types/medical'
const state=useListState('audit-logs',{page:1,view:'cards' as ViewMode,filters:{search:'',action:'',resource:'',dateRange:[] as string[]}})
const rows=ref<any[]>([]),total=ref(0),loading=ref(false),error=ref('')
async function load(){loading.value=true;error.value='';try{const{data}=await api.get<PageResult<any>>('audit-logs/',{params:{page:state.page,search:state.filters.search,action:state.filters.action||undefined,resource:state.filters.resource||undefined,date_from:state.filters.dateRange?.[0],date_to:state.filters.dateRange?.[1]}});rows.value=data.results;total.value=data.count}catch(e:any){rows.value=[];total.value=0;error.value=e.response?.data?.detail||'审计日志加载失败'}finally{loading.value=false}}
function search(){state.page=1;load()}
function reset(){Object.assign(state.filters,{search:'',action:'',resource:'',dateRange:[]});state.page=1;load()}
onMounted(load)
</script>
<template>
  <section>
    <div class="page-heading"><div><h1>操作审计</h1><p>按操作人、资源、动作和日期追溯关键行为</p></div></div>
    <el-card class="table-card">
      <div class="table-tools audit-tools">
        <el-input v-model="state.filters.search" clearable placeholder="操作人或描述" @keyup.enter="search"/>
        <el-input v-model="state.filters.resource" clearable placeholder="资源，如 billing"/>
        <el-input v-model="state.filters.action" clearable placeholder="动作，如 pay"/>
        <el-date-picker v-model="state.filters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期"/>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <span class="table-count">共 {{total}} 条</span>
        <ViewSwitch v-model="state.view"/>
      </div>
      <ListError v-if="error" :message="error" @retry="load"/>
      <div v-else-if="state.view==='cards'" v-loading="loading" class="timeline-list">
        <EventCard v-for="row in rows" :key="row.id" :time="row.created_at?.replace('T',' ').slice(0,16)" :title="row.description||`${row.resource} ${row.action}`" :subtitle="`${row.user_name||'系统'} · ${row.resource} · ${row.action}`" :actor="row.user_name||'系统'" :action="row.action" :target="`${row.resource}${row.object_id?` #${row.object_id}`:''}`"/>
        <el-empty v-if="!rows.length&&!loading" description="暂无审计记录"/>
      </div>
      <template v-else>
        <el-table v-loading="loading" :data="rows">
          <el-table-column prop="created_at" label="时间" min-width="180"/>
          <el-table-column prop="user_name" label="操作人"/>
          <el-table-column prop="resource" label="资源"/>
          <el-table-column prop="action" label="动作"/>
          <el-table-column prop="object_id" label="对象 ID"/>
          <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip/>
        </el-table>
      </template>
      <div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="state.page" layout="prev,pager,next" :total="total" @change="load"/></div>
    </el-card>
  </section>
</template>
