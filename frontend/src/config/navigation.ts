import {Calendar,DataAnalysis,Document,FirstAidKit,House,Money,OfficeBuilding,Reading,User} from '@element-plus/icons-vue'
import type {UserRole} from '../stores/auth'

export interface NavItem{label:string;path:string;icon:unknown}
export interface NavGroup{label:string;items:NavItem[]}
const common:NavGroup[]=[{label:'概览',items:[{label:'工作台',path:'/dashboard',icon:House}]}]

const roleMenus:Record<UserRole,NavGroup[]>={
  admin:[
    {label:'业务管理',items:[
      {label:'人员与科室',path:'/console/people',icon:User},
      {label:'门诊管理',path:'/console/outpatient',icon:Calendar},
      {label:'医疗资源',path:'/console/clinical',icon:FirstAidKit},
      {label:'住院管理',path:'/console/inpatient',icon:OfficeBuilding},
      {label:'运营管理',path:'/console/operations',icon:DataAnalysis},
    ]},
  ],
  doctor:[
    {label:'诊疗工作',items:[
      {label:'门诊工作',path:'/doctor/outpatient',icon:Calendar},
      {label:'诊疗资料',path:'/doctor/clinical',icon:Document},
      {label:'住院工作',path:'/doctor/inpatient',icon:OfficeBuilding},
    ]},
  ],
  patient:[
    {label:'个人医疗',items:[
      {label:'预约就诊',path:'/patient/visits',icon:Calendar},
      {label:'我的医疗',path:'/patient/care',icon:Reading},
      {label:'我的费用',path:'/patient/finance',icon:Money},
    ]},
  ],
}
export const navigationFor=(role:UserRole):NavGroup[]=>[...common,...roleMenus[role]]
