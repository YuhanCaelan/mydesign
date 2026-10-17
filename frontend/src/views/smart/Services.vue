<script setup lang="ts">
import{computed,onMounted,ref}from'vue'
import{ElMessage}from'element-plus'
import api from'../../services/api'
import ListError from'../../components/common/ListError.vue'
import{useAuthStore}from'../../stores/auth'
interface Service{id:number;name:string;service_type:string;description:string;is_enabled:boolean;updated_at:string}
const auth=useAuthStore(),services=ref<Service[]>([]),loading=ref(false),error=ref(''),isAdmin=computed(()=>auth.user?.role==='admin')
async function load(){loading.value=true;error.value='';try{const{data}=await api.get('ai/services/');services.value=Array.isArray(data)?data:data.results||[]}catch(e:any){services.value=[];error.value=e.response?.data?.detail||'智慧服务加载失败'}finally{loading.value=false}}
async function toggle(item:Service){try{await api.patch(`ai/services/${item.id}/`,{is_enabled:!item.is_enabled});ElMessage.success('服务状态已更新');await load()}catch(e:any){ElMessage.error(e.response?.data?.detail||'更新失败')}}
onMounted(load)
</script>
<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">INTELLIGENT MEDICAL SERVICES</p><h1>智慧服务</h1><p>医学影像分析与辅助诊断的统一扩展入口</p></div></div>
    <el-alert title="AI 输出仅作为辅助分析信息，不能替代医师诊断；当前版本仅保留服务配置与状态，尚未接入真实模型或分析流程。" type="warning" :closable="false" show-icon/>
    <ListError v-if="error" :message="error" @retry="load"/>
    <div v-else class="service-grid" v-loading="loading">
      <article v-for="item in services" :key="item.id" class="service-card">
        <div><span class="ai-mark">AI</span><el-tag :type="item.is_enabled?'success':'info'">{{item.is_enabled?'已启用':'尚未启用'}}</el-tag></div>
        <h3>{{item.name}}</h3>
        <p>{{item.description||'该服务暂未配置说明。'}}</p>
        <small>{{item.service_type}}</small>
        <el-button v-if="isAdmin" text :type="item.is_enabled?'danger':'primary'" @click="toggle(item)">{{item.is_enabled?'停用服务':'启用服务'}}</el-button>
        <p v-else class="service-note"><el-tag type="info" size="small">接口预留</el-tag> 当前版本未接入分析流程，仅展示服务状态。</p>
      </article>
      <el-empty v-if="!services.length&&!loading" description="尚未配置智能服务；可通过管理 API 添加模型服务"/>
    </div>
  </section>
</template>
