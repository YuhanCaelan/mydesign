<script setup lang="ts">
import {reactive,ref} from 'vue'
import {useRouter} from 'vue-router'
import api from '../../services/api'
const router=useRouter(),loading=ref(false),error=ref(''),form=reactive({username:'',password:'',password_confirm:'',full_name:'',phone:''})
async function submit(){error.value='';if(!form.username||!form.password||!form.full_name){error.value='请完整填写必填信息';return}if(form.password!==form.password_confirm){error.value='两次输入的密码不一致';return}loading.value=true;try{await api.post('auth/register/',form);await router.push('/login')}catch(e:any){error.value=e.response?.data?.detail||'注册失败，请检查填写内容'}finally{loading.value=false}}
</script>
<template><main class="simple-auth"><div class="simple-card"><router-link to="/login" class="back">← 返回登录</router-link><div class="live-label"><i/>患者自助服务</div><h1>创建患者账户</h1><p class="muted">医师账户由管理员创建，患者可在此自主注册。</p><el-form label-position="top"><el-form-item label="姓名"><el-input v-model="form.full_name"/></el-form-item><el-form-item label="手机号码"><el-input v-model="form.phone"/></el-form-item><el-form-item label="用户名"><el-input v-model="form.username"/></el-form-item><el-form-item label="密码"><el-input v-model="form.password" type="password" show-password/></el-form-item><el-form-item label="确认密码"><el-input v-model="form.password_confirm" type="password" show-password @keyup.enter="submit"/></el-form-item><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-button class="submit" type="primary" :loading="loading" @click="submit">完成注册</el-button></el-form></div></main></template>
