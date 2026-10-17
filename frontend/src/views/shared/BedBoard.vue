<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {useAuthStore} from '../../stores/auth'
import BedCard from '../../components/beds/BedCard.vue'
import ListError from '../../components/common/ListError.vue'
import {getBedOccupancy,getBedBoard} from '../../services/operations'
import type {BedBoardData,BoardBed} from '../../types/medical'

const auth=useAuthStore(),isAdmin=computed(()=>auth.user?.role==='admin'),rolePrefix=computed(()=>auth.user?.role==='admin'?'/console':'/doctor')
const data=ref<BedBoardData|null>(null),loading=ref(false),error=ref('')
const drawer=ref(false),detailLoading=ref(false),current=ref<BoardBed|null>(null)
const stats=computed(()=>data.value?.stats||{total:0,available:0,occupied:0,inactive:0})

async function load(){loading.value=true;error.value='';try{data.value=await getBedBoard()}catch(e:any){data.value=null;error.value=e.response?.data?.detail||'床位看板加载失败'}finally{loading.value=false}}
async function openBed(bed:BoardBed){current.value=bed;drawer.value=true;detailLoading.value=true;try{const detail=await getBedOccupancy(bed.id);current.value={...bed,...detail.bed,occupancy:detail.admission}}catch(e:any){ElMessage.error(e.response?.data?.detail||'床位详情加载失败')}finally{detailLoading.value=false}}
function admissionPath(){const id=current.value?.occupancy?.id;return id?`${rolePrefix.value}/inpatients/${id}`:''}
function returnTo(){return`${rolePrefix.value}/inpatient?tab=beds`}
function money(value?:string|null){return value===null||value===undefined?'—':`¥${Number(value).toFixed(2)}`}
function shortTime(value?:string|null){return value?value.replace('T',' ').slice(0,16):'—'}
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading">
      <div><p class="eyebrow">WARD BED BOARD</p><h1>床位看板</h1><p>按“科室 → 病区 → 床位”查看全院床位占用；点击床位查看入住详情。</p></div>
      <div class="intro-actions"><router-link v-if="isAdmin" :to="{path:`${rolePrefix}/inpatient`,query:{tab:'bed-config'}}"><el-button>床位配置</el-button></router-link><el-button @click="load">刷新</el-button></div>
    </div>
    <div class="bed-metrics">
      <div class="bed-metric"><span>全院床位</span><strong>{{stats.total}}</strong><small>当前看板全部床位</small></div>
      <div class="bed-metric available"><span>空闲</span><strong>{{stats.available}}</strong><small>绿色卡片，可直接安排入院</small></div>
      <div class="bed-metric occupied"><span>住院中</span><strong>{{stats.occupied}}</strong><small>暖橙色卡片，显示患者信息</small></div>
      <div class="bed-metric muted"><span>停用</span><strong>{{stats.inactive}}</strong><small>灰色卡片，不参与收治</small></div>
    </div>
    <ListError v-if="error" :message="error" @retry="load"/>
    <div v-else v-loading="loading" class="bed-board">
      <template v-if="data&&data.departments.length">
        <section v-for="department in data.departments" :key="department.department_id" class="bed-department">
          <header class="bed-department-head"><h2>{{department.department_name}}</h2><span>共 {{department.stats.total}} 张 · 空闲 {{department.stats.available}} · 住院中 {{department.stats.occupied}} · 停用 {{department.stats.inactive}}</span></header>
          <div v-for="ward in department.wards" :key="ward.ward_name" class="bed-group">
            <header class="bed-group-head"><h3>{{ward.ward_name}}</h3><span>共 {{ward.stats.total}} 张 · 空闲 {{ward.stats.available}} · 住院中 {{ward.stats.occupied}} · 停用 {{ward.stats.inactive}}</span></header>
            <div class="bed-grid"><BedCard v-for="bed in ward.beds" :key="bed.id" :bed="bed" :current="bed.id===current?.id" @open="openBed"/></div>
          </div>
        </section>
      </template>
      <el-empty v-else-if="!loading" description="暂无床位数据"/>
    </div>

    <el-drawer v-model="drawer" :title="current?`${current.ward_name} · ${current.bed_no}`:'床位详情'" size="min(560px,94vw)">
      <div v-if="current" v-loading="detailLoading" class="record-detail">
        <div><span>床位状态</span><b>{{current.status_label}}</b></div>
        <div><span>所属科室</span><b>{{current.department_name}}</b></div>
        <div><span>床位日费</span><b>{{money(current.daily_rate)}} / 日</b></div>
        <template v-if="current.occupancy">
          <div><span>患者</span><b>{{current.occupancy.patient_name}} · {{current.occupancy.patient_no}}</b></div>
          <div><span>住院号</span><b>{{current.occupancy.admission_no}}</b></div>
          <div><span>主治医师</span><b>{{current.occupancy.doctor_name}}</b></div>
          <div><span>入院时间</span><b>{{shortTime(current.occupancy.admitted_at)}}（已住 {{current.occupancy.days_admitted}} 天）</b></div>
          <div><span>床位日费快照</span><b>{{money(current.occupancy.daily_rate_snapshot)}} / 日</b></div>
          <div><span>入院诊断</span><p>{{current.occupancy.admission_diagnosis}}</p></div>
        </template>
        <el-empty v-else :image-size="70" :description="current.status==='inactive'?'该床位已停用':'该床位当前空闲，可直接用于入院分配'"/>
        <div v-if="current.occupancy" class="drawer-actions"><router-link :to="{path:admissionPath(),query:{returnTo:returnTo()}}"><el-button type="primary">查看住院详情与费用清单</el-button></router-link></div>
      </div>
    </el-drawer>
  </section>
</template>
