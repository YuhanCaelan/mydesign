import {defineStore} from 'pinia'
import api from '../services/api'

export type UserRole = 'admin' | 'doctor' | 'patient'
export interface SessionUser {id:number;username:string;full_name:string;role:UserRole;avatar?:string|null}

function storedUser(): SessionUser | null {
  try { return JSON.parse(localStorage.getItem('smart_medical_user') || 'null') }
  catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({user: storedUser(), ready: false}),
  getters: {isAuthenticated: (state) => Boolean(state.user)},
  actions: {
    async login(username:string,password:string) {
      const {data}=await api.post('auth/login/',{username,password})
      const access=data.access||data.token
      if(!access||!data.user) throw new Error('登录响应格式无效')
      localStorage.setItem('smart_medical_access',access)
      if(data.refresh)localStorage.setItem('smart_medical_refresh',data.refresh)
      localStorage.setItem('smart_medical_user',JSON.stringify(data.user))
      this.user=data.user
    },
    async refresh() {
      if(!localStorage.getItem('smart_medical_access')){this.user=null;this.ready=true;return}
      try{const {data}=await api.get('auth/me/');this.user=data;localStorage.setItem('smart_medical_user',JSON.stringify(data))}
      catch{this.logout()}
      finally{this.ready=true}
    },
    logout(){localStorage.removeItem('smart_medical_access');localStorage.removeItem('smart_medical_refresh');localStorage.removeItem('smart_medical_user');this.user=null},
  },
})
