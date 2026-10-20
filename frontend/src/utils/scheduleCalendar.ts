/** Calendar dates use local components rather than UTC serialization. */
export function localDate(date=new Date()):string{
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
}
export function monthDays(month:string){
  const [year,number]=month.split('-').map(Number)
  const first=new Date(year!,number!-1,1)
  const offset=(first.getDay()+6)%7
  const length=Math.ceil((offset+new Date(year!,number!,0).getDate())/7)*7
  return Array.from({length},(_,index)=>{
    const date=new Date(year!,number!-1,1-offset+index)
    return {value:localDate(date),day:date.getDate(),inMonth:date.getMonth()===number!-1}
  })
}
export function shiftMonth(month:string,offset:number):string{
  const [year,number]=month.split('-').map(Number)
  return localDate(new Date(year!,number!-1+offset,1)).slice(0,7)
}
