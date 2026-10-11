import axios from 'axios'

const api = axios.create({baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1/', timeout: 15000})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('smart_medical_access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) {
    localStorage.removeItem('smart_medical_access')
    localStorage.removeItem('smart_medical_refresh')
    localStorage.removeItem('smart_medical_user')
    if (!location.pathname.endsWith('/login')) location.assign(`${import.meta.env.BASE_URL}login`)
  }
  return Promise.reject(error)
})

export default api
