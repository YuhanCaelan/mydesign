import{computed,watch}from'vue'
import{useRoute,useRouter}from'vue-router'

/**
 * 子页统一使用 ?tab= 表示。无效或重复的 tab 自动回到默认页；
 * 切换子页时保留其他查询参数（如医师/科室预选）。
 */
export function useTabQuery<T extends string>(tabs:readonly T[],fallback:T){
  const route=useRoute(),router=useRouter()
  const valid=(value:unknown):value is T=>typeof value==='string'&&(tabs as readonly string[]).includes(value)
  const current=computed<T>(()=>valid(route.query.tab)?route.query.tab:fallback)
  watch(()=>route.query.tab,value=>{
    if(value===undefined)return
    if(!valid(value)){
      const query={...route.query,tab:fallback}
      router.replace({path:route.path,query})
    }
  },{immediate:true})
  function setTab(tab:string){
    if(!valid(tab)||tab===current.value)return
    router.replace({path:route.path,query:{...route.query,tab}})
  }
  return{current,setTab}
}
