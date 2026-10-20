"""排班日历浏览器回归：模拟 API，不依赖 Django，也不修改业务数据库。

先运行 cd frontend && npm run build，再运行 python verify_schedule_ui.py。
复用项目 verify_ui.py 的无头 Chrome 工具；截图输出到 /tmp/schedule-calendar-*。
"""
import base64
import json
import os
import threading
import time
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from verify_ui import Chrome

ROOT = Path(__file__).resolve().parent
DIST = Path(os.environ.get('SCHEDULE_DIST', str(ROOT / 'frontend' / 'dist')))
TODAY = date.today().isoformat()
FUTURE = (date.today() + timedelta(days=2)).isoformat()
STATE = {'role': 'admin', 'fail_page': False, 'reject_create': False, 'requests': []}
DOCTORS = [dict(id=i, full_name=f'测试医师{i}', department_id=1 if i < 101 else 2,
                department_name='内科' if i < 101 else '外科', title='主治医师', specialty='') for i in range(1, 102)]
DEPARTMENTS = [dict(id=i, name='内科' if i == 1 else '外科' if i == 2 else f'科室{i}') for i in range(1, 102)]


def schedule(i, day=TODAY, doctor=1):
    info = DOCTORS[doctor-1]
    return dict(id=i, doctor=doctor, doctor_name=info['full_name'], doctor_title=info['title'],
                department_id=info['department_id'], department_name=info['department_name'],
                date=day, start_time='09:00:00', end_time='12:00:00', time_range='09:00–12:00',
                slot_minutes=30, is_active=i % 2 == 1, total_slots=6, available_slots=4, booked_slots=2)


ROWS = [schedule(i, doctor=101 if i == 101 else 1) for i in range(1, 102)]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, data, status=200):
        content = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        url = urlparse(self.path)
        if not url.path.startswith('/api/v1/'):
            self.path = '/' + (url.path[len('/app/'):] if url.path.startswith('/app/assets/') else 'index.html')
            return super().do_GET()
        route = url.path[len('/api/v1/'):]
        params = parse_qs(url.query)
        STATE['requests'].append(route + '?' + url.query)
        if route == 'auth/me/':
            return self.reply(dict(id=1, username=STATE['role'], full_name='演示用户', role=STATE['role']))
        if route == 'doctors/me/':
            return self.reply(DOCTORS[0])
        if route == 'schedules/outpatient/':
            return self.reply(dict(count=0, results=[], slot_count=0, date_from=TODAY, date_to=TODAY))
        data = {'schedules/': ROWS, 'doctors/': DOCTORS, 'departments/': DEPARTMENTS}.get(route, [])
        if route == 'schedules/' and STATE['role'] == 'doctor':
            data = [row for row in data if row['doctor'] == 1]
        page, size = int(params.get('page', ['1'])[0]), int(params.get('page_size', ['20'])[0])
        if route == 'schedules/' and page == 2 and STATE['fail_page']:
            return self.reply({'detail': '模拟第二页加载失败'}, 500)
        self.reply(dict(count=len(data), results=data[(page-1)*size:page*size]))

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if STATE['reject_create']:
            return self.reply({'detail': '请求数据校验失败。', 'errors': {'non_field_errors': ['该医师在此时间段已有排班。']}}, 400)
        row = schedule(max(item['id'] for item in ROWS)+1, data['date'], data['doctor'])
        row.update(data, is_active=True)
        ROWS.append(row)
        self.reply(row, 201)

    def do_PATCH(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        row = next(item for item in ROWS if item['id'] == int(urlparse(self.path).path.rstrip('/').split('/')[-1]))
        row.update(data)
        self.reply(row)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *args, **kwargs: Handler(*args, directory=str(DIST), **kwargs))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    chrome = Chrome()
    count = 0

    def check(label, expression):
        nonlocal count
        assert chrome.evaluate(expression), label
        count += 1
        print('PASS', label, flush=True)

    def click(selector, text=None):
        chrome.evaluate(f"(()=>{{const items=[...document.querySelectorAll({json.dumps(selector)})];const node=items.find(x=>!{json.dumps(text)}||x.innerText.includes({json.dumps(text)}));if(!node)throw Error('missing button');node.click()}})()")
        time.sleep(.18)

    def select(index, label):
        click(f'.schedule-filters .el-select:nth-child({index}) .el-select__wrapper')
        chrome.evaluate(f"[...document.querySelectorAll('.el-select-dropdown__item')].find(x=>x.getBoundingClientRect().height&&x.innerText.includes({json.dumps(label)})).click()")
        time.sleep(.15)

    def go(path='/console/outpatient?tab=schedules'):
        chrome.goto(base+'/app'+path, .4)
        assert chrome.wait_for("document.querySelector('.schedule-panel')?.getAttribute('aria-busy')==='false'"), 'calendar not ready'

    try:
        chrome.send('Page.enable')
        chrome.viewport(1640, 1100)
        chrome.goto(base+'/app/login', .3)
        chrome.evaluate("localStorage.setItem('smart_medical_access','fixture');localStorage.setItem('smart_medical_user',JSON.stringify({id:1,username:'admin',full_name:'演示用户',role:'admin'}))")
        go()
        check('完整加载 101 条排班', "document.querySelector('.schedule-summary').innerText.includes('101')&&document.querySelectorAll('.schedule-event').length===101")
        check('医师和科室选项均遍历分页', "document.querySelector('.schedule-day.selected .schedule-day-previews').innerText.includes('另有 99 条')")
        assert any('doctors/?page=2' in item for item in STATE['requests'])
        assert any('departments/?status=active&page=2' in item for item in STATE['requests'])
        check('桌面左右布局且无横向溢出', "document.querySelector('.schedule-agenda').getBoundingClientRect().left>document.querySelector('.schedule-month').getBoundingClientRect().left+200&&document.documentElement.scrollWidth<=innerWidth")
        chrome.screenshot('/tmp/schedule-calendar-desktop.png')
        select(1, '外科')
        check('科室筛选包含第二页医师的排班', "document.querySelectorAll('.schedule-event').length===1&&document.querySelector('.schedule-event').innerText.includes('测试医师101')")
        select(2, '测试医师101')
        click('.schedule-agenda-head button')
        check('选日新建自动填入日期和医师', f"[...document.querySelectorAll('.el-dialog input')].some(x=>x.value==='{TODAY}')&&document.querySelector('.el-dialog').innerText.includes('测试医师101')")
        click('.el-dialog__footer button', '取消')
        click('.schedule-filters button', '重置筛选')
        select(3, '已关闭')
        check('状态筛选及关闭语义', "document.querySelectorAll('.schedule-event').length===50&&[...document.querySelectorAll('.schedule-closed-note')].every(x=>x.innerText.includes('不可预约'))")
        click('.schedule-filters button', '重置筛选')
        click('.schedule-event button', '关闭排班')
        check('关闭操作后刷新', "document.querySelector('.schedule-event').innerText.includes('已关闭')")
        click('.schedule-event button', '开放排班')
        check('开放操作后刷新', "document.querySelector('.schedule-event').innerText.includes('开放')&&!document.querySelector('.schedule-event').classList.contains('closed')")
        # Future date creation and structured API errors, entirely within fixtures.
        if FUTURE[:7] != TODAY[:7]:
            click('.schedule-month-nav button[aria-label="下个月"]')
        click(f'.schedule-day[aria-label^="{FUTURE}"]')
        click('.schedule-agenda-head button')
        click('.el-dialog .el-select__wrapper')
        chrome.evaluate("[...document.querySelectorAll('.el-select-dropdown__item')].find(x=>x.getBoundingClientRect().height&&x.innerText.includes('测试医师1 ·')).click()")
        STATE['reject_create'] = True
        click('.el-dialog__footer button', '生成排班')
        check('结构化冲突错误可见且保留弹窗', "document.querySelector('.el-message--error')?.innerText.includes('已有排班')&&!!document.querySelector('.el-dialog')")
        STATE['reject_create'] = False
        click('.el-dialog__footer button', '生成排班')
        check('新建成功定位日期和新排班', f"document.querySelector('.schedule-day.selected').getAttribute('aria-label').startsWith('{FUTURE}')&&document.querySelectorAll('.schedule-event').length===1")
        click('.schedule-month-nav button', '今天')
        click('.schedule-month-nav button[aria-label="上个月"]')
        check('历史日期无新建入口', "!document.querySelector('.schedule-agenda-head button')&&document.querySelector('.schedule-agenda-head').innerText.includes('仅供查看')")
        click('.schedule-month-nav button', '今天')
        check('今天导航恢复选中日期', f"document.querySelector('.schedule-day.selected').getAttribute('aria-label').startsWith('{TODAY}')")
        STATE['fail_page'] = True
        click('.schedule-toolbar button', '刷新排班')
        check('分页失败不呈现部分日历', "!!document.querySelector('.list-error')&&!document.querySelector('.schedule-panel')")
        STATE['fail_page'] = False
        click('.list-error button', '重试')
        check('失败重试恢复完整数据', "!!document.querySelector('.schedule-panel')")
        chrome.viewport(390, 844)
        time.sleep(.2)
        check('手机日历无横向溢出且详情在下方', "document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.schedule-agenda').getBoundingClientRect().top>document.querySelector('.schedule-month').getBoundingClientRect().top&&getComputedStyle(document.querySelector('.schedule-day-previews')).display==='none'")
        chrome.wait_for("!document.querySelector('.el-message')", timeout=6)
        shot=chrome.send('Page.captureScreenshot', {'format':'png','captureBeyondViewport':False})['data']
        Path('/tmp/schedule-calendar-mobile.png').write_bytes(base64.b64decode(shot))
        chrome.evaluate("document.querySelector('.schedule-day.selected').focus()")
        chrome.send('Input.dispatchKeyEvent', {'type':'keyDown', 'key':'Enter', 'code':'Enter', 'windowsVirtualKeyCode':13})
        chrome.send('Input.dispatchKeyEvent', {'type':'keyUp', 'key':'Enter', 'code':'Enter', 'windowsVirtualKeyCode':13})
        check('日期按钮可键盘访问', "document.activeElement.classList.contains('schedule-day')&&document.activeElement.getAttribute('aria-pressed')==='true'")
        STATE['role'] = 'doctor'
        chrome.evaluate("localStorage.setItem('smart_medical_user',JSON.stringify({id:1,username:'doctor',full_name:'演示医师',role:'doctor'}))")
        go('/doctor/outpatient?tab=schedule')
        check('医师仅显示本人排班且无医师科室筛选', "document.querySelectorAll('.schedule-filters .el-select').length===1&&[...document.querySelectorAll('.schedule-event h3')].every(x=>x.innerText.includes('测试医师1 '))")
        click('.schedule-agenda-head button')
        check('医师新建不提供其他医师选择', "!!document.querySelector('.el-dialog')&&![...document.querySelectorAll('.el-dialog .el-form-item__label')].some(x=>x.innerText.includes('出诊医师'))")
        click('.el-dialog__footer button', '取消')
        chrome.goto(base+'/app/doctor/outpatient?tab=visits', .4)
        check('门诊就诊页面保持原视图', "!!document.querySelector('.outpatient-board')&&!document.querySelector('.schedule-panel')")
        print(f'{count} checks passed; screenshots: /tmp/schedule-calendar-{{desktop,mobile}}.png')
    finally:
        chrome.close()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
