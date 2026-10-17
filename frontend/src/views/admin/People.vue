<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Users from'./Users.vue'
import Departments from'./Departments.vue'
const tabs:FolderTab[]=[{key:'doctors',label:'医师账户'},{key:'patients',label:'患者账户'},{key:'departments',label:'科室管理'}]
const{current,setTab}=useTabQuery(['doctors','patients','departments'] as const,'doctors')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="人员与科室子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel" :aria-label="tabs.find(tab=>tab.key===current)?.label">
      <Users v-if="current==='doctors'" role="doctor"/>
      <Users v-else-if="current==='patients'" role="patient"/>
      <Departments v-else/>
    </div>
  </section>
</template>
