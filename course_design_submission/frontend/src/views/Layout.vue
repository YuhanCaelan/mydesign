<script setup lang="ts">
import {computed} from 'vue';import {useRouter} from 'vue-router';import {useAuthStore} from '../stores/auth'
const auth=useAuthStore(),router=useRouter();const roleName=computed(()=>({admin:'管理员',doctor:'医师',patient:'患者'}[auth.user?.role||'patient']))
function logout(){auth.logout();router.push('/login')}
</script>
<template><div class="shell"><aside><div class="brand">✚ 慧医云<small>课程设计版</small></div><el-menu router :default-active="$route.path"><el-menu-item index="/dashboard">数据总览</el-menu-item><el-menu-item v-if="auth.user?.role==='admin'" index="/departments">科室管理</el-menu-item><el-menu-item index="/schedules">{{auth.user?.role==='patient'?'就诊预约':'医师排班'}}</el-menu-item><el-menu-item index="/appointments">{{auth.user?.role==='doctor'?'接诊管理':'我的预约'}}</el-menu-item></el-menu></aside><main><header><span>智慧医疗管理系统</span><div>{{auth.user?.full_name}} · {{roleName}} <el-button link @click="logout">退出</el-button></div></header><section class="content"><router-view/></section></main></div></template>
