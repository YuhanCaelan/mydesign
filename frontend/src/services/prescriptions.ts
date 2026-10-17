import api from './api'
import type{Medicine,PageResult,Prescription,PrescriptionItem}from'../types/medical'
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getPrescriptions(params:Record<string,unknown>={}){return unpack((await api.get<Prescription[]|PageResult<Prescription>>('prescriptions/',{params})).data)}
export async function getMedicines(search=''){return unpack((await api.get<Medicine[]|PageResult<Medicine>>('medicines/',{params:{search,available:true}})).data).results}
export async function createPrescription(payload:{record_id:number;notes:string;items:PrescriptionItem[];admission_id?:number|null}){return(await api.post<Prescription>('prescriptions/',payload)).data}
export async function cancelPrescription(id:number){return(await api.post<Prescription>(`prescriptions/${id}/cancel/`)).data}
