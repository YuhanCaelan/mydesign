"""卡片视图浏览器验收：档案、接诊、病历、检查、住院、费用、药品与审计。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已重建。
用法：python verify_cards_ui.py
"""

import os
import time

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


def click_tab(chrome, label):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('.folder-tab,.el-tabs__item')].find(item=>item.innerText.includes('{label}'));
      if(!node)return false;node.click();return true;
    }})()""")


def switch_view(chrome, label):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('.view-switch button')].find(item=>item.innerText.trim()==='{label}');
      if(!node)return false;node.click();return true;
    }})()""")


def active_view(chrome):
    return chrome.evaluate("document.querySelector('.view-switch button.active')?.innerText.trim()||''")


def main():
    results = []
    chrome = Chrome()
    try:
        chrome.send('Page.enable')
        chrome.viewport(1440, 1000)

        # 1. 管理员：档案卡、管理列表、时间轴与状态分组
        check('管理员登录', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        chrome.goto(f'{BASE}/app/console/people?tab=doctors', 1.0)
        chrome.wait_for("document.querySelectorAll('.entity-card').length>0")
        people = chrome.evaluate("(()=>({cards:document.querySelectorAll('.entity-card').length,view:document.querySelector('.view-switch button.active')?.innerText.trim(),status:document.querySelectorAll('.entity-card .el-tag').length}))()")
        check('医师档案默认头像卡片并保留状态', people['cards'] == 6 and people['view'] == '卡片' and people['status'] > 0, str(people), results)
        switch_view(chrome, '列表')
        chrome.wait_for("document.querySelectorAll('.el-table__body tbody tr').length>0")
        check('管理员可切换紧凑档案列表', active_view(chrome) == '列表' and chrome.evaluate("document.querySelectorAll('.el-table__body tbody tr').length") > 0, '', results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-people-list.png'))
        click_tab(chrome, '患者账户')
        chrome.wait_for("document.querySelectorAll('.entity-card').length>0")
        chrome.evaluate("[...document.querySelectorAll('.el-pager li.number')].find(node=>node.innerText.trim()==='2')?.click()")
        chrome.wait_for("document.querySelectorAll('.entity-card').length===2")
        switch_view(chrome, '列表')
        chrome.wait_for("document.querySelectorAll('.el-table__body tbody tr').length===2")
        paged = chrome.evaluate("(()=>({page:document.querySelector('.el-pager li.is-active,.el-pager li.active')?.innerText.trim(),rows:document.querySelectorAll('.el-table__body tbody tr').length}))()")
        check('切换视图保留患者账户页码与数据', paged['page'] == '2' and paged['rows'] == 2, str(paged), results)

        chrome.goto(f'{BASE}/app/console/clinical?tab=medicines', 1.0)
        chrome.wait_for("document.querySelectorAll('.el-table__body tbody tr').length>0")
        medicine_list = chrome.evaluate("(()=>({view:document.querySelector('.view-switch button.active')?.innerText.trim(),rows:document.querySelectorAll('.el-table__body tbody tr').length}))()")
        check('管理员药品库存默认紧凑列表', medicine_list['view'] == '列表' and medicine_list['rows'] > 0, str(medicine_list), results)

        chrome.goto(f'{BASE}/app/console/operations?tab=audit', 1.0)
        chrome.wait_for("document.querySelectorAll('.event-card').length>0")
        audit = chrome.evaluate("(()=>({cards:document.querySelectorAll('.event-card').length,time:document.querySelectorAll('.event-time').length,meta:document.body.innerText.includes('操作人')&&document.body.innerText.includes('动作')}))()")
        check('审计默认时间轴事件卡并展示操作人/动作', audit['cards'] > 0 and audit['time'] > 0 and audit['meta'], str(audit), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-audit-timeline.png'))

        chrome.goto(f'{BASE}/app/console/inpatient?tab=admissions', 1.0)
        chrome.wait_for("document.querySelectorAll('.task-group').length>0")
        admissions = chrome.evaluate("(()=>({groups:[...document.querySelectorAll('.task-group-head h2')].map(node=>node.innerText.trim()),cards:document.querySelectorAll('.task-card').length,bedLink:[...document.querySelectorAll('button')].some(node=>node.innerText.includes('床位总览'))}))()")
        check('住院管理按状态归组患者卡并保留床位总览入口', admissions['cards'] > 0 and '住院中' in admissions['groups'] and admissions['bedLink'], str(admissions), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-inpatients.png'))

        # 2. 医师：日期轴接诊队列、病历时间轴、检查任务分组
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        chrome.goto(f'{BASE}/app/doctor/outpatient?tab=appointments', 1.0)
        chrome.wait_for("document.querySelectorAll('.task-card').length>0")
        queue = chrome.evaluate("(()=>({axis:document.querySelectorAll('.date-axis button').length,labels:[...document.querySelectorAll('.date-axis button')].map(node=>node.innerText.replace(/\\n/g,' ')),cards:document.querySelectorAll('.task-card').length,highlight:document.querySelectorAll('.task-card[data-highlight=\"true\"]').length,next:document.body.innerText.includes('下一位')||document.body.innerText.includes('诊疗中')}))()")
        check('医师接诊默认日期轴与高亮队列卡', queue['axis'] == 8 and queue['cards'] > 0 and queue['highlight'] == 1 and queue['next'], str(queue), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-reception-queue.png'))

        chrome.goto(f'{BASE}/app/doctor/clinical?tab=records', 1.0)
        chrome.wait_for("document.querySelectorAll('.event-card').length>0")
        records = chrome.evaluate("(()=>({cards:document.querySelectorAll('.event-card').length,status:document.querySelectorAll('.event-card .el-tag').length,actions:[...document.querySelectorAll('.event-card button')].map(node=>node.innerText.trim())}))()")
        check('病历默认就诊时间轴卡并保留确认/更正操作', records['cards'] > 0 and records['status'] > 0 and any('查看' in item for item in records['actions']), str(records), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-record-timeline.png'))

        chrome.goto(f'{BASE}/app/doctor/clinical?tab=examinations', 1.0)
        chrome.wait_for("document.querySelectorAll('.task-group').length>0")
        exams = chrome.evaluate("(()=>({groups:[...document.querySelectorAll('.task-group-head h2')].map(node=>node.innerText.trim()),cards:document.querySelectorAll('.task-card').length,actions:document.querySelectorAll('.task-card button').length}))()")
        check('检查按状态归组任务卡并保留报告操作', exams['cards'] > 0 and len(exams['groups']) >= 1 and exams['actions'] > 0, str(exams), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-examinations.png'))

        chrome.goto(f'{BASE}/app/doctor/clinical?tab=medicines', 1.0)
        chrome.wait_for("document.querySelectorAll('.entity-card').length>0")
        medicines = chrome.evaluate("(()=>({view:document.querySelector('.view-switch button.active')?.innerText.trim(),cards:document.querySelectorAll('.entity-card').length,price:document.body.innerText.includes('单价'),stock:document.body.innerText.includes('库存')}))()")
        check('医师药品目录默认目录卡', medicines['view'] == '卡片' and medicines['cards'] > 0 and medicines['price'] and medicines['stock'], str(medicines), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-medicines.png'))

        # 3. 患者：费用账本卡、药品目录卡、病历时间轴
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/finance?tab=bills', 1.0)
        chrome.wait_for("document.querySelectorAll('.ledger-card').length>0")
        bills = chrome.evaluate("(()=>({groups:document.querySelectorAll('.ledger-group').length,dates:[...document.querySelectorAll('.ledger-group-head h3')].map(node=>node.innerText.trim()),cards:document.querySelectorAll('.ledger-card').length,amount:document.querySelectorAll('.ledger-amount').length,note:document.body.innerText.includes('不计入日期合计')}))()")
        check('患者费用默认按日期归组账本卡', bills['groups'] > 0 and bills['cards'] > 0 and bills['amount'] == bills['cards'] and bills['note'], str(bills), results)
        chrome.screenshot(os.path.join(SHOTS, 'cards-billing-ledger.png'))

        chrome.goto(f'{BASE}/app/patient/care?tab=records', 1.0)
        chrome.wait_for("document.querySelectorAll('.event-card').length>0")
        timeline = chrome.evaluate("(()=>({cards:document.querySelectorAll('.event-card').length,view:document.querySelector('.view-switch button.active')?.innerText.trim(),hasDate:Boolean(document.querySelector('.event-time')?.innerText.trim())}))()")
        check('患者病历默认按就诊时间轴展示', timeline['cards'] > 0 and timeline['view'] == '卡片' and timeline['hasDate'], str(timeline), results)

        # 4. 窄屏卡片不横向溢出
        chrome.goto(f'{BASE}/app/patient/care?tab=admissions', 0.8)
        chrome.wait_for("document.querySelectorAll('.task-card').length>0")
        chrome.viewport(375, 900)
        time.sleep(0.7)
        grouped_mobile = chrome.evaluate("(()=>({overflow:document.documentElement.scrollWidth>window.innerWidth+1,cards:document.querySelectorAll('.task-card').length,groups:document.querySelectorAll('.task-group').length}))()")
        check('窄屏住院状态分组卡无横向溢出', not grouped_mobile['overflow'] and grouped_mobile['cards'] > 0 and grouped_mobile['groups'] > 0, str(grouped_mobile), results)
        chrome.viewport(1440, 1000)
        chrome.goto(f'{BASE}/app/patient/finance?tab=bills', 0.8)
        chrome.viewport(375, 900)
        time.sleep(0.7)
        narrow = chrome.evaluate("(()=>({overflow:document.documentElement.scrollWidth>window.innerWidth+1,cards:document.querySelectorAll('.ledger-card').length,columns:getComputedStyle(document.querySelector('.ledger-card')).gridTemplateColumns}))()")
        check('窄屏账本卡单列且无横向溢出', not narrow['overflow'] and narrow['cards'] > 0 and ' ' not in narrow['columns'].strip(), str(narrow), results)
        chrome.viewport(1440, 1000)
    finally:
        chrome.close()
    print(f"\n卡片视图验收：{sum(1 for _,ok,_ in results if ok)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 0 if all(ok for _,ok,_ in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
