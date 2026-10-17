import api from './api'
import type{Department,DepartmentDoctor,DepartmentHistoryResult,DepartmentOverviewResult,DepartmentVisitResult,DoctorSummary,OutpatientResult,PageResult}from'../types/medical'
export interface ManagedUser{id:number;username:string;full_name:string;role:'doctor'|'patient';role_display:string;phone:string;email:string;is_active:boolean;is_active_display:string;doctor_no?:string|null;doctor_id?:number|null;doctor_title?:string|null;doctor_specialty?:string|null;patient_no?:string|null;patient_id?:number|null;department_name?:string|null;created_at:string}
export interface Schedule{id:number;doctor:number;doctor_name:string;date:string;start_time:string;end_time:string;time_range:string;slot_minutes:number;is_active:boolean;total_slots:number;available_slots:number}
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getUsers(params:Record<string,unknown>={}){return unpack((await api.get<ManagedUser[]|PageResult<ManagedUser>>('users/',{params})).data)}
export async function createUser(payload:Record<string,unknown>){return(await api.post<ManagedUser>('users/',payload)).data}
export async function updateUser(id:number,payload:Record<string,unknown>){return(await api.patch<ManagedUser>(`users/${id}/`,payload)).data}
export async function getDepartmentsAdmin(params:Record<string,unknown>={}){return unpack((await api.get<Department[]|PageResult<Department>>('departments/',{params})).data)}
export async function createDepartment(payload:{name:string;description:string}){return(await api.post<Department>('departments/',payload)).data}
export async function updateDepartment(id:number,payload:Partial<Department>){return(await api.patch<Department>(`departments/${id}/`,payload)).data}
export async function getDepartmentOverview(params:Record<string,unknown>={}){return(await api.get<DepartmentOverviewResult>('departments/overview/',{params})).data}
export async function getDepartmentVisits(id:number,params:Record<string,unknown>={}){return(await api.get<DepartmentVisitResult>(`departments/${id}/visits/`,{params})).data}
export async function getDepartmentDoctors(id:number,params:Record<string,unknown>={}){return(await api.get<{date:string;department_id:number;department_name:string;count:number;results:DepartmentDoctor[]}>(`departments/${id}/doctors/`,{params})).data}
export async function getDepartmentHistoryPatients(id:number,params:Record<string,unknown>={}){return(await api.get<DepartmentHistoryResult>(`departments/${id}/history-patients/`,{params})).data}
export async function getDoctorsAdmin(params:Record<string,unknown>={}){return unpack((await api.get<DoctorSummary[]|PageResult<DoctorSummary>>('doctors/',{params})).data).results}
export async function getSchedules(params:Record<string,unknown>={}){return unpack((await api.get<Schedule[]|PageResult<Schedule>>('schedules/',{params})).data)}
export async function createSchedule(payload:{doctor:number;date:string;start_time:string;end_time:string;slot_minutes:number}){return(await api.post<Schedule>('schedules/',payload)).data}
export async function updateSchedule(id:number,payload:Partial<Schedule>){return(await api.patch<Schedule>(`schedules/${id}/`,payload)).data}
export async function getOutpatientVisits(params:Record<string,unknown>={}){return(await api.get<OutpatientResult>('schedules/outpatient/',{params})).data}
