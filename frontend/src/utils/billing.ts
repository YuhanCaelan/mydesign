export const billingCategoryLabels:Record<string,string>={
  registration:'挂号费',
  examination:'检查费',
  medicine:'药品费',
  inpatient:'住院费',
  other:'其他',
}
export function billingCategoryLabel(key:string):string{return billingCategoryLabels[key]||key}
