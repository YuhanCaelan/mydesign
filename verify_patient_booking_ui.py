"""患者日历预约的隔离浏览器验收，不创建真实预约。

复用 verify_schedule_ui.py 的静态服务和模拟医师、科室，支持 SCHEDULE_DIST 指定构建目录。
"""
import json
import threading
import time
from datetime import date,timedelta
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse
from verify_schedule_ui import Chrome,DIST,DOCTORS,Handler,ROWS,STATE,schedule

TODAY=date.today().isoformat()
DAY=(date.today()+timedelta(days=1)).isoformat()
STATE.update(role='patient',fail_slots=False,conflict=False,appointments=[])
ROWS[:]=[schedule(1,DAY),schedule(2,DAY,2),schedule(3,DAY,101)]
for row in ROWS:row['is_active']=True
ROWS[1]['available_slots']=0
SLOTS=[dict(id=i+1,schedule_id=1,doctor_id=1,date=DAY,start_time=f'{9+i//2:02}:{30*(i%2):02}:00',end_time=f'{9+(i+1)//2:02}:{30*((i+1)%2):02}:00',status='available') for i in range(4)]


class PatientHandler(Handler):
    def do_GET(self):
        url=urlparse(self.path)
        if url.path.endswith('/slots/'):
            STATE['requests'].append(url.path+'?'+url.query)
            if STATE['fail_slots']:return self.reply({'detail':'模拟号源加载失败'},500)
            selected=int(parse_qs(url.query).get('schedule',['0'])[0])
            return self.reply([slot for slot in SLOTS if slot['schedule_id']==selected])
        if url.path=='/api/v1/appointments/':
            return self.reply({'count':len(STATE['appointments']),'results':STATE['appointments']})
        return super().do_GET()

    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if STATE['conflict']:
            SLOTS[:]=[slot for slot in SLOTS if slot['id']!=payload['slot_id']]
            ROWS[0]['available_slots']=len(SLOTS)
            return self.reply({'detail':'请求数据校验失败。','errors':{'non_field_errors':['该号源已不可预约。']}},400)
        slot=next(slot for slot in SLOTS if slot['id']==payload['slot_id'])
        appointment=dict(id=1,appointment_no='APT-TEST-001',patient_id=1,patient_name='测试患者',doctor_id=1,doctor_name=DOCTORS[0]['full_name'],department_id=1,department_name='内科',slot=slot,visit_date=DAY,status='pending',reason=payload['reason'])
        STATE['appointments'].append(appointment)
        SLOTS.remove(slot);ROWS[0]['available_slots']=len(SLOTS)
        return self.reply(appointment,201)


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args,**kwargs:PatientHandler(*args,directory=str(DIST),**kwargs))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    chrome=Chrome();count=0

    def check(label,expression):
        nonlocal count
        assert chrome.evaluate(expression),label
        count+=1;print('PASS',label,flush=True)

    def click(selector,text=None):
        chrome.evaluate(f"[...document.querySelectorAll({json.dumps(selector)})].find(x=>x.getBoundingClientRect().height&&(!{json.dumps(text)}||x.innerText.includes({json.dumps(text)}))).click()")
        time.sleep(.2)

    try:
        chrome.send('Page.enable');chrome.viewport(1440,1000)
        chrome.goto(base+'/app/login',.2)
        chrome.evaluate("localStorage.setItem('smart_medical_access','fixture');localStorage.setItem('smart_medical_user',JSON.stringify({id:1,username:'patient',role:'patient',full_name:'测试患者'}))")
        chrome.goto(base+'/app/patient/visits',.4)
        assert chrome.wait_for("document.querySelector('.schedule-panel')?.getAttribute('aria-busy')==='false'")
        check('患者默认进入排班预约',"document.querySelector('h1').innerText==='排班预约'&&document.querySelectorAll('.folder-tab').length===3")
        check('无排班日期显示空状态',"document.querySelectorAll('.schedule-event').length===0&&!!document.querySelector('.schedule-agenda .el-empty')")
        check('患者没有排班管理操作',"!document.querySelector('.schedule-agenda-head button')&&!document.querySelector('.schedule-panel').innerText.includes('新建排班')")
        check('过去日期不可预约',f"[...document.querySelectorAll('.schedule-day')].filter(x=>x.getAttribute('aria-label').slice(0,10)<'{TODAY}').every(x=>x.disabled)")
        click(f'.schedule-day[aria-label^="{DAY}"]')
        check('选日展示三位出诊医师',"document.querySelectorAll('.schedule-event').length===3")
        click('.schedule-filters .el-select:first-child .el-select__wrapper')
        chrome.evaluate("[...document.querySelectorAll('.el-select-dropdown__item')].find(x=>x.getBoundingClientRect().height&&x.innerText.includes('内科')).click()")
        time.sleep(.2)
        check('科室过滤及无余号禁用预约',"document.querySelectorAll('.schedule-event').length===2&&document.querySelectorAll('.schedule-event button:disabled').length===1")
        click('.schedule-filters .el-select:nth-child(2) .el-select__wrapper')
        chrome.evaluate("[...document.querySelectorAll('.el-select-dropdown__item')].find(x=>x.getBoundingClientRect().height&&x.innerText.includes('测试医师1 ·')).click()")
        time.sleep(.2)
        check('按医师筛选日历',"document.querySelectorAll('.schedule-event').length===1")
        STATE['fail_slots']=True
        click('.schedule-event button')
        check('号源失败显示重试而非无余号',"!!document.querySelector('.el-dialog .list-error')")
        STATE['fail_slots']=False
        click('.el-dialog .list-error button','重试')
        check('号源重试恢复',"document.querySelectorAll('.patient-slot-options .slot-list button').length===4")
        assert any('schedule=1' in request for request in STATE['requests'] if '/slots/' in request)
        check('弹窗展示已选日期医师和科室',f"document.querySelector('.patient-booking-context').innerText.includes('{DAY}')&&document.querySelector('.patient-booking-context').innerText.includes('测试医师1')")
        check('未填号源或原因不能确认',"document.querySelector('.el-dialog__footer .el-button--primary').disabled")
        click('.patient-slot-options button')
        chrome.evaluate("(()=>{const input=document.querySelector('.el-dialog textarea');input.value='头痛三天';input.dispatchEvent(new Event('input',{bubbles:true}))})()")
        click('.el-dialog__footer button','确认预约')
        check('提交前显示确认摘要',"document.querySelector('.el-message-box').innerText.includes('头痛三天')")
        click('.el-message-box__btns button','返回修改')
        check('返回修改不提交预约',"!!document.querySelector('.el-dialog')")
        assert not STATE['appointments']
        STATE['conflict']=True
        click('.el-dialog__footer button','确认预约');click('.el-message-box__btns button','确认预约')
        check('号源冲突保留原因并刷新可选号源',"document.querySelectorAll('.patient-slot-options button').length===3&&document.querySelector('.el-dialog textarea').value==='头痛三天'&&!document.querySelector('.patient-slot-options .selected')")
        check('显示具体冲突原因',"[...document.querySelectorAll('.el-message--error')].some(x=>x.innerText.includes('已不可预约'))")
        STATE['conflict']=False
        click('.patient-slot-options button');click('.el-dialog__footer button','确认预约');click('.el-message-box__btns button','确认预约')
        check('预约成功显示回执且刷新余号',"document.querySelector('.booking-success').innerText.includes('APT-TEST-001')&&document.querySelector('.schedule-event-slots').innerText.includes('2')")
        assert len(STATE['appointments'])==1
        click('.booking-success button','查看我的预约')
        check('成功后进入我的预约查看新记录',"document.querySelector('h1').innerText==='我的预约'&&document.body.innerText.includes('头痛三天')")
        click('.page-heading button','预约挂号')
        check('我的预约挂号入口返回日历',"document.querySelector('h1').innerText==='排班预约'")
        chrome.viewport(390,844);time.sleep(.2)
        check('手机日历无横向溢出',"document.documentElement.scrollWidth<=innerWidth")
        print(f'{count} patient booking checks passed',flush=True)
    finally:
        chrome.close();server.shutdown();server.server_close()


if __name__=='__main__':main()
