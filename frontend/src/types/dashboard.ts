export type DashboardRange='7d'|'30d'|'90d'
export interface DashboardKpi{key:string;label:string;value:number|string;unit:string;change:number|null;tone:'neutral'|'warning'|'danger'|'success'}
export interface TimeSeriesPoint{date:string;visits:number;completed:number;revenue:number}
export interface NamedValue{name:string;value:number|string}
export interface DashboardAlert{label:string;value:number;tone:string;path:string}
export interface RecentActivity{id:number;number:string;patient:string;doctor:string;department:string;date:string;time:string;status:string}
export interface DashboardData{
  meta:{range:DashboardRange;start:string;end:string;generated_at:string;role:string}
  kpis:DashboardKpi[];timeseries:TimeSeriesPoint[];appointment_status:NamedValue[];recent_activity:RecentActivity[];alerts:DashboardAlert[]
  department_workload?:NamedValue[];doctor_workload?:NamedValue[];billing_categories?:NamedValue[];inpatient_status?:NamedValue[];workflow?:NamedValue[]
  today_schedule?:{id:number;time:string;patient:string;reason:string;status:string;status_label:string}[]
  examination_queue?:{id:number;number:string;patient:string;type:string;status:string;status_label:string;created_at:string}[]
  next_appointment?:RecentActivity|null
}
