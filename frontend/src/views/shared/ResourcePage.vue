<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import api from '../../services/api'

interface Definition{title:string;description:string;endpoint:string;action?:string;columns:[string,string][]}
const definitions:Record<string,Definition>={
  'admin-users':{title:'用户账户',description:'创建账户、启停账号并分配三类业务角色',endpoint:'users/',action:'创建账户',columns:[['username','用户名'],['full_name','姓名'],['role_display','角色'],['is_active_display','状态']]},
  'admin-departments':{title:'科室管理',description:'维护医院科室及对外介绍',endpoint:'departments/',action:'新增科室',columns:[['name','科室名称'],['description','科室介绍'],['status_display','状态']]},
  'admin-doctors':{title:'医师管理',description:'管理医师档案、职称与专业方向',endpoint:'doctors/',action:'新增医师',columns:[['doctor_no','医师编号'],['full_name','姓名'],['department_name','科室'],['title','职称']]},
  'admin-patients':{title:'患者管理',description:'查询患者基础档案与账户状态',endpoint:'patients/',columns:[['patient_no','患者编号'],['full_name','姓名'],['gender_display','性别'],['phone','联系电话']]},
  'admin-schedules':{title:'排班管理',description:'设置医师出诊时间与预约号源',endpoint:'schedules/',action:'新建排班',columns:[['doctor_name','医师'],['date','日期'],['time_range','出诊时间'],['available_slots','剩余号源']]},
  'admin-appointments':{title:'预约管理',description:'查看并处理全院预约记录',endpoint:'appointments/',columns:[['appointment_no','预约编号'],['patient_name','患者'],['doctor_name','医师'],['appointment_time','就诊时间'],['status_display','状态']]},
  'admin-examinations':{title:'检查管理',description:'审计检查申请、报告和医学文件',endpoint:'examinations/',columns:[['order_no','申请单号'],['patient_name','患者'],['type_display','检查类型'],['status_display','状态']]},
  'admin-audit':{title:'操作审计',description:'追踪关键操作与敏感医疗数据访问',endpoint:'audit-logs/',columns:[['created_at','时间'],['user_name','操作人'],['action_display','操作'],['resource','资源']]},
  'doctor-schedule':{title:'我的排班',description:'查看个人出诊时间与号源安排',endpoint:'schedules/',columns:[['date','日期'],['time_range','出诊时间'],['total_slots','号源'],['available_slots','剩余']]},
  'doctor-appointments':{title:'接诊管理',description:'按预约状态推进患者诊疗流程',endpoint:'appointments/',columns:[['appointment_time','就诊时间'],['patient_name','患者'],['reason','就诊原因'],['status_display','状态']]},
  'doctor-patients':{title:'我的患者',description:'仅展示与当前医师存在诊疗关系的患者',endpoint:'patients/',columns:[['patient_no','患者编号'],['full_name','姓名'],['last_visit_at','最近就诊'],['appointment_count','就诊次数']]},
  'doctor-records':{title:'电子病历',description:'创建、确认并追溯患者诊疗记录',endpoint:'medical-records/',action:'创建病历',columns:[['record_no','病历编号'],['patient_name','患者'],['diagnosis','诊断'],['status_display','状态'],['updated_at','更新时间']]},
  'doctor-prescriptions':{title:'电子处方',description:'开具药品处方并查看历史处方',endpoint:'prescriptions/',action:'开具处方',columns:[['prescription_no','处方编号'],['patient_name','患者'],['item_count','药品数'],['status_display','状态']]},
  'doctor-examinations':{title:'医学检查',description:'创建检查申请并查看已发布报告',endpoint:'examinations/',action:'申请检查',columns:[['order_no','申请单号'],['patient_name','患者'],['type_display','类型'],['status_display','状态']]},
  'patient-doctors':{title:'医师查询',description:'按科室查找医师并了解其专业方向',endpoint:'doctors/',columns:[['full_name','医师姓名'],['department_name','科室'],['title','职称'],['specialty','专业方向']]},
  'patient-appointments':{title:'预约挂号',description:'选择科室、医师和可预约号源',endpoint:'appointments/',action:'预约挂号',columns:[['appointment_no','预约编号'],['doctor_name','医师'],['appointment_time','就诊时间'],['status_display','状态']]},
  'patient-records':{title:'我的病历',description:'查看已经医师确认的个人就诊记录',endpoint:'medical-records/',columns:[['visit_at','就诊时间'],['doctor_name','医师'],['diagnosis','诊断'],['treatment','治疗建议']]},
  'patient-prescriptions':{title:'我的处方',description:'查阅个人历史处方及用药说明',endpoint:'prescriptions/',columns:[['created_at','开具时间'],['doctor_name','医师'],['item_summary','处方内容'],['status_display','状态']]},
  'patient-reports':{title:'检查报告',description:'查看已经发布的个人检查结果',endpoint:'examinations/',columns:[['completed_at','报告时间'],['type_display','检查类型'],['conclusion','结论'],['status_display','状态']]},
}
const route=useRoute(),rows=ref<any[]>([]),loading=ref(false),keyword=ref(''),total=ref(0),page=ref(1)
const definition=computed(()=>definitions[String(route.name)]||definitions['admin-users'])
async function load(){loading.value=true;try{const {data}=await api.get(definition.value.endpoint,{params:{page:page.value,search:keyword.value}});rows.value=Array.isArray(data)?data:data.results||[];total.value=data.count??rows.value.length}catch{rows.value=[];total.value=0}finally{loading.value=false}}
watch(()=>route.name,()=>{page.value=1;keyword.value='';load()})
onMounted(load)
</script>
<template><section><div class="page-heading"><div><p class="eyebrow">CORE MEDICAL SERVICE</p><h1>{{definition.title}}</h1><p>{{definition.description}}</p></div><el-button v-if="definition.action" type="primary">＋ {{definition.action}}</el-button></div><el-card class="table-card"><div class="table-tools"><el-input v-model="keyword" clearable placeholder="搜索关键词" @keyup.enter="load"/><el-button @click="load">查询</el-button></div><el-table v-loading="loading" :data="rows" empty-text="暂无数据"><el-table-column v-for="column in definition.columns" :key="column[0]" :prop="column[0]" :label="column[1]" min-width="130" show-overflow-tooltip/><el-table-column label="操作" width="110" fixed="right"><el-button link type="primary">查看</el-button></el-table-column></el-table><div class="pagination"><span>共 {{total}} 条</span><el-pagination v-model:current-page="page" layout="prev,pager,next" :total="total" @change="load"/></div></el-card></section></template>
