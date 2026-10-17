<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Appointments from'../shared/Appointments.vue'
import Schedules from'../admin/Schedules.vue'
import PeopleDirectory from'../shared/PeopleDirectory.vue'
const tabs:FolderTab[]=[{key:'appointments',label:'接诊管理'},{key:'schedule',label:'我的排班'},{key:'visits',label:'门诊就诊'},{key:'patients',label:'我的患者'}]
const{current,setTab}=useTabQuery(['appointments','schedule','visits','patients'] as const,'appointments')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="门诊工作子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Appointments v-if="current==='appointments'"/>
      <Schedules v-else-if="current==='schedule'" view="schedules"/>
      <Schedules v-else-if="current==='visits'" view="visits"/>
      <PeopleDirectory v-else mode="patients" audience="doctor"/>
    </div>
  </section>
</template>
