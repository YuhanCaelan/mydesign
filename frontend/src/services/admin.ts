import api from './api'
import type{Department,DoctorSummary,PageResult}from'../types/medical'
export interface ManagedUser{id:number;username:string;full_name:string;role:'doctor'|'patient';role_display:string;phone:string;email:string;is_active:boolean;is_active_display:string;doctor_no?:string;department_name?:string;created_at:string}
export interface Schedule{id:number;doctor:number;doctor_name:string;date:string;start_time:string;end_time:string;time_range:string;slot_minutes:number;is_active:boolean;total_slots:number;available_slots:number}
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getUsers(params:Record<string,unknown>={}){return unpack((await api.get<ManagedUser[]|PageResult<ManagedUser>>('users/',{params})).data)}
export async function createUser(payload:Record<string,unknown>){return(await api.post<ManagedUser>('users/',payload)).data}
export async function updateUser(id:number,payload:Record<string,unknown>){return(await api.patch<ManagedUser>(`users/${id}/`,payload)).data}
export async function getDepartmentsAdmin(){return unpack((await api.get<Department[]|PageResult<Department>>('departments/')).data)}
export async function createDepartment(payload:{name:string;description:string}){return(await api.post<Department>('departments/',payload)).data}
export async function updateDepartment(id:number,payload:Partial<Department>){return(await api.patch<Department>(`departments/${id}/`,payload)).data}
export async function getDoctorsAdmin(){return unpack((await api.get<DoctorSummary[]|PageResult<DoctorSummary>>('doctors/')).data).results}
export async function getSchedules(){return unpack((await api.get<Schedule[]|PageResult<Schedule>>('schedules/')).data)}
export async function createSchedule(payload:{doctor:number;date:string;start_time:string;end_time:string;slot_minutes:number}){return(await api.post<Schedule>('schedules/',payload)).data}
export async function updateSchedule(id:number,payload:Partial<Schedule>){return(await api.patch<Schedule>(`schedules/${id}/`,payload)).data}
