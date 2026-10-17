<script setup lang="ts">
import{nextTick,ref}from'vue'

export interface FolderTab{key:string;label:string;hint?:string}
const props=defineProps<{tabs:FolderTab[];modelValue:string;ariaLabel?:string}>()
const emit=defineEmits<{(event:'update:modelValue',value:string):void}>()
const buttons=ref<HTMLButtonElement[]>([])

function select(key:string){if(key!==props.modelValue)emit('update:modelValue',key)}
function onKeydown(event:KeyboardEvent,index:number){
  let target=index
  if(event.key==='ArrowRight')target=(index+1)%props.tabs.length
  else if(event.key==='ArrowLeft')target=(index-1+props.tabs.length)%props.tabs.length
  else if(event.key==='Home')target=0
  else if(event.key==='End')target=props.tabs.length-1
  else return
  event.preventDefault()
  const key=props.tabs[target]?.key
  if(!key)return
  select(key)
  nextTick(()=>buttons.value[target]?.focus())
}
</script>

<template>
  <div class="folder-tabs" role="tablist" :aria-label="ariaLabel||'子页面'">
    <button
      v-for="(tab,index) in tabs"
      :key="tab.key"
      ref="buttons"
      type="button"
      role="tab"
      class="folder-tab"
      :class="{active:tab.key===modelValue}"
      :aria-selected="tab.key===modelValue"
      :aria-controls="`panel-${tab.key}`"
      :tabindex="tab.key===modelValue?0:-1"
      @click="select(tab.key)"
      @keydown="onKeydown($event,index)">
      <span>{{tab.label}}</span>
      <small v-if="tab.hint">{{tab.hint}}</small>
    </button>
  </div>
</template>
