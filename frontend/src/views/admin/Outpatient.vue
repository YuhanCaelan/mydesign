<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Appointments from'../shared/Appointments.vue'
import Schedules from'./Schedules.vue'
const tabs:FolderTab[]=[{key:'appointments',label:'预约管理'},{key:'schedules',label:'排班设置'},{key:'visits',label:'门诊就诊'}]
const{current,setTab}=useTabQuery(['appointments','schedules','visits'] as const,'appointments')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="门诊管理子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Appointments v-if="current==='appointments'"/>
      <Schedules v-else-if="current==='schedules'" view="schedules"/>
      <Schedules v-else view="visits"/>
    </div>
  </section>
</template>
