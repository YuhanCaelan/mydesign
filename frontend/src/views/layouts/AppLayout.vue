<script setup lang="ts">
import{computed,onBeforeUnmount,onMounted,ref,watch}from'vue'
import{useRoute,useRouter}from'vue-router'
import{ArrowDown,Clock,Menu as MenuIcon}from'@element-plus/icons-vue'
import{navigationFor}from'../../config/navigation'
import{useAuthStore}from'../../stores/auth'
const auth=useAuthStore(),route=useRoute(),router=useRouter(),mobileOpen=ref(false),compact=ref(false),now=ref(new Date())
const menu=computed(()=>navigationFor(auth.user!.role)),roleLabel=computed(()=>({admin:'系统管理员',doctor:'医师',patient:'患者'}[auth.user!.role]))
const dateText=computed(()=>new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'short'}).format(now.value))
const timeText=computed(()=>now.value.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false}))
let timer=0
onMounted(()=>{timer=window.setInterval(()=>now.value=new Date(),30000)})
onBeforeUnmount(()=>clearInterval(timer))
watch(()=>route.fullPath,()=>{mobileOpen.value=false})
function logout(){auth.logout();router.replace('/login')}
</script>
<template><div class="app-shell" :class="{'nav-compact':compact}"><div v-if="mobileOpen" class="nav-mask" @click="mobileOpen=false"/><aside class="app-nav" :class="{open:mobileOpen}"><div class="brand"><div class="brand-mark" aria-hidden="true"><span/><span/></div><div class="brand-copy"><strong>慧医云</strong><small>临床协作与运营平台</small></div><button class="nav-collapse" :aria-label="compact?'展开导航':'收起导航'" @click="compact=!compact">{{compact?'›':'‹'}}</button></div><nav aria-label="主导航"><section v-for="group in menu" :key="group.label"><p>{{group.label}}</p><router-link v-for="item in group.items" :key="item.path" :to="item.path" :title="item.label"><el-icon><component :is="item.icon"/></el-icon><span>{{item.label}}</span></router-link></section></nav><div class="nav-footer"><span class="status-dot"/><div><b>服务运行正常</b><small>数据已安全连接</small></div></div></aside><main class="app-main"><header class="app-header"><button class="mobile-trigger" aria-label="打开导航" @click="mobileOpen=true"><el-icon><MenuIcon/></el-icon></button><div class="system-rail"><div class="pulse-mark"><span/><i/><span/></div><div><strong>临床运行中心</strong><small>诊疗、检查、住院和结算数据实时同步</small></div></div><div class="header-tools"><div class="clock"><el-icon><Clock/></el-icon><span><b>{{timeText}}</b><small>{{dateText}}</small></span></div><el-dropdown trigger="click"><button class="account"><span class="avatar">{{auth.user?.full_name?.slice(0,1)||'用'}}</span><span><b>{{auth.user?.full_name}}</b><small>{{roleLabel}}</small></span><el-icon><ArrowDown/></el-icon></button><template #dropdown><el-dropdown-menu><el-dropdown-item @click="router.push('/profile')">个人中心</el-dropdown-item><el-dropdown-item divided @click="logout">退出登录</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></header><div class="page-wrap"><router-view/></div></main></div></template>
