<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Records from'../shared/Records.vue'
import Prescriptions from'../shared/Prescriptions.vue'
import Examinations from'../shared/Examinations.vue'
import Inpatients from'../shared/Inpatients.vue'
import Services from'../smart/Services.vue'
const tabs:FolderTab[]=[{key:'records',label:'病历'},{key:'prescriptions',label:'处方'},{key:'reports',label:'检查报告'},{key:'admissions',label:'住院记录'},{key:'smart',label:'智慧服务'}]
const{current,setTab}=useTabQuery(['records','prescriptions','reports','admissions','smart'] as const,'records')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="我的医疗子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Records v-if="current==='records'"/>
      <Prescriptions v-else-if="current==='prescriptions'"/>
      <Examinations v-else-if="current==='reports'"/>
      <Inpatients v-else-if="current==='admissions'"/>
      <Services v-else/>
    </div>
  </section>
</template>
