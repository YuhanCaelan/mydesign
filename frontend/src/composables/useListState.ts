import{reactive,watch}from'vue'

/**
 * 将列表页的筛选条件、页码和每页条数保存在本次浏览器会话中。
 * 子页切换或从详情返回时重新挂载页面，仍能恢复原来的列表位置。
 */
export function useListState<T extends object>(key:string,defaults:T):T{
  const storageKey=`smartmedical:list:${key}`
  const initial={...defaults} as Record<string,unknown>
  try{
    const saved=sessionStorage.getItem(storageKey)
    if(saved)Object.assign(initial,JSON.parse(saved))
  }catch{/* 会话存储不可用时退回默认值 */}
  const state=reactive(initial) as T
  watch(state,()=>{
    try{sessionStorage.setItem(storageKey,JSON.stringify(state))}catch{/* 忽略存储失败 */}
  },{deep:true})
  return state
}

export function clearListState(key:string){
  try{sessionStorage.removeItem(`smartmedical:list:${key}`)}catch{/* 忽略存储失败 */}
}
