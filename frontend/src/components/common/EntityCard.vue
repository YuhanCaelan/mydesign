<script setup lang="ts">
const props=defineProps<{
  title:string
  subtitle?:string
  avatar?:string
  meta?:{label:string;value:string|number|null|undefined}[]
  clickable?:boolean
}>()
const emit=defineEmits<{(event:'open'):void}>()
function activate(){if(props.clickable!==false)emit('open')}
</script>
<template>
  <article class="entity-card" :class="{clickable:clickable!==false}" :tabindex="clickable===false?-1:0" @click="activate" @keyup.enter="activate">
    <header class="entity-card-head">
      <span class="entity-avatar" aria-hidden="true">{{avatar||title.slice(0,1)}}</span>
      <div class="entity-identity"><h3>{{title}}</h3><p v-if="subtitle">{{subtitle}}</p></div>
      <slot name="status"/>
    </header>
    <dl v-if="meta?.length" class="entity-meta">
      <div v-for="item in meta" :key="item.label"><dt>{{item.label}}</dt><dd>{{item.value??'—'}}</dd></div>
    </dl>
    <slot name="extra"/>
    <footer v-if="$slots.actions" class="entity-actions" @click.stop @keydown.stop><slot name="actions"/></footer>
  </article>
</template>
