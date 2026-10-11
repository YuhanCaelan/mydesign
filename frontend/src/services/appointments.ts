import api from './api'
import type{Appointment,AppointmentSlot,Department,DoctorSummary,PageResult}from'../types/medical'
const list=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?data:data.results
export async function getDepartments(){return list((await api.get<Department[]|PageResult<Department>>('departments/',{params:{status:'active'}})).data)}
export async function getDoctors(department?:number){return list((await api.get<DoctorSummary[]|PageResult<DoctorSummary>>('doctors/',{params:{department}})).data)}
export async function getSlots(doctor:number,date:string){return list((await api.get<AppointmentSlot[]|PageResult<AppointmentSlot>>(`doctors/${doctor}/slots/`,{params:{date}})).data)}
export async function getAppointments(params:Record<string,unknown>={}){const data=(await api.get<Appointment[]|PageResult<Appointment>>('appointments/',{params})).data;return{rows:list(data),count:Array.isArray(data)?data.length:data.count}}
export async function createAppointment(payload:{slot_id:number;reason:string}){return(await api.post<Appointment>('appointments/',payload)).data}
export async function cancelAppointment(id:number){return(await api.post<Appointment>(`appointments/${id}/cancel/`)).data}
export async function startAppointment(id:number){return(await api.post<Appointment>(`appointments/${id}/start/`)).data}
export async function completeAppointment(id:number){return(await api.post<Appointment>(`appointments/${id}/complete/`)).data}
export async function markNoShow(id:number){return(await api.post<Appointment>(`appointments/${id}/no-show/`)).data}
