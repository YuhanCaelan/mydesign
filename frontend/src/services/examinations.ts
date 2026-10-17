import api from './api'
import type{ExaminationOrder,PageResult}from'../types/medical'
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getExaminations(params:Record<string,unknown>={}){return unpack((await api.get<ExaminationOrder[]|PageResult<ExaminationOrder>>('examinations/',{params})).data)}
export async function createExamination(payload:{record_id:number;item_id:number;type:string;clinical_question:string;admission_id?:number|null}){return(await api.post<ExaminationOrder>('examinations/',payload)).data}
export async function startExamination(id:number){return(await api.post<ExaminationOrder>(`examinations/${id}/start/`)).data}
export async function saveReport(id:number,payload:{findings:string;conclusion:string}){return(await api.post(`examinations/${id}/report/`,payload)).data}
export async function publishReport(id:number){return(await api.post<ExaminationOrder>(`examinations/${id}/publish/`)).data}
export async function uploadMedicalFile(id:number,file:File){const body=new FormData();body.append('file',file);return(await api.post(`examinations/${id}/upload/`,body)).data}
export async function downloadMedicalFile(id:number,name:string){const{data}=await api.get(`medical-files/${id}/download/`,{responseType:'blob'});const url=URL.createObjectURL(data);const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();URL.revokeObjectURL(url)}
