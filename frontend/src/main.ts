import {createApp} from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@fontsource-variable/noto-sans-sc'
import '@fontsource/ibm-plex-sans-condensed/500.css'
import '@fontsource/ibm-plex-sans-condensed/600.css'
import './style.css'
import App from './App.vue'
import router from './router'
import {createPinia} from 'pinia'
import {useAuthStore} from './stores/auth'

async function bootstrap(){
  const pinia=createPinia()
  const auth=useAuthStore(pinia)
  await auth.refresh()
  createApp(App).use(pinia).use(router).use(ElementPlus).mount('#app')
}

bootstrap()
