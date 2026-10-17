import {createRouter,createWebHistory,type LocationQueryRaw,type RouteRecordRaw} from 'vue-router'
import {useAuthStore,type UserRole} from '../stores/auth'

const pages=import.meta.glob('../views/**/*.vue')
const view=(name:string)=>pages[`../views/${name}.vue`]
const route=(path:string,name:string,component:string,roles:UserRole[],meta:Record<string,unknown>={}):RouteRecordRaw=>({path,name,component:view(component),meta:{roles,...meta}})

const legacyRoutes:Record<string,{path:string;tab?:string}>={
  '/console/users':{path:'/console/people',tab:'doctors'},
  '/console/doctors':{path:'/console/people',tab:'doctors'},
  '/console/patients':{path:'/console/people',tab:'patients'},
  '/console/departments':{path:'/console/people',tab:'departments'},
  '/console/schedules':{path:'/console/outpatient',tab:'schedules'},
  '/console/appointments':{path:'/console/outpatient',tab:'appointments'},
  '/console/examinations':{path:'/console/clinical',tab:'examinations'},
  '/console/medicines':{path:'/console/clinical',tab:'medicines'},
  '/console/bed-board':{path:'/console/inpatient',tab:'beds'},
  '/console/inpatients':{path:'/console/inpatient',tab:'admissions'},
  '/console/billing':{path:'/console/operations',tab:'bills'},
  '/console/statistics':{path:'/console/operations',tab:'statistics'},
  '/console/audit-logs':{path:'/console/operations',tab:'audit'},
  '/doctor/schedule':{path:'/doctor/outpatient',tab:'schedule'},
  '/doctor/appointments':{path:'/doctor/outpatient',tab:'appointments'},
  '/doctor/patients':{path:'/doctor/outpatient',tab:'patients'},
  '/doctor/prescriptions':{path:'/doctor/clinical',tab:'prescriptions'},
  '/doctor/examinations':{path:'/doctor/clinical',tab:'examinations'},
  '/doctor/medicines':{path:'/doctor/clinical',tab:'medicines'},
  '/doctor/bed-board':{path:'/doctor/inpatient',tab:'beds'},
  '/doctor/inpatients':{path:'/doctor/inpatient',tab:'admissions'},
  '/patient/doctors':{path:'/patient/visits',tab:'doctors'},
  '/patient/appointments':{path:'/patient/visits',tab:'appointments'},
  '/patient/prescriptions':{path:'/patient/care',tab:'prescriptions'},
  '/patient/inpatients':{path:'/patient/care',tab:'admissions'},
  '/patient/billing':{path:'/patient/finance',tab:'bills'},
}

function legacyRedirect(path:string,query:LocationQueryRaw):{path:string;query:LocationQueryRaw}|null{
  if(path==='/patient/care'){
    const tab=typeof query.tab==='string'?query.tab:''
    if(tab==='records'||tab==='reports')return{path:'/patient/records',query:{...query,tab}}
  }
  if(path==='/console/resources'){
    const oldTab=typeof query.tab==='string'?query.tab:'beds'
    const target=oldTab==='exams'?{path:'/console/clinical',tab:'exam-items'}:oldTab==='movements'?{path:'/console/clinical',tab:'stock'}:{path:'/console/inpatient',tab:'bed-config'}
    return{path:target.path,query:{...query,tab:target.tab}}
  }
  const legacy=legacyRoutes[path]
  if(!legacy)return null
  return{path:legacy.path,query:{...query,...(legacy.tab?{tab:legacy.tab}:{})}}
}

const legacyRouteRecords:RouteRecordRaw[]=Object.entries(legacyRoutes).map(([path,legacy])=>({
  path,
  redirect:to=>({path:legacy.path,query:{...to.query,...(legacy.tab?{tab:legacy.tab}:{})}}),
}))
legacyRouteRecords.push(
  {path:'/console/resources',redirect:to=>legacyRedirect('/console/resources',to.query)||'/dashboard'},
  {path:'/patient/reports',redirect:to=>({path:'/patient/records',query:{...to.query,tab:'reports'}})},
  {path:'/doctor/reports',redirect:to=>({path:'/doctor/records',query:{...to.query,tab:'reports'}})},
  {path:'/smart/services',redirect:to=>{
    const auth=useAuthStore(),role=auth.user?.role
    const target=role==='admin'?{path:'/console/clinical',tab:'smart'}:role==='doctor'?{path:'/doctor/clinical',tab:'smart'}:{path:'/patient/care',tab:'smart'}
    return{path:target.path,query:{...to.query,tab:target.tab}}
  }},
)

const routes:RouteRecordRaw[]=[
  {path:'/login',name:'login',component:view('auth/Login')},
  {path:'/register',name:'register',component:view('auth/Register')},
  {path:'/',component:view('layouts/AppLayout'),children:[
    {path:'',redirect:'/dashboard'},
    route('/dashboard','dashboard','shared/Dashboard',['admin','doctor','patient']),
    // 管理员主栏目
    route('/console/people','admin-people','admin/People',['admin']),
    route('/console/outpatient','admin-outpatient','admin/Outpatient',['admin']),
    route('/console/clinical','admin-clinical','admin/Clinical',['admin']),
    route('/console/inpatient','admin-inpatient','admin/Inpatient',['admin']),
    route('/console/operations','admin-operations','admin/Operations',['admin']),
    route('/console/inpatients/:admissionId','admin-inpatient-detail','shared/AdmissionDetail',['admin'],{activePath:'/console/inpatient'}),
    // 医师主栏目
    route('/doctor/outpatient','doctor-outpatient','doctor/Outpatient',['doctor']),
    route('/doctor/records','doctor-records','shared/Archive',['doctor']),
    route('/doctor/clinical','doctor-clinical','doctor/Clinical',['doctor']),
    route('/doctor/inpatient','doctor-inpatient','doctor/Inpatient',['doctor']),
    route('/doctor/visits/:appointmentId','doctor-visit-workspace','doctor/VisitWorkspace',['doctor'],{activePath:'/doctor/outpatient'}),
    route('/doctor/inpatients/:admissionId','doctor-inpatient-detail','shared/AdmissionDetail',['doctor'],{activePath:'/doctor/inpatient'}),
    // 患者主栏目
    route('/patient/visits','patient-visits','patient/Visits',['patient']),
    route('/patient/records','patient-records','shared/Archive',['patient']),
    route('/patient/care','patient-care','patient/Care',['patient']),
    route('/patient/finance','patient-finance','patient/Finance',['patient']),
    route('/patient/inpatients/:admissionId','patient-inpatient-detail','shared/AdmissionDetail',['patient'],{activePath:'/patient/care'}),
    route('/profile','profile','shared/Profile',['admin','doctor','patient']),
  ]},
  ...legacyRouteRecords,
  {path:'/:pathMatch(.*)*',redirect:'/dashboard'},
]

const router=createRouter({history:createWebHistory(import.meta.env.BASE_URL),routes})
router.beforeEach(to=>{
  const auth=useAuthStore()
  if(to.name==='login'||to.name==='register')return auth.user?'/dashboard':true
  if(!auth.user)return{name:'login',query:{redirect:to.fullPath}}
  const legacy=legacyRedirect(to.path,to.query)
  if(legacy)return{path:legacy.path,query:legacy.query,replace:true}
  const roles=to.meta.roles as UserRole[]|undefined
  return roles&&!roles.includes(auth.user.role)?'/dashboard':true
})
router.afterEach(to=>{
  document.title=typeof to.meta.title==='string'?`${to.meta.title} · 慧医云`:'慧医云'
})
export default router
