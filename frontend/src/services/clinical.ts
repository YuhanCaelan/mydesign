import api from './api'
import type{InpatientOrder,InpatientRecord,PageResult,ProcedureItem,ProcedureOrder,RecordTemplate,ReportShare,SharedReport}from'../types/medical'

const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data

export async function registerEmergency(payload:{patient_id?:number;patient?:number;doctor_id?:number;doctor?:number;triage_level:number;reason:string}){return(await api.post('appointments/emergency/',payload)).data}
export async function dispensePrescription(id:number){return(await api.post(`prescriptions/${id}/dispense/`)).data}
export async function refundBill(id:number,reason:string){return(await api.post(`billing-records/${id}/refund/`,{reason})).data}
export async function getProcedureItems(params:Record<string,unknown>={}){return unpack((await api.get<ProcedureItem[]|PageResult<ProcedureItem>>('procedure-items/',{params})).data)}
export async function saveProcedureItem(payload:Record<string,unknown>,id?:number){return(await(id?api.patch<ProcedureItem>(`procedure-items/${id}/`,payload):api.post<ProcedureItem>('procedure-items/',payload))).data}
export async function getProcedures(params:Record<string,unknown>={}){return unpack((await api.get<ProcedureOrder[]|PageResult<ProcedureOrder>>('procedures/',{params})).data)}
export async function createProcedure(payload:{record_id:number;item_id:number;clinical_note:string;admission_id?:number|null}){return(await api.post<ProcedureOrder>('procedures/',payload)).data}
export async function startProcedure(id:number){return(await api.post<ProcedureOrder>(`procedures/${id}/start/`)).data}
export async function completeProcedure(id:number){return(await api.post<ProcedureOrder>(`procedures/${id}/complete/`)).data}
export async function cancelProcedure(id:number){return(await api.post<ProcedureOrder>(`procedures/${id}/cancel/`)).data}
export async function getRecordTemplates(params:Record<string,unknown>={}){return unpack((await api.get<RecordTemplate[]|PageResult<RecordTemplate>>('record-templates/',{params})).data)}
export async function createReportShare(reportId:number){return(await api.post<ReportShare>(`examination-reports/${reportId}/share/`)).data}
export async function getSharedReport(token:string){return(await api.get<SharedReport>(`share/reports/${token}/`)).data}
export async function receiveInpatient(id:number){return(await api.post(`inpatients/${id}/receive/`)).data}
export async function getInpatientRecord(id:number){return(await api.get<{record:InpatientRecord|null}>(`inpatients/${id}/record/`)).data}
export async function saveInpatientRecord(id:number,payload:Partial<InpatientRecord>){return(await api.put<{record:InpatientRecord}>(`inpatients/${id}/record/`,payload)).data}
export async function getInpatientOrders(id:number,order_type?:'long'|'temp'){return(await api.get<{count:number;results:InpatientOrder[]}>(`inpatients/${id}/orders/`,{params:{order_type}})).data}
export async function createInpatientOrder(id:number,payload:Partial<InpatientOrder>){return(await api.post<InpatientOrder>(`inpatients/${id}/orders/`,payload)).data}
export async function executeInpatientOrder(admissionId:number,orderId:number,execution_note=''){return(await api.post<InpatientOrder>(`inpatients/${admissionId}/orders/${orderId}/execute/`,{execution_note})).data}
export async function stopInpatientOrder(admissionId:number,orderId:number){return(await api.post<InpatientOrder>(`inpatients/${admissionId}/orders/${orderId}/stop/`)).data}

export async function getMedicineCatalog(params:Record<string,unknown>={}){return unpack((await api.get<PageResult<import('../types/medical').Medicine>|import('../types/medical').Medicine[]>('medicines/',{params})).data)}
export async function getExaminationCatalog(params:Record<string,unknown>={}){return unpack((await api.get<PageResult<import('../types/medical').ExaminationItem>|import('../types/medical').ExaminationItem[]>('examination-items/',{params})).data)}
export async function getDepartmentsCatalog(){return(await api.get('departments/',{params:{status:'active',page_size:100}})).data.results||[]}
export async function getWardBedsAvailable(department?:number){return unpack((await api.get<PageResult<import('../types/medical').WardBed>|import('../types/medical').WardBed[]>('ward-beds/',{params:{department,available:true,page_size:100}})).data)}
export async function createInpatientRequest(payload:Record<string,unknown>){return(await api.post('inpatients/',payload)).data}
export async function getAppointmentList(params:Record<string,unknown>={}){return unpack((await api.get<PageResult<import('../types/medical').Appointment>|import('../types/medical').Appointment[]>('appointments/',{params})).data)}

export async function assignInpatientBed(id:number,bed_id:number){return(await api.post(`inpatients/${id}/assign-bed/`,{bed_id})).data}
export async function getPatientsForStaff(search=''){return unpack((await api.get<PageResult<import('../types/medical').PatientSummary>|import('../types/medical').PatientSummary[]>('patients/',{params:{search,page_size:50}})).data)}
export async function getDoctorsForStaff(department?:number){return unpack((await api.get<PageResult<import('../types/medical').DoctorSummary>|import('../types/medical').DoctorSummary[]>('doctors/',{params:{department,page_size:100}})).data)}
export async function getDepartmentsForStaff(){return(await api.get('departments/',{params:{status:'active',page_size:100}})).data.results||[]}
