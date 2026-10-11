import api from'./api'
import type{DashboardData,DashboardRange}from'../types/dashboard'
export async function getDashboard(range:DashboardRange='30d'){return(await api.get<DashboardData>('statistics/dashboard/',{params:{range}})).data}
