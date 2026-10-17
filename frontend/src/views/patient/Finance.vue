<script setup lang="ts">
import FolderTabs,{type FolderTab}from'../../components/navigation/FolderTabs.vue'
import{useTabQuery}from'../../composables/useTabQuery'
import Billing from'../shared/Billing.vue'
const tabs:FolderTab[]=[{key:'bills',label:'全部账单'},{key:'exam-costs',label:'检查费用'},{key:'medicine-costs',label:'药品费用'}]
const{current,setTab}=useTabQuery(['bills','exam-costs','medicine-costs'] as const,'bills')
</script>
<template>
  <section class="tabbed-page">
    <FolderTabs :tabs="tabs" :model-value="current" aria-label="我的费用子页面" @update:model-value="setTab"/>
    <div :id="`panel-${current}`" class="folder-panel" role="tabpanel">
      <Billing v-if="current==='bills'" view="bills"/>
      <Billing v-else-if="current==='exam-costs'" view="exam-costs"/>
      <Billing v-else view="medicine-costs"/>
    </div>
  </section>
</template>
