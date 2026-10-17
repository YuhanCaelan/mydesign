<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Prescriptions from'../shared/Prescriptions.vue'
import Inpatients from'../shared/Inpatients.vue'
import Services from'../smart/Services.vue'
const tabs:FolderTab[]=[{key:'prescriptions',label:'处方'},{key:'admissions',label:'住院记录'},{key:'smart',label:'智慧服务'}]
const{current,setTab}=useTabQuery(['prescriptions','admissions','smart'] as const,'prescriptions')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="我的医疗子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Prescriptions v-if="current==='prescriptions'"/>
      <Inpatients v-else-if="current==='admissions'"/>
      <Services v-else/>
    </div>
  </section>
</template>
