<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import PeopleDirectory from'../shared/PeopleDirectory.vue'
import Appointments from'../shared/Appointments.vue'
const tabs:FolderTab[]=[{key:'doctors',label:'医师查询'},{key:'appointments',label:'我的预约'}]
const{current,setTab}=useTabQuery(['doctors','appointments'] as const,'doctors')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="预约就诊子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <PeopleDirectory v-if="current==='doctors'" mode="doctors" audience="patient"/>
      <Appointments v-else/>
    </div>
  </section>
</template>
