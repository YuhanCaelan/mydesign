<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Examinations from'../shared/Examinations.vue'
import Medicines from'../shared/Medicines.vue'
import Services from'../smart/Services.vue'
import ClinicalResources from'./ClinicalResources.vue'
const tabs:FolderTab[]=[{key:'examinations',label:'检查管理'},{key:'exam-items',label:'检查项目'},{key:'medicines',label:'药品管理'},{key:'stock',label:'库存流水'},{key:'smart',label:'智慧服务'}]
const{current,setTab}=useTabQuery(['examinations','exam-items','medicines','stock','smart'] as const,'examinations')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="医疗资源子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Examinations v-if="current==='examinations'"/>
      <ClinicalResources v-else-if="current==='exam-items'" view="exams"/>
      <Medicines v-else-if="current==='medicines'"/>
      <ClinicalResources v-else-if="current==='stock'" view="movements"/>
      <Services v-else/>
    </div>
  </section>
</template>
