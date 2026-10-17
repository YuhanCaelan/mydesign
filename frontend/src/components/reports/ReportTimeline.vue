<script setup lang="ts">
import{computed}from'vue'
import ListError from'../common/ListError.vue'
import ReportCard from'./ReportCard.vue'
import type{ExaminationOrder}from'../../types/medical'

const props=defineProps<{orders:ExaminationOrder[];loading:boolean;error:string}>()
const emit=defineEmits<{(event:'open',order:ExaminationOrder):void;(event:'retry'):void}>()

const groups=computed(()=>{
  const map=new Map<string,ExaminationOrder[]>()
  for(const order of props.orders){
    const key=(order.published_at||order.completed_at||order.created_at||'').slice(0,7)||'未知'
    map.set(key,[...(map.get(key)||[]),order])
  }
  return[...map.entries()].map(([key,items])=>({key,label:monthLabel(key),items}))
})
function monthLabel(key:string){
  if(!/^\d{4}-\d{2}$/.test(key))return'时间未记录'
  const[year,month]=key.split('-')
  return`${year} 年 ${Number(month)} 月`
}
</script>

<template>
  <ListError v-if="error" :message="error" @retry="emit('retry')"/>
  <div v-else-if="loading" class="archive-skeleton-list" aria-hidden="true">
    <article v-for="index in 3" :key="index" class="archive-skeleton-card">
      <span class="skeleton-block skeleton-date"/>
      <div class="archive-skeleton-body">
        <span class="skeleton-block skeleton-title"/>
        <span class="skeleton-block skeleton-line"/>
        <span class="skeleton-block skeleton-line short"/>
      </div>
    </article>
  </div>
  <div v-else-if="groups.length" class="archive-timeline">
    <section v-for="group in groups" :key="group.key" class="archive-month">
      <header class="archive-month-head">
        <h3>{{group.label}}</h3>
        <span>{{group.items.length}} 份报告</span>
      </header>
      <ReportCard v-for="order in group.items" :key="order.id" :order="order" @open="emit('open',$event)"/>
    </section>
  </div>
  <el-empty v-else description="暂无检查报告">
    <p class="archive-empty-hint">报告发布后会出现在这里；若刚完成检查，请稍后刷新。</p>
  </el-empty>
</template>
