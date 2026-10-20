<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import PeopleDirectory from'../shared/PeopleDirectory.vue'
import Appointments from'../shared/Appointments.vue'
import BookingCalendar from'./BookingCalendar.vue'
const tabs:FolderTab[]=[{key:'doctors',label:'就诊预约'},{key:'directory',label:'医师查询'},{key:'appointments',label:'我的预约'}]
const{current,setTab}=useTabQuery(['doctors','directory','appointments'] as const,'doctors')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="预约就诊子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <BookingCalendar v-if="current==='doctors'"/>
      <PeopleDirectory v-else-if="current==='directory'" mode="doctors" audience="patient"/>
      <Appointments v-else/>
    </div>
  </section>
</template>
