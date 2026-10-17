<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Inpatients from'../shared/Inpatients.vue'
import BedBoard from'../shared/BedBoard.vue'
const tabs:FolderTab[]=[{key:'admissions',label:'住院记录'},{key:'beds',label:'床位看板'}]
const{current,setTab}=useTabQuery(['admissions','beds'] as const,'admissions')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="住院工作子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Inpatients v-if="current==='admissions'"/>
      <BedBoard v-else/>
    </div>
  </section>
</template>
