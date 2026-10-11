import api from './api'
import type{BillingRecord,Department,DoctorSummary,ExaminationItem,InpatientAdmission,Medicine,PageResult,PatientSummary,StockMovement,WardBed}from'../types/medical'
const unpack=<T>(data:T[]|PageResult<T>)=>Array.isArray(data)?{count:data.length,results:data}:data
export async function getMedicines(params:Record<string,unknown>={}){return unpack((await api.get<Medicine[]|PageResult<Medicine>>('medicines/',{params})).data)}
export async function saveMedicine(payload:Record<string,unknown>,id?:number){return(await(id?api.patch<Medicine>(`medicines/${id}/`,payload):api.post<Medicine>('medicines/',payload))).data}
export async function adjustMedicineStock(id:number,delta:number){return(await api.post<Medicine>(`medicines/${id}/adjust-stock/`,{delta})).data}
export async function getBills(params:Record<string,unknown>={}){return unpack((await api.get<BillingRecord[]|PageResult<BillingRecord>>('billing-records/',{params})).data)}
export async function createBill(payload:Record<string,unknown>){return(await api.post<BillingRecord>('billing-records/',payload)).data}
export async function payBill(id:number,payment_method='演示支付'){return(await api.post<BillingRecord>(`billing-records/${id}/pay/`,{payment_method})).data}
export async function cancelBill(id:number){return(await api.post<BillingRecord>(`billing-records/${id}/cancel/`)).data}
export async function getInpatients(params:Record<string,unknown>={}){return unpack((await api.get<InpatientAdmission[]|PageResult<InpatientAdmission>>('inpatients/',{params})).data)}
export async function createInpatient(payload:Record<string,unknown>){return(await api.post<InpatientAdmission>('inpatients/',payload)).data}
export async function admitPatient(id:number){return(await api.post<InpatientAdmission>(`inpatients/${id}/admit/`)).data}
export async function dischargePatient(id:number,discharge_summary:string){return(await api.post<InpatientAdmission>(`inpatients/${id}/discharge/`,{discharge_summary})).data}
export async function getPatients(){return unpack((await api.get<PatientSummary[]|PageResult<PatientSummary>>('patients/')).data).results}
export async function getOperationDoctors(){return unpack((await api.get<DoctorSummary[]|PageResult<DoctorSummary>>('doctors/')).data).results}
export async function getOperationDepartments(){return unpack((await api.get<Department[]|PageResult<Department>>('departments/',{params:{status:'active'}})).data).results}
export async function getWardBeds(params:Record<string,unknown>={}){return unpack((await api.get<WardBed[]|PageResult<WardBed>>('ward-beds/',{params})).data)}
export async function saveWardBed(payload:Record<string,unknown>,id?:number){return(await(id?api.patch<WardBed>(`ward-beds/${id}/`,payload):api.post<WardBed>('ward-beds/',payload))).data}
export async function getExaminationItems(params:Record<string,unknown>={}){return unpack((await api.get<ExaminationItem[]|PageResult<ExaminationItem>>('examination-items/',{params})).data)}
export async function saveExaminationItem(payload:Record<string,unknown>,id?:number){return(await(id?api.patch<ExaminationItem>(`examination-items/${id}/`,payload):api.post<ExaminationItem>('examination-items/',payload))).data}
export async function getStockMovements(params:Record<string,unknown>={}){return unpack((await api.get<StockMovement[]|PageResult<StockMovement>>('medicine-stock-movements/',{params})).data)}
