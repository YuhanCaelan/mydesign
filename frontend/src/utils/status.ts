export type StatusTone='primary'|'success'|'warning'|'danger'|'info'
export interface StatusInfo{label:string;tone:StatusTone}

export const appointmentStatuses:Record<string,StatusInfo>={
  pending:{label:'待就诊',tone:'warning'},
  in_progress:{label:'就诊中',tone:'primary'},
  completed:{label:'已完成',tone:'success'},
  cancelled:{label:'已取消',tone:'info'},
  no_show:{label:'爽约',tone:'danger'},
}
export const recordStatuses:Record<string,StatusInfo>={
  draft:{label:'草稿',tone:'warning'},
  confirmed:{label:'已确认',tone:'success'},
}
export const examinationStatuses:Record<string,StatusInfo>={
  requested:{label:'已申请',tone:'warning'},
  in_progress:{label:'检查中',tone:'primary'},
  completed:{label:'报告待发布',tone:'warning'},
  published:{label:'已发布',tone:'success'},
  cancelled:{label:'已取消',tone:'info'},
}
export const inpatientStatuses:Record<string,StatusInfo>={
  pending:{label:'待入院',tone:'warning'},
  admitted:{label:'住院中',tone:'primary'},
  discharged:{label:'已出院',tone:'success'},
  cancelled:{label:'已取消',tone:'info'},
}
export const billingStatuses:Record<string,StatusInfo>={
  unpaid:{label:'待缴费',tone:'warning'},
  paid:{label:'已缴费',tone:'success'},
  cancelled:{label:'已取消',tone:'info'},
}
export const prescriptionStatuses:Record<string,StatusInfo>={
  issued:{label:'待缴费取药',tone:'warning'},
  dispensed:{label:'已取药',tone:'success'},
  cancelled:{label:'已作废',tone:'info'},
}
export const slotStatuses:Record<string,StatusInfo>={
  available:{label:'可预约',tone:'success'},
  booked:{label:'已预约',tone:'warning'},
  closed:{label:'已关闭',tone:'info'},
}

export type StatusDomain='appointment'|'record'|'examination'|'inpatient'|'billing'|'prescription'|'slot'
const maps:Record<StatusDomain,Record<string,StatusInfo>>={
  appointment:appointmentStatuses,record:recordStatuses,examination:examinationStatuses,
  inpatient:inpatientStatuses,billing:billingStatuses,prescription:prescriptionStatuses,slot:slotStatuses,
}
export function statusInfo(domain:StatusDomain,statusOrLabel:string):StatusInfo{
  const map=maps[domain]
  if(map[statusOrLabel])return map[statusOrLabel]
  const found=Object.values(map).find(item=>item.label===statusOrLabel)
  return found||{label:statusOrLabel,tone:'info'}
}
export function statusTone(domain:StatusDomain,statusOrLabel:string):StatusTone{return statusInfo(domain,statusOrLabel).tone}
export function statusLabel(domain:StatusDomain,statusOrLabel:string):string{return statusInfo(domain,statusOrLabel).label}
export function statusItems(domain:StatusDomain){return Object.entries(maps[domain]).map(([key,value])=>({key,...value}))}
