"""P0/P1 浏览器验收：医生工作区开单、岗位工作台、护士工作台、住院病志、报告二维码。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已生成。
用法：python verify_p0p1_ui.py
"""

import os
import sys
import time

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


results = []


def main():
    chrome = Chrome()
    try:
        chrome.send('Page.enable')
        chrome.send('Network.enable')
        chrome.viewport(1440, 1000)

        # 1. 岗位工作台
        for username, expected in [('schedule_staff', '科室排班'), ('admission_staff', '住院处'), ('cashier', '收费退费'), ('pharmacy', '药房发药'), ('tech', '医技执行')]:
            check(f'{username} 登录', login(chrome, username, 'Staff123!') == 'staff', '', results)
            chrome.goto(f'{BASE}/app/staff', 1.1)
            chrome.wait_for("document.querySelector('h1')")
            check(f'{username} 进入岗位工作台', chrome.evaluate("document.querySelector('h1')?.innerText") == expected, chrome.evaluate("document.querySelector('h1')?.innerText"), results)
        chrome.goto(f'{BASE}/app/staff', 1.0)
        chrome.screenshot(os.path.join(SHOTS, 'p0-staff-workspace.png'))

        # 2. 护士工作台
        check('护士登录', login(chrome, 'nurse', 'Nurse123!') == 'nurse', '', results)
        chrome.goto(f'{BASE}/app/nurse', 1.2)
        chrome.wait_for("document.querySelectorAll('.el-tabs__item').length>=3")
        tabs = chrome.evaluate("[...document.querySelectorAll('.el-tabs__item')].map(node=>node.innerText.trim())")
        check('护士工作台包含急诊/住院接诊/医嘱执行', all(any(key in tab for tab in tabs) for key in ('急诊登记', '住院接诊', '医嘱执行')), str(tabs), results)
        check('急诊登记表单可用', chrome.evaluate("document.querySelectorAll('.nurse-form .el-select').length>=3"), chrome.evaluate("document.querySelectorAll('.nurse-form .el-select').length"), results)
        chrome.screenshot(os.path.join(SHOTS, 'p0-nurse-workspace.png'))

        # 3. 医生工作区：医嘱页签、模板入口、开单按钮
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        appointment = chrome.evaluate("""(async()=>{const t=localStorage.getItem('smart_medical_access');const r=await fetch('/api/v1/appointments/?status=in_progress&page_size=30',{headers:{Authorization:'Bearer '+t}});const d=await r.json();const row=(d.results||[]).find(item=>item.record_id);return row?{id:row.id}:null})()""")
        check('找到已建档的接诊记录', bool(appointment and appointment.get('id')), str(appointment), results)
        if appointment and appointment.get('id'):
            chrome.goto(f"{BASE}/app/doctor/visits/{appointment['id']}", 1.3)
            chrome.wait_for("document.querySelectorAll('.el-tabs__item').length>=4")
            tabs = chrome.evaluate("[...document.querySelectorAll('.el-tabs__item')].map(node=>node.innerText.trim())")
            check('医生工作区包含本次病历与医嘱', any('本次病历' in tab for tab in tabs) and any('医嘱' in tab for tab in tabs), str(tabs), results)
            check('本次病历提供套用模板', chrome.evaluate("document.body.innerText.includes('套用模板')"), '', results)
            chrome.evaluate("(()=>{const t=[...document.querySelectorAll('.el-tabs__item')].find(node=>node.innerText.includes('医嘱'));t?.click()})()")
            time.sleep(0.5)
            actions = chrome.evaluate("[...document.querySelectorAll('.orders-actions button')].map(node=>node.innerText.trim())")
            check('医嘱页签内直接开具处方/检查/处置/住院', all(any(key in action for action in actions) for key in ('处方', '检查', '处置', '住院')), str(actions), results)
            chrome.screenshot(os.path.join(SHOTS, 'p0-doctor-orders.png'))

        # 4. 住院病志与长期/临时医嘱
        admitted = chrome.evaluate("""(async()=>{const t=localStorage.getItem('smart_medical_access');const r=await fetch('/api/v1/inpatients/?status=admitted&page_size=5',{headers:{Authorization:'Bearer '+t}});const d=await r.json();return (d.results||[])[0]||null})()""")
        if admitted:
            chrome.goto(f"{BASE}/app/inpatient/{admitted['id']}", 1.2)
            chrome.wait_for("document.querySelectorAll('.el-tabs__item').length>=3")
            inpatient_tabs = chrome.evaluate("[...document.querySelectorAll('.el-tabs__item')].map(node=>node.innerText.trim())")
            check('住院工作区包含病志与长期/临时医嘱', any('住院病志' in tab for tab in inpatient_tabs) and any('长期医嘱' in tab for tab in inpatient_tabs) and any('临时医嘱' in tab for tab in inpatient_tabs), str(inpatient_tabs), results)
            chrome.screenshot(os.path.join(SHOTS, 'p0-inpatient-workspace.png'))

        # 5. 患者报告二维码
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/records?tab=reports', 1.4)
        chrome.wait_for("document.querySelectorAll('.report-card').length>0")
        chrome.evaluate("document.querySelector('.report-card')?.click()")
        chrome.wait_for("document.querySelector('.report-paper')")
        chrome.wait_for("!!document.querySelector('.report-share img')", timeout=8)
        check('报告阅读器生成分享二维码', chrome.evaluate("!!document.querySelector('.report-share img')"), chrome.evaluate("document.querySelector('.report-share')?.innerText.replace(/\\n+/g,' | ').slice(0,80)"), results)
        chrome.screenshot(os.path.join(SHOTS, 'p0-report-qr.png'))

        # 6. 窄屏
        chrome.viewport(375, 900)
        chrome.goto(f'{BASE}/app/staff', 1.0)
        time.sleep(0.5)
        check('岗位工作台窄屏不横向溢出', not chrome.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'), f"{chrome.evaluate('document.documentElement.scrollWidth')} / {chrome.evaluate('window.innerWidth')}", results)
    finally:
        chrome.close()
    failed = [row for row in results if not row[1]]
    print(f"\nP0/P1 验收：{len(results) - len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
