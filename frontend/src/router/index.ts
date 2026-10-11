import {createRouter,createWebHistory,type RouteRecordRaw} from 'vue-router'
import {useAuthStore,type UserRole} from '../stores/auth'

const pages=import.meta.glob('../views/**/*.vue')
const view=(name:string)=>pages[`../views/${name}.vue`]
const route=(path:string,name:string,component:string,roles:UserRole[]):RouteRecordRaw=>({path,name,component:view(component),meta:{roles}})

const routes:RouteRecordRaw[]=[
  {path:'/login',name:'login',component:view('auth/Login')},
  {path:'/register',name:'register',component:view('auth/Register')},
  {path:'/',component:view('layouts/AppLayout'),children:[
    {path:'',redirect:'/dashboard'},
    route('/dashboard','dashboard','shared/Dashboard',['admin','doctor','patient']),
    route('/console/users','admin-users','admin/Users',['admin']),
    route('/console/departments','admin-departments','admin/Departments',['admin']),
    route('/console/doctors','admin-doctors','shared/PeopleDirectory',['admin']),
    route('/console/patients','admin-patients','shared/PeopleDirectory',['admin']),
    route('/console/schedules','admin-schedules','admin/Schedules',['admin']),
    route('/console/appointments','admin-appointments','shared/Appointments',['admin']),
    route('/console/examinations','admin-examinations','shared/Examinations',['admin']),
    route('/console/resources','admin-resources','admin/ClinicalResources',['admin']),
    route('/console/inpatients','admin-inpatients','shared/Inpatients',['admin']),
    route('/console/billing','admin-billing','shared/Billing',['admin']),
    route('/console/medicines','admin-medicines','shared/Medicines',['admin']),
    route('/console/statistics','admin-statistics','admin/Statistics',['admin']),
    route('/console/audit-logs','admin-audit','admin/AuditLogs',['admin']),
    route('/doctor/schedule','doctor-schedule','admin/Schedules',['doctor']),
    route('/doctor/appointments','doctor-appointments','shared/Appointments',['doctor']),
    route('/doctor/visits/:appointmentId','doctor-visit-workspace','doctor/VisitWorkspace',['doctor']),
    route('/doctor/patients','doctor-patients','shared/PeopleDirectory',['doctor']),
    route('/doctor/records','doctor-records','shared/Records',['doctor']),
    route('/doctor/prescriptions','doctor-prescriptions','shared/Prescriptions',['doctor']),
    route('/doctor/examinations','doctor-examinations','shared/Examinations',['doctor']),
    route('/doctor/inpatients','doctor-inpatients','shared/Inpatients',['doctor']),
    route('/doctor/medicines','doctor-medicines','shared/Medicines',['doctor']),
    route('/patient/doctors','patient-doctors','shared/PeopleDirectory',['patient']),
    route('/patient/appointments','patient-appointments','shared/Appointments',['patient']),
    route('/patient/records','patient-records','shared/Records',['patient']),
    route('/patient/prescriptions','patient-prescriptions','shared/Prescriptions',['patient']),
    route('/patient/reports','patient-reports','shared/Examinations',['patient']),
    route('/patient/inpatients','patient-inpatients','shared/Inpatients',['patient']),
    route('/patient/billing','patient-billing','shared/Billing',['patient']),
    route('/smart/services','smart-services','smart/Services',['admin','doctor','patient']),
    route('/profile','profile','shared/Profile',['admin','doctor','patient']),
  ]},
  {path:'/:pathMatch(.*)*',redirect:'/dashboard'},
]

const router=createRouter({history:createWebHistory(import.meta.env.BASE_URL),routes})
router.beforeEach(to=>{
  const auth=useAuthStore()
  if(to.name==='login'||to.name==='register')return auth.user?'/dashboard':true
  if(!auth.user)return{name:'login',query:{redirect:to.fullPath}}
  const roles=to.meta.roles as UserRole[]|undefined
  return roles&&!roles.includes(auth.user.role)?'/dashboard':true
})
export default router
