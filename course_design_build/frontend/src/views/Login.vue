<script setup lang="ts">
import {reactive,ref} from 'vue';import type{FormInstance,FormRules}from'element-plus';import{ElMessage}from'element-plus';import{useRouter}from'vue-router';import{useAuthStore}from'../stores/auth'
const form=reactive({username:'admin',password:'Admin123!'}),loading=ref(false),formRef=ref<FormInstance>(),router=useRouter(),auth=useAuthStore()
const rules:FormRules={username:[{required:true,message:'请输入用户名',trigger:'blur'}],password:[{required:true,message:'请输入密码',trigger:'blur'},{min:6,message:'密码至少6位',trigger:'blur'}]}
async function submit(){await formRef.value?.validate();loading.value=true;try{await auth.login(form.username,form.password);ElMessage.success('登录成功');router.push('/dashboard')}finally{loading.value=false}}
</script>
<template><div class="login"><el-card><h1>慧医云</h1><p>智慧医疗管理系统 · 课程设计版</p><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="用户名" prop="username"><el-input v-model="form.username"/></el-form-item><el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password @keyup.enter="submit"/></el-form-item><el-button type="primary" :loading="loading" style="width:100%" @click="submit">登录系统</el-button></el-form><div class="accounts">测试账号：admin / doctor / patient<br>密码：Admin123! / Doctor123! / Patient123!</div></el-card></div></template>
