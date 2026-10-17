<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Records from'../shared/Records.vue'
import Prescriptions from'../shared/Prescriptions.vue'
import Examinations from'../shared/Examinations.vue'
import Medicines from'../shared/Medicines.vue'
import Services from'../smart/Services.vue'
const tabs:FolderTab[]=[{key:'records',label:'电子病历'},{key:'prescriptions',label:'电子处方'},{key:'examinations',label:'医学检查'},{key:'medicines',label:'药品目录'},{key:'smart',label:'智慧服务'}]
const{current,setTab}=useTabQuery(['records','prescriptions','examinations','medicines','smart'] as const,'records')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="诊疗资料子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Records v-if="current==='records'"/>
      <Prescriptions v-else-if="current==='prescriptions'"/>
      <Examinations v-else-if="current==='examinations'"/>
      <Medicines v-else-if="current==='medicines'"/>
      <Services v-else/>
    </div>
  </section>
</template>
