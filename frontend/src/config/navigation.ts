import {Calendar,DataAnalysis,Document,FirstAidKit,House,OfficeBuilding,Setting,User,UserFilled} from '@element-plus/icons-vue'
import type {UserRole} from '../stores/auth'

export interface NavItem{label:string;path:string;icon:unknown}
export interface NavGroup{label:string;items:NavItem[]}
const common:NavGroup[]=[{label:'概览',items:[{label:'工作台',path:'/dashboard',icon:House}]}]
const roleMenus:Record<UserRole,NavGroup[]>={
  admin:[
    {label:'基础管理',items:[{label:'用户账户',path:'/console/users',icon:User},{label:'科室管理',path:'/console/departments',icon:OfficeBuilding},{label:'医师管理',path:'/console/doctors',icon:FirstAidKit},{label:'患者管理',path:'/console/patients',icon:UserFilled},{label:'排班管理',path:'/console/schedules',icon:Calendar}]},
    {label:'医疗业务',items:[{label:'预约管理',path:'/console/appointments',icon:Calendar},{label:'住院管理',path:'/console/inpatients',icon:OfficeBuilding},{label:'检查管理',path:'/console/examinations',icon:Document},{label:'床位与项目',path:'/console/resources',icon:Setting},{label:'费用结算',path:'/console/billing',icon:Document},{label:'药品管理',path:'/console/medicines',icon:FirstAidKit},{label:'数据统计',path:'/console/statistics',icon:DataAnalysis},{label:'操作审计',path:'/console/audit-logs',icon:Setting}]},
  ],
  doctor:[{label:'诊疗工作',items:[{label:'我的排班',path:'/doctor/schedule',icon:Calendar},{label:'接诊管理',path:'/doctor/appointments',icon:FirstAidKit},{label:'我的患者',path:'/doctor/patients',icon:UserFilled},{label:'电子病历',path:'/doctor/records',icon:Document},{label:'电子处方',path:'/doctor/prescriptions',icon:Document},{label:'医学检查',path:'/doctor/examinations',icon:DataAnalysis},{label:'住院管理',path:'/doctor/inpatients',icon:OfficeBuilding},{label:'药品目录',path:'/doctor/medicines',icon:FirstAidKit}]}],
  patient:[{label:'个人医疗',items:[{label:'医师查询',path:'/patient/doctors',icon:FirstAidKit},{label:'预约挂号',path:'/patient/appointments',icon:Calendar},{label:'我的病历',path:'/patient/records',icon:Document},{label:'我的处方',path:'/patient/prescriptions',icon:Document},{label:'检查报告',path:'/patient/reports',icon:DataAnalysis},{label:'住院记录',path:'/patient/inpatients',icon:OfficeBuilding},{label:'费用账单',path:'/patient/billing',icon:Document}]}],
}
export const navigationFor=(role:UserRole):NavGroup[]=>[...common,...roleMenus[role],{label:'智慧医疗',items:[{label:'智慧服务中心',path:'/smart/services',icon:DataAnalysis}]}]
