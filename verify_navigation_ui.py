"""导航与前端体验验收：主栏目、文件夹页签、旧链接、状态/错误、预约步骤、返回上下文与窄屏。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已重建。
用法：python verify_navigation_ui.py
"""

import os
import sys
import time
import urllib.parse

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


def route_state(chrome):
    return chrome.evaluate("(()=>({path:location.pathname,search:location.search,hash:location.hash}))()")


def click_text(chrome, selector, text):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('{selector}')].find(item=>item.innerText.includes('{text}'));
      if(!node)return false;node.click();return true;
    }})()""")


def select_last_dropdown_option(chrome, text=None):
    expression = f"[...drop.querySelectorAll('.el-select-dropdown__item')].find(node=>node.innerText.includes('{text}'))" if text else "options[0]"
    return chrome.evaluate(f"""(() => {{
      const drops=[...document.querySelectorAll('.el-select-dropdown')].filter(node=>node.getBoundingClientRect().height>0);
      const drop=drops[drops.length-1];if(!drop)return false;
      const options=[...drop.querySelectorAll('.el-select-dropdown__item')];
      const option={expression};
      if(!option)return false;option.click();return option.innerText.trim();
    }})()""")


def active_sidebar(chrome):
    return chrome.evaluate("[...document.querySelectorAll('.app-nav nav a.active')].map(node=>node.innerText.trim())")


def main():
    results = []
    chrome = Chrome()
    try:
        chrome.send('Page.enable');chrome.send('Network.enable');chrome.viewport(1440, 1000)

        # 1. 管理员主栏目与工作台快捷入口
        check('管理员登录', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        chrome.goto(f'{BASE}/app/dashboard', 1.0)
        sidebar = chrome.evaluate("[...document.querySelectorAll('.app-nav nav a')].map(node=>node.innerText.trim())")
        check('管理员只看到系统主栏目', sidebar == ['工作台', '账号与科室', '基础字典', '审计日志'], str(sidebar), results)
        quick = chrome.evaluate("[...document.querySelectorAll('.quick-panel a')].map(node=>({text:node.innerText.trim(),href:node.getAttribute('href')}))")
        check('工作台快捷操作指向新子页', all('?tab=' in (item['href'] or '') for item in quick) and len(quick) == 4, str(quick), results)
        alerts = chrome.evaluate("[...document.querySelectorAll('.attention-panel a')].map(node=>node.getAttribute('href'))")
        check('工作台待办卡片指向新子页', bool(alerts) and all('?tab=' in (href or '') for href in alerts), str(alerts), results)
        click_text(chrome, '.quick-panel a', '排班设置');time.sleep(0.6)
        state = route_state(chrome)
        check('点击快捷操作进入准确子页', state['path'] == '/app/console/outpatient' and 'tab=schedules' in state['search'], str(state), results)

        # 2. 文件夹页签：选中态、URL、刷新、无效回退、键盘
        chrome.goto(f'{BASE}/app/console/people', 0.9)
        chrome.wait_for("document.querySelectorAll('.folder-tab').length===3")
        tabs = chrome.evaluate("[...document.querySelectorAll('.folder-tab')].map(node=>({text:node.innerText.trim(),selected:node.getAttribute('aria-selected')}))")
        check('文件夹页签展示并标出选中态', len(tabs) == 3 and tabs[0]['selected'] == 'true', str(tabs), results)
        click_text(chrome, '.folder-tab', '患者账户');time.sleep(0.6)
        state = route_state(chrome)
        check('点击页签更新网址', state['path'] == '/app/console/people' and 'tab=patients' in state['search'], str(state), results)
        check('页签切换后内容归属正确', chrome.evaluate("document.querySelector('h1')?.innerText") == '患者账户', chrome.evaluate("document.querySelector('h1')?.innerText"), results)
        chrome.goto(f"{BASE}{state['path']}{state['search']}", 0.9)
        check('刷新后保持选中页签', chrome.evaluate("document.querySelector('.folder-tab.active')?.innerText.trim()") == '患者账户', chrome.evaluate("document.querySelector('.folder-tab.active')?.innerText.trim()"), results)
        chrome.goto(f'{BASE}/app/console/people?tab=bogus', 0.9)
        chrome.wait_for("document.querySelector('.folder-tab.active')?.innerText.includes('医师账户')")
        state = route_state(chrome)
        check('无效页签安全回到默认页', 'tab=doctors' in state['search'] and chrome.evaluate("document.querySelector('.folder-tab.active')?.innerText.trim()") == '医师账户', str(state), results)
        keyboard = chrome.evaluate("""(async()=>{
          const active=document.querySelector('.folder-tab.active');active.focus();
          active.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
          await new Promise(resolve=>setTimeout(resolve,350));
          return {focused:document.activeElement?.className,selected:document.querySelector('.folder-tab.active')?.innerText.trim(),search:location.search};
        })()""")
        check('页签支持键盘左右切换并保持焦点', 'folder-tab' in (keyboard['focused'] or '') and keyboard['selected'] == '患者账户' and 'tab=patients' in keyboard['search'], str(keyboard), results)
        chrome.screenshot(os.path.join(SHOTS, 'navigation-folder-tabs.png'))

        # 3. 旧地址与查询参数
        legacy = [
            ('/app/console/appointments?foo=bar', '/app/console/outpatient', ['tab=appointments', 'foo=bar']),
            ('/app/console/schedules', '/app/console/outpatient', ['tab=schedules']),
            ('/app/console/resources?tab=exams', '/app/console/clinical', ['tab=exam-items']),
            ('/app/console/resources?tab=movements', '/app/console/clinical', ['tab=stock']),
            ('/app/console/resources?tab=beds', '/app/console/inpatient', ['tab=bed-config']),
            ('/app/console/bed-board', '/app/console/inpatient', ['tab=beds']),
            ('/app/console/billing', '/app/console/operations', ['tab=bills']),
            ('/app/console/audit-logs', '/app/console/operations', ['tab=audit']),
        ]
        for path, expected_path, expected_query in legacy:
            chrome.goto(f'{BASE}{path}', 0.7)
            state = route_state(chrome)
            parsed = urllib.parse.parse_qs(state['search'].lstrip('?'))
            queries_ok = all(query.split('=')[1] in parsed.get(query.split('=')[0], []) for query in expected_query)
            check(f'旧地址 {path} 重定向正确', state['path'] == expected_path and queries_ok, f"{state['path']}{state['search']}", results)

        # 4. 床位看板精简
        chrome.goto(f'{BASE}/app/console/inpatient?tab=beds', 0.9)
        chrome.wait_for("document.querySelectorAll('.bed-card').length>0")
        board = chrome.evaluate("""(() => ({
          departments:document.querySelectorAll('.bed-department').length,
          cards:document.querySelectorAll('.bed-card').length,
          filters:document.querySelectorAll('.board-filter-card').length,
          segmented:document.querySelectorAll('.bed-board .el-segmented').length,
          config:[...document.querySelectorAll('a')].some(node=>node.innerText.includes('床位配置'))
        }))()""")
        check('床位看板仅保留科室/病区/床位视图且无查询区', board['departments'] >= 6 and board['cards'] == 48 and board['filters'] == 0 and board['segmented'] == 0, str(board), results)
        chrome.screenshot(os.path.join(SHOTS, 'bed-board-departments-only.png'))
        check('管理员床位配置入口可用', board['config'], str(board['config']), results)
        check('业务页面不进入管理员主栏目', active_sidebar(chrome) == [], str(active_sidebar(chrome)), results)
        # 从床位下钻并返回
        chrome.evaluate("(()=>{const card=[...document.querySelectorAll('.bed-card')].find(node=>node.dataset.status==='occupied');card?.click()})()")
        chrome.wait_for("document.querySelector('.el-drawer .record-detail')")
        href = chrome.evaluate("(()=>{const a=document.querySelector('.el-drawer a[href*=\"/inpatients/\"]');return a?a.getAttribute('href'):null})()")
        check('床位详情可进入住院详情并携带返回上下文', bool(href) and 'returnTo=' in (href or ''), str(href), results)
        if href:
            chrome.goto(f'{BASE}{href}', 0.8)
            check('住院详情不进入管理员主栏目', active_sidebar(chrome) == [], str(active_sidebar(chrome)), results)
            click_text(chrome, 'button', '返回');time.sleep(0.7)
            state = route_state(chrome)
            check('住院详情返回原床位子页', state['path'] == '/app/console/inpatient' and 'tab=beds' in state['search'], str(state), results)

        # 5. 请求失败与空数据区分
        chrome.send('Network.setBlockedURLs', {'urls': ['*api/v1/appointments*']})
        chrome.goto(f'{BASE}/app/console/outpatient?tab=appointments', 1.0)
        chrome.wait_for("document.querySelector('.list-error')", timeout=8)
        failed = chrome.evaluate("(()=>({text:document.querySelector('.list-error')?.innerText||'',retry:Boolean(document.querySelector('.list-error button'))}))()")
        check('请求失败显示错误与重试而非空数据', '加载失败' in failed['text'] and failed['retry'], failed['text'].replace('\n', ' | ')[:120], results)
        chrome.send('Network.setBlockedURLs', {'urls': []})
        click_text(chrome, '.list-error button', '重试')
        chrome.wait_for("document.querySelectorAll('.task-card').length>0", timeout=8)
        check('重试后恢复接诊队列卡片', chrome.evaluate("document.querySelectorAll('.task-card').length") > 0, '', results)

        # 6. 医师：页签、返回上下文、状态保持
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        chrome.goto(f'{BASE}/app/dashboard', 0.8)
        sidebar = chrome.evaluate("[...document.querySelectorAll('.app-nav nav a')].map(node=>node.innerText.trim())")
        check('医师只看到诊疗主栏目', sidebar == ['工作台', '接诊工作', '诊疗档案', '诊疗资料', '住院工作'], str(sidebar), results)
        chrome.goto(f'{BASE}/app/doctor/outpatient?tab=appointments', 1.0)
        chrome.wait_for("document.querySelectorAll('.task-card').length>0")
        queue = chrome.evaluate("(()=>({cards:document.querySelectorAll('.task-card').length,highlight:document.querySelectorAll('.task-card[data-highlight=\"true\"]').length,axis:document.querySelectorAll('.date-axis button').length}))()")
        check('接诊页默认展示日期轴与队列卡片', queue['cards'] > 0 and queue['axis'] == 8, str(queue), results)
        chrome.evaluate("(()=>{const s=document.querySelector('.table-tools .el-select__wrapper');s?.click()})()");time.sleep(0.4)
        select_last_dropdown_option(chrome, '就诊中');time.sleep(0.8)
        chrome.wait_for("document.querySelectorAll('.task-card').length>0")
        check('医师可按状态筛选接诊列表', chrome.evaluate("document.querySelector('.table-tools .el-select')?.innerText.includes('就诊中')"), chrome.evaluate("document.querySelector('.table-tools .el-select')?.innerText.trim()"), results)
        click_text(chrome, '.task-card button', '工作区');time.sleep(0.9)
        state = route_state(chrome)
        check('从接诊列表进入诊疗工作区', state['path'].startswith('/app/doctor/visits/') and 'returnTo=' in state['search'], str(state), results)
        check('诊疗工作区高亮接诊工作', active_sidebar(chrome) == ['接诊工作'], str(active_sidebar(chrome)), results)
        click_text(chrome, 'button', '返回接诊列表');time.sleep(0.9)
        state = route_state(chrome)
        restored = chrome.evaluate("document.querySelector('.table-tools .el-select')?.innerText.trim()")
        check('接诊工作区返回原子页并保留筛选条件', state['path'] == '/app/doctor/outpatient' and 'tab=appointments' in state['search'] and '就诊中' in (restored or ''), f"{state} / {restored}", results)
        chrome.goto(f'{BASE}/app/doctor/clinical?tab=smart', 0.9)
        smart = chrome.evaluate("(()=>({dead:[...document.querySelectorAll('button')].some(node=>node.innerText.includes('进入服务')),note:document.body.innerText.includes('接口预留')}))()")
        check('智慧服务无无响应的“进入服务”按钮', not smart['dead'] and smart['note'], str(smart), results)

        # 7. 患者：排班日历预约与号源选择
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/visits?tab=doctors', 1.2)
        chrome.wait_for("document.querySelector('.schedule-panel')")
        calendar=chrome.evaluate("(()=>({days:document.querySelectorAll('.schedule-day').length,events:document.querySelectorAll('.schedule-event').length,filters:document.querySelectorAll('.schedule-filters .el-select').length,note:document.querySelector('.schedule-hint')?.innerText||''}))()")
        check('患者按排班日历选择日期与医师', calendar['days']>=28 and calendar['events']>0 and calendar['filters']>=2, str(calendar), results)
        chrome.evaluate("""(()=>{const days=[...document.querySelectorAll('.schedule-day')];const target=days.find(day=>/([1-9]\\d*) 个余号/.test(day.innerText));target?.click()})()""");time.sleep(1.0)
        chrome.evaluate("(()=>{const event=[...document.querySelectorAll('.schedule-event')].find(node=>{const button=node.querySelector('button');return button&&button.innerText.includes('选择号源')&&!button.disabled});event?.querySelector('button')?.click()})()");time.sleep(1.0)
        dialog=chrome.evaluate("(()=>({open:!!document.querySelector('.el-dialog'),slots:document.querySelectorAll('.el-dialog .slot-list button').length,summary:document.querySelector('.patient-booking-context')?.innerText.replace(/\\n+/g,' | ')||''}))()")
        check('选择号源打开预约对话框', dialog['open'] and dialog['slots']>0, str(dialog), results)
        check('预约对话框展示科室、医师与日期', all(key in dialog['summary'] for key in ('·','每号')), dialog['summary'][:120], results)
        if dialog['open']:
            chrome.evaluate("document.querySelector('.el-dialog .slot-list button')?.click()");time.sleep(0.3)
            summary=chrome.evaluate("document.querySelector('.booking-summary')?.innerText.replace(/\\n+/g,' | ')||''")
            check('提交前展示预约摘要', '预约摘要' in summary and '·' in summary, summary[:120], results)
            click_text(chrome, '.el-dialog button', '取消');time.sleep(0.3)

        # 8. 患者状态保持与窄屏信息卡
        chrome.goto(f'{BASE}/app/patient/visits?tab=appointments', 1.0)
        chrome.wait_for("document.querySelectorAll('.task-card').length>0")
        chrome.evaluate("document.querySelector('.table-tools .el-select__wrapper')?.click()");time.sleep(0.4)
        select_last_dropdown_option(chrome, '已完成');time.sleep(0.8)
        click_text(chrome, '.folder-tab', '医师查询');time.sleep(0.6)
        click_text(chrome, '.folder-tab', '我的预约');time.sleep(1.0)
        kept = chrome.evaluate("document.querySelector('.table-tools .el-select')?.innerText.trim()")
        check('切换子页后保留本次会话筛选条件', '已完成' in (kept or ''), str(kept), results)
        click_text(chrome, '.view-switch button', '列表');time.sleep(0.5)
        switched = chrome.evaluate("(()=>({filter:document.querySelector('.table-tools .el-select')?.innerText.trim()||'',table:document.querySelectorAll('.desktop-table .el-table__body tbody tr').length}))()")
        check('切换卡片/列表不重置筛选与数据', '已完成' in switched['filter'] and switched['table'] > 0, str(switched), results)
        click_text(chrome, '.view-switch button', '卡片');time.sleep(0.5)
        check('切回卡片后仍保留筛选条件', '已完成' in chrome.evaluate("document.querySelector('.table-tools .el-select')?.innerText.trim()||''"), '', results)
        chrome.goto(f'{BASE}/app/patient/finance?tab=bills', 0.9)
        chrome.wait_for("document.querySelectorAll('.ledger-card').length>0")
        chrome.viewport(375, 900);time.sleep(0.6)
        mobile = chrome.evaluate("""(() => ({
          groups:document.querySelectorAll('.ledger-group').length,
          cards:document.querySelectorAll('.ledger-card').length,
          overflow:document.documentElement.scrollWidth>window.innerWidth+1
        }))()""")
        check('窄屏账单按日期归组为账本卡且不横向溢出', mobile['groups'] > 0 and mobile['cards'] > 0 and not mobile['overflow'], str(mobile), results)
        chrome.screenshot(os.path.join(SHOTS, 'mobile-billing-ledger.png'))
        chrome.viewport(1440, 1000)
        chrome.goto(f'{BASE}/app/patient/care?tab=smart', 0.9)
        smart = chrome.evaluate("(()=>({dead:[...document.querySelectorAll('button')].some(node=>node.innerText.includes('进入服务')),note:document.body.innerText.includes('接口预留')}))()")
        check('患者智慧服务显示预留说明且无空按钮', not smart['dead'] and smart['note'], str(smart), results)

        # 9. 患者旧地址与 smart 重定向
        for path, expected_path, expected_tab in [
            ('/app/patient/appointments?department=1&doctor=1', '/app/patient/visits', 'doctors'),
            ('/app/patient/appointments', '/app/patient/visits', 'appointments'),
            ('/app/patient/billing', '/app/patient/finance', 'bills'),
            ('/app/smart/services', '/app/patient/care', 'smart'),
        ]:
            chrome.goto(f'{BASE}{path}', 0.9)
            state = route_state(chrome)
            check(f'患者旧地址 {path} 重定向正确', state['path'] == expected_path and f'tab={expected_tab}' in state['search'], f"{state['path']}{state['search']}", results)

    finally:
        chrome.close()
    failed = [row for row in results if not row[1]]
    print(f"\n导航与体验验收：{len(results) - len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
