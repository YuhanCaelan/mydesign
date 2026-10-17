<script setup lang="ts">
defineProps<{
  time:string
  title:string
  subtitle?:string
  description?:string
  actor?:string
  action?:string
  target?:string
}>()
</script>
<template>
  <article class="event-card">
    <time class="event-time">{{time}}</time>
    <div class="event-body">
      <header class="event-head"><h3>{{title}}</h3><slot name="status"/></header>
      <p v-if="subtitle" class="event-sub">{{subtitle}}</p>
      <p v-if="description" class="event-description">{{description}}</p>
      <div v-if="actor||action||target" class="event-meta">
        <span v-if="actor"><small>操作人</small>{{actor}}</span>
        <span v-if="action"><small>动作</small>{{action}}</span>
        <span v-if="target"><small>对象</small>{{target}}</span>
      </div>
      <slot name="extra"/>
      <footer v-if="$slots.actions" class="event-actions"><slot name="actions"/></footer>
    </div>
  </article>
</template>
