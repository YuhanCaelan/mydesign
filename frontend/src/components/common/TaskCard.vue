<script setup lang="ts">
withDefaults(defineProps<{
  title:string
  subtitle?:string
  time?:string
  accent?:'primary'|'success'|'warning'|'danger'|'info'
  highlight?:boolean
  meta?:{label:string;value:string|number|null|undefined}[]
}>(),{accent:'info'})
</script>
<template>
  <article class="task-card" :data-accent="accent" :data-highlight="highlight?'true':undefined">
    <header class="task-card-head">
      <div class="task-card-title">
        <span v-if="time" class="task-card-time">{{time}}</span>
        <h3>{{title}}</h3>
        <p v-if="subtitle">{{subtitle}}</p>
      </div>
      <slot name="status"/>
    </header>
    <dl v-if="meta?.length" class="task-meta">
      <div v-for="item in meta" :key="item.label"><dt>{{item.label}}</dt><dd>{{item.value??'—'}}</dd></div>
    </dl>
    <slot name="extra"/>
    <footer v-if="$slots.actions" class="task-actions"><slot name="actions"/></footer>
  </article>
</template>
