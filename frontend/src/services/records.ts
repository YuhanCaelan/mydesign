import api from './api'
import type{MedicalRecord,PageResult}from'../types/medical'

export interface RecordPayload{appointment_id:number;chief_complaint:string;present_illness:string;past_history:string;examination:string;diagnosis:string;treatment:string}
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getRecords(params:Record<string,unknown>={}){return unpack((await api.get<MedicalRecord[]|PageResult<MedicalRecord>>('medical-records/',{params})).data)}
export async function getRecord(id:number){return(await api.get<MedicalRecord>(`medical-records/${id}/`)).data}
export async function createRecord(payload:RecordPayload){return(await api.post<MedicalRecord>('medical-records/',payload)).data}
export async function updateRecord(id:number,payload:Omit<RecordPayload,'appointment_id'>){return(await api.patch<MedicalRecord>(`medical-records/${id}/`,payload)).data}
export async function confirmRecord(id:number){return(await api.post<MedicalRecord>(`medical-records/${id}/confirm/`)).data}
export async function completeVisit(id:number){return(await api.post<MedicalRecord>(`medical-records/${id}/complete-visit/`)).data}
export async function addCorrection(id:number,content:string){return(await api.post(`medical-records/${id}/corrections/`,{content})).data}
