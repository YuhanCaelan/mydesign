<script setup lang="ts">
import {computed} from 'vue'
import type {Schedule} from '../../services/admin'
import type {Department,DoctorSummary} from '../../types/medical'
import {localDate,monthDays,shiftMonth} from '../../utils/scheduleCalendar'

const props=defineProps<{
  rows:Schedule[];departments:Department[];doctors:DoctorSummary[];isDoctor:boolean
  month:string;selectedDate:string;department?:number;doctor?:number;status:string
  loading:boolean;optionsLoading:boolean;pendingIds:number[];bookingMode?:boolean
}>()
const emit=defineEmits<{
  'update:month':[value:string];'update:selectedDate':[value:string]
  'update:department':[value:number|undefined];'update:doctor':[value:number|undefined]
  'update:status':[value:string];create:[date:string];toggle:[row:Schedule];reserve:[row:Schedule];refresh:[]
}>()
const today=computed(()=>localDate())
const days=computed(()=>monthDays(props.month))
const availableDoctors=computed(()=>props.doctors.filter(item=>!props.department||item.department_id===props.department))
function matchesStatus(row:Schedule){return !props.status||(props.bookingMode?(props.status==='open')===(row.available_slots>0):(props.status==='open')===row.is_active)}
const filtered=computed(()=>props.rows.filter(row=>(!props.department||row.department_id===props.department)&&(!props.doctor||row.doctor===props.doctor)&&matchesStatus(row)).sort((a,b)=>a.start_time.localeCompare(b.start_time)||a.doctor_name.localeCompare(b.doctor_name,'zh-CN')||a.id-b.id))
const byDate=computed(()=>{
  const groups=new Map<string,Schedule[]>()
  for(const row of filtered.value){const group=groups.get(row.date)||[];group.push(row);groups.set(row.date,group)}
  return groups
})
const monthRows=computed(()=>filtered.value.filter(row=>row.date.startsWith(props.month)))
const monthDoctors=computed(()=>new Set(monthRows.value.map(row=>row.doctor)).size)
const dayAvailability=computed(()=>new Map([...byDate.value].map(([day,rows])=>[day,rows.reduce((sum,row)=>sum+row.available_slots,0)])))
const dayRows=computed(()=>byDate.value.get(props.selectedDate)||[])
const selectedLabel=computed(()=>{
  const [year,month,day]=props.selectedDate.split('-').map(Number)
  return `${month}月${day}日 · ${['周日','周一','周二','周三','周四','周五','周六'][new Date(year!,month!-1,day).getDay()]}`
})
function selectDate(value:string){emit('update:selectedDate',value);if(!value.startsWith(props.month))emit('update:month',value.slice(0,7))}
function selectMonth(value:string){if(!value)return;emit('update:month',value);emit('update:selectedDate',value===today.value.slice(0,7)?today.value:`${value}-01`)}
function reset(){emit('update:department',undefined);emit('update:doctor',undefined);emit('update:status','')}
function changeDepartment(value:number|undefined){emit('update:department',value);emit('update:doctor',undefined)}
function disabledMonth(date:Date){return Boolean(props.bookingMode&&localDate(date).slice(0,7)<today.value.slice(0,7))}
</script>

<template>
  <div class="schedule-panel" :aria-busy="loading">
    <div class="schedule-toolbar">
      <div class="schedule-month-nav">
        <el-button aria-label="上个月" :disabled="bookingMode&&month<=today.slice(0,7)" @click="selectMonth(shiftMonth(month,-1))">‹</el-button>
        <el-date-picker :model-value="month" type="month" value-format="YYYY-MM" format="YYYY 年 M 月" :clearable="false" :disabled-date="disabledMonth" aria-label="选择排班月份" @update:model-value="selectMonth"/>
        <el-button aria-label="下个月" @click="selectMonth(shiftMonth(month,1))">›</el-button>
        <el-button @click="selectDate(today)">今天</el-button>
      </div>
      <el-button :loading="loading" @click="emit('refresh')">刷新排班</el-button>
    </div>
    <div class="schedule-filters">
      <template v-if="!isDoctor">
        <el-select :model-value="department" clearable placeholder="全部科室" aria-label="筛选排班科室" @update:model-value="changeDepartment"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id"/></el-select>
        <el-select :model-value="doctor" clearable filterable :loading="optionsLoading" placeholder="全部医师" aria-label="筛选排班医师" @update:model-value="emit('update:doctor',$event||undefined)"><el-option v-for="item in availableDoctors" :key="item.id" :label="`${item.full_name} · ${item.department_name}`" :value="item.id"/></el-select>
      </template>
      <el-select :model-value="status" clearable placeholder="全部状态" aria-label="筛选排班状态" @update:model-value="emit('update:status',$event||'')"><el-option :label="bookingMode?'有余号':'开放'" value="open"/><el-option :label="bookingMode?'无余号':'已关闭'" value="closed"/></el-select>
      <el-button link @click="reset">重置筛选</el-button>
    </div>
    <div class="schedule-summary" aria-live="polite">
      <span>本月 <b>{{monthRows.length}}</b> 个出诊时段</span><span><b>{{monthDoctors}}</b> 位医师</span>
      <span class="schedule-key"><i/>{{bookingMode?'有余号':'开放'}} <i class="closed"/>{{bookingMode?'无余号':'已关闭'}}</span>
    </div>
    <div v-loading="loading" class="schedule-layout">
      <section class="schedule-month" aria-label="月排班日历">
        <div class="schedule-weekdays"><span v-for="day in ['周一','周二','周三','周四','周五','周六','周日']" :key="day">{{day}}</span></div>
        <div class="schedule-grid">
          <button v-for="day in days" :key="day.value" type="button" class="schedule-day" :disabled="bookingMode&&day.value<today" :class="{outside:!day.inMonth,selected:day.value===selectedDate,today:day.value===today}" :aria-pressed="day.value===selectedDate" :aria-current="day.value===today?'date':undefined" :aria-label="`${day.value}，${byDate.get(day.value)?.length||0} 个出诊时段${bookingMode?`，剩余 ${dayAvailability.get(day.value)||0} 个号源`:''}`" @click="selectDate(day.value)">
            <span class="schedule-day-head"><b>{{day.day}}</b><small v-if="day.value===today">今天</small></span>
            <span v-if="byDate.get(day.value)?.length" class="schedule-day-count">{{bookingMode?`${dayAvailability.get(day.value)||0} 个余号`:`${byDate.get(day.value)!.length} 个时段`}}</span>
            <span class="schedule-day-previews">
              <span v-for="row in (byDate.get(day.value)||[]).slice(0,2)" :key="row.id" class="schedule-preview" :class="{closed:bookingMode?row.available_slots===0:!row.is_active}"><strong>{{row.doctor_name}}</strong><span>{{row.time_range}}</span></span>
              <small v-if="(byDate.get(day.value)?.length||0)>2">另有 {{byDate.get(day.value)!.length-2}} 条</small>
            </span>
          </button>
        </div>
        <p class="schedule-hint">{{bookingMode?'选择日期，查看出诊医师与剩余号源；灰色时段暂无可预约号源。':'点击日期查看出诊安排；灰色时段为已关闭排班。'}}</p>
      </section>
      <aside class="schedule-agenda" aria-label="当日排班详情">
        <header class="schedule-agenda-head"><span class="schedule-caption">当日安排</span><h2>{{selectedLabel}}</h2><p>{{dayRows.length}} 个出诊时段 <span v-if="selectedDate<today">· 历史排班仅供查看</span></p>
          <el-button v-if="!bookingMode&&selectedDate>=today" type="primary" :disabled="loading||optionsLoading" @click="emit('create',selectedDate)">＋ 为此日新建排班</el-button>
        </header>
        <div class="schedule-agenda-list" aria-live="polite">
          <article v-for="row in dayRows" :key="row.id" class="schedule-event" :class="{closed:bookingMode?row.available_slots===0:!row.is_active}">
            <div class="schedule-event-top"><b>{{row.time_range}}</b><el-tag size="small" :type="(bookingMode?row.available_slots>0:row.is_active)?'success':'info'">{{bookingMode?(row.available_slots>0?'可预约':'无余号'):(row.is_active?'开放':'已关闭')}}</el-tag></div>
            <h3>{{row.doctor_name}} <small>{{row.doctor_title||'医师'}}</small></h3><p>{{row.department_name}}</p>
            <div class="schedule-event-slots"><span>总号源 <b>{{row.total_slots}}</b></span><span>{{row.is_active?'剩余可预约':'剩余号源'}} <b>{{row.available_slots}}</b></span></div>
            <footer><span>每号 {{row.slot_minutes}} 分钟</span><el-button v-if="bookingMode" type="primary" size="small" :disabled="loading||row.available_slots===0||row.date<today" @click="emit('reserve',row)">选择号源</el-button><el-button v-else-if="row.date>=today" link :loading="pendingIds.includes(row.id)" :disabled="loading" @click="emit('toggle',row)">{{row.is_active?'关闭排班':'开放排班'}}</el-button><small v-else>历史排班</small></footer>
            <small v-if="!row.is_active" class="schedule-closed-note">已关闭，剩余号源暂不可预约</small>
          </article>
          <el-empty v-if="!dayRows.length&&!loading" :image-size="72" description="当日暂无符合条件的排班"/>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.schedule-panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px;min-width:0}
.schedule-day:disabled{cursor:default;opacity:.45;background:var(--surface-soft)}
.schedule-toolbar,.schedule-month-nav,.schedule-filters,.schedule-summary{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.schedule-toolbar{justify-content:space-between}.schedule-month-nav{gap:8px}.schedule-month-nav :deep(.el-date-editor){width:184px}.schedule-month-nav :deep(.el-button+.el-button){margin-left:0}
.schedule-filters{padding:20px 0 16px}.schedule-filters .el-select{width:180px}.schedule-filters .el-select:nth-child(2){width:210px}
.schedule-summary{padding:14px 0;border-top:1px solid var(--line-soft);font-size:13px;color:var(--muted)}.schedule-summary b{color:var(--blue-deep);font-size:17px}.schedule-key{display:flex;align-items:center;gap:7px;margin-left:auto}.schedule-key i{width:8px;height:8px;border-radius:50%;background:var(--teal)}.schedule-key i.closed{background:#929b97;margin-left:10px}
.schedule-layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:22px;align-items:start}.schedule-month{min-width:0}.schedule-weekdays,.schedule-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}.schedule-weekdays{background:var(--surface-soft);border:1px solid var(--line);border-bottom:0;border-radius:10px 10px 0 0}.schedule-weekdays span{text-align:center;padding:12px 0;color:var(--muted);font-size:12px}.schedule-weekdays span:nth-last-child(-n+2){color:var(--amber)}
.schedule-grid{gap:1px;background:var(--line);border:1px solid var(--line);border-radius:0 0 10px 10px;overflow:hidden}.schedule-day{appearance:none;border:0;background:var(--surface);padding:9px 7px;text-align:left;cursor:pointer;min-width:0;min-height:150px;position:relative;display:flex;flex-direction:column;gap:4px;transition:background .15s}.schedule-day:hover{background:#f1f7f3}.schedule-day.selected{background:#eaf4ee;box-shadow:inset 0 0 0 2px var(--teal)}.schedule-day:focus-visible{outline-offset:-3px;z-index:1}.schedule-day.outside{background:var(--surface-soft);color:var(--muted)}.schedule-day.outside .schedule-day-previews{opacity:.65}.schedule-day-head{display:flex;align-items:center;justify-content:space-between;gap:2px}.schedule-day-head b{font-family:var(--number);font-size:20px;line-height:26px;font-weight:500}.schedule-day.today .schedule-day-head b{background:var(--teal);color:#fff;border-radius:50%;width:26px;text-align:center}.schedule-day-head small{font-size:10px;color:var(--teal)}.schedule-day-count{font-size:10px;color:var(--muted)}.schedule-day-previews{display:flex;flex-direction:column;gap:4px;width:100%;margin-top:3px}.schedule-preview{display:flex;flex-direction:column;gap:2px;padding:4px 5px;background:#e5f0e9;color:var(--blue-deep);border-left:2px solid var(--teal);border-radius:3px;font-size:10px;overflow:hidden}.schedule-preview strong{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}.schedule-preview span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.schedule-preview.closed{background:#eeefec;color:#737d78;border-color:#a4ada7}.schedule-day-previews>small{font-size:10px;color:var(--muted);padding-left:3px}.schedule-hint{font-size:12px;color:var(--muted);margin:12px 0 0}
.schedule-agenda{background:var(--surface-soft);border:1px solid var(--line-soft);border-radius:10px;overflow:hidden}.schedule-agenda-head{padding:20px;border-bottom:1px solid var(--line)}.schedule-caption{font-size:11px;letter-spacing:.12em;color:var(--teal)}.schedule-agenda-head h2{font-size:21px;color:var(--blue-deep);margin:8px 0}.schedule-agenda-head p{color:var(--muted);font-size:12px;margin:0 0 16px}.schedule-agenda-head p span{display:inline-block}.schedule-agenda-list{display:flex;flex-direction:column;gap:12px;padding:14px;max-height:760px;overflow-y:auto}.schedule-event{background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--teal);border-radius:8px;padding:14px}.schedule-event.closed{border-top-color:#a4ada7}.schedule-event-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.schedule-event-top>b{font-family:var(--number);font-size:19px;font-weight:500;color:var(--blue-deep)}.schedule-event h3{margin:13px 0 5px;font-size:16px}.schedule-event h3 small{font-size:11px;color:var(--muted);font-weight:400}.schedule-event>p{font-size:12px;color:var(--muted);margin:0 0 14px}.schedule-event-slots{display:flex;gap:18px;font-size:11px;color:var(--muted);background:var(--surface-soft);padding:10px;border-radius:6px}.schedule-event-slots b{font-family:var(--number);font-size:18px;color:var(--blue-deep);margin-left:4px}.schedule-event footer{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;font-size:11px;color:var(--muted);min-height:28px}.schedule-closed-note{display:block;font-size:11px;color:var(--muted);border-top:1px solid var(--line-soft);padding-top:8px;margin-top:6px}
@media(min-width:1500px){.schedule-layout{grid-template-columns:minmax(0,1fr) 340px}.schedule-preview{font-size:11px}}
@media(max-width:1150px){.schedule-layout{grid-template-columns:minmax(0,1fr)}.schedule-agenda-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));max-height:none}.schedule-agenda-head .el-button{margin-top:0}.schedule-agenda-list>.el-empty{grid-column:1/-1}}
@media(max-width:600px){.schedule-panel{padding:12px}.schedule-toolbar{gap:12px}.schedule-month-nav{gap:4px}.schedule-month-nav :deep(.el-date-editor){width:156px}.schedule-month-nav :deep(.el-button){padding:8px 12px}.schedule-filters{gap:8px}.schedule-filters .el-select,.schedule-filters .el-select:nth-child(2){width:calc(50% - 4px)}.schedule-summary{gap:8px;font-size:11px}.schedule-summary b{font-size:15px}.schedule-key{width:100%;margin-left:0}.schedule-day{min-height:72px;padding:6px 4px}.schedule-day-head b{font-size:18px}.schedule-day-head small{font-size:9px}.schedule-day-previews{display:none}.schedule-day-count{font-size:9px}.schedule-weekdays span{font-size:11px}.schedule-agenda-list{grid-template-columns:minmax(0,1fr)}.schedule-agenda-head{padding:16px}}
@media(max-width:600px){.schedule-day-head small{display:none}}
</style>
