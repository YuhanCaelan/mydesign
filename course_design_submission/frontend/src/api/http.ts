import axios from 'axios'
import {ElMessage} from 'element-plus'
const http=axios.create({baseURL:'/api/v1',timeout:12000})
http.interceptors.request.use(config=>{const token=localStorage.getItem('course_token');if(token)config.headers.Authorization=`Bearer ${token}`;return config})
http.interceptors.response.use(response=>response,error=>{
  const message=error.response?.data?.detail||'网络请求失败，请检查后端服务'
  ElMessage.error(message)
  if(error.response?.status===401){localStorage.clear();if(location.pathname!='/login')location.assign('/login')}
  return Promise.reject(error)
})
export default http
