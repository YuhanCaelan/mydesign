import {createRouter,createWebHistory} from 'vue-router'
import {useAuthStore} from '../stores/auth'
const router=createRouter({history:createWebHistory(),routes:[
  {path:'/login',component:()=>import('../views/Login.vue')},
  {path:'/',component:()=>import('../views/Layout.vue'),children:[
    {path:'',redirect:'/dashboard'},{path:'dashboard',component:()=>import('../views/Dashboard.vue')},
    {path:'departments',component:()=>import('../views/Departments.vue'),meta:{roles:['admin']}},
    {path:'schedules',component:()=>import('../views/Schedules.vue')},
    {path:'appointments',component:()=>import('../views/Appointments.vue')},
  ]},{path:'/:pathMatch(.*)*',redirect:'/dashboard'}]})
router.beforeEach(to=>{const auth=useAuthStore();if(to.path==='/login')return auth.user?'/dashboard':true;if(!auth.user)return'/login';const roles=to.meta.roles as string[]|undefined;return roles&&!roles.includes(auth.user.role)?'/dashboard':true})
export default router
