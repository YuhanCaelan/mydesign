import api from './api'
import type{PageResult,PatientSummary}from'../types/medical'

/** 患者本人档案；仅患者角色可访问。 */
export async function getMyPatient(){return(await api.get<PatientSummary>('patients/me/')).data}

/** 医师读取有预约关系的患者详情。 */
export async function getPatient(id:number){return(await api.get<PatientSummary>(`patients/${id}/`)).data}

/** 医师搜索有预约关系的患者，支持姓名、患者号、手机号。 */
export async function searchPatients(params:Record<string,unknown>={}){
  const data=(await api.get<PatientSummary[]|PageResult<PatientSummary>>('patients/',{params})).data
  return Array.isArray(data)?{count:data.length,results:data}:data
}
