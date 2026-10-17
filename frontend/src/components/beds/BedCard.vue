<script setup lang="ts">
import {computed} from 'vue'
import type {BoardBed} from '../../types/medical'

const props=defineProps<{bed:BoardBed;current?:boolean}>()
const emit=defineEmits<{(event:'open',bed:BoardBed):void}>()
const occupancy=computed(()=>props.bed.occupancy)
function money(value?:string|null){return value===null||value===undefined?'—':`¥${Number(value).toFixed(2)}`}
function shortTime(value?:string|null){return value?value.replace('T',' ').slice(0,16):'—'}
function activate(){emit('open',props.bed)}
</script>

<template>
  <article
    class="bed-card"
    :data-status="bed.status"
    :data-bed="bed.bed_no"
    :data-ward="bed.ward_name"
    :data-current="current?'true':'false'"
    tabindex="0"
    role="button"
    :aria-label="`${bed.department_name}${bed.ward_name}${bed.bed_no} ${bed.status_label}`"
    @click="activate"
    @keyup.enter="activate"
    @keyup.space.prevent="activate">
    <header class="bed-card-head">
      <b class="bed-card-no">{{bed.bed_no}}</b>
      <span class="bed-card-status">{{bed.status_label}}</span>
    </header>
    <p class="bed-card-location">{{bed.department_name}} · {{bed.ward_name}}</p>
    <template v-if="bed.status==='occupied'">
      <div v-if="occupancy" class="bed-card-body">
        <strong class="bed-card-patient">{{occupancy.patient_name}}</strong>
        <span class="bed-card-line">患者编号 {{occupancy.patient_no}}</span>
        <span class="bed-card-line">住院号 {{occupancy.admission_no}}</span>
        <span class="bed-card-line">主治医师 {{occupancy.doctor_name}}</span>
      </div>
      <footer v-if="occupancy" class="bed-card-foot">
        <span>入院 {{shortTime(occupancy.admitted_at)}}</span>
        <b>已住 {{occupancy.days_admitted}} 天</b>
      </footer>
      <footer v-else class="bed-card-foot warning"><span>缺少住院记录，请核对床位占用状态</span></footer>
    </template>
    <template v-else-if="bed.status==='inactive'">
      <div class="bed-card-body muted"><span class="bed-card-line">该床位已停用，不参与收治</span></div>
      <footer class="bed-card-foot"><span>日费 {{money(bed.daily_rate)}}</span></footer>
    </template>
    <template v-else>
      <div class="bed-card-body"><span class="bed-card-line">可安排入院</span></div>
      <footer class="bed-card-foot"><span>日费</span><b>{{money(bed.daily_rate)}} / 日</b></footer>
    </template>
  </article>
</template>
