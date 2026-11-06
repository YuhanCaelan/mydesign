import {defineStore} from 'pinia'
import http from '../api/http'
export interface UserInfo{id:number;username:string;full_name:string;role:'admin'|'doctor'|'patient';phone?:string}
export const useAuthStore=defineStore('auth',{
  state:()=>({user:JSON.parse(localStorage.getItem('course_user')||'null') as UserInfo|null}),
  actions:{async login(username:string,password:string){const {data}=await http.post('/auth/login',{username,password});localStorage.setItem('course_token',data.access_token);localStorage.setItem('course_user',JSON.stringify(data.user));this.user=data.user},logout(){localStorage.clear();this.user=null}}
})
