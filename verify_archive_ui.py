"""诊疗档案浏览器验收：患者/医师快速查看历史病历与检查报告。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已生成。
用法：python verify_archive_ui.py
"""

import os
import sys
import time
import urllib.parse

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


def click_text(chrome, selector, text):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('{selector}')].find(item=>item.innerText.includes('{text}'));
      if(!node)return false;node.click();return true;
    }})()""")


def route_state(chrome):
    return chrome.evaluate("(()=>({path:location.pathname,search:location.search,hash:location.hash}))()")


def sidebar_active(chrome):
    return chrome.evaluate("[...document.querySelectorAll('.app-nav nav a.active')].map(node=>node.innerText.trim())")


def main():
    results = []
    chrome = Chrome()
    try:
        chrome.send('Page.enable')
        chrome.send('Network.enable')
        chrome.viewport(1440, 1000)

        # 1. 患者：一级入口、病历时间轴、病历阅读器
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/records', 1.6)
        chrome.wait_for("document.querySelector('.archive-patient')")
        check('患者诊疗档案一级入口可直接到达', route_state(chrome)['path'] == '/app/patient/records', str(route_state(chrome)), results)
        check('侧栏高亮诊疗档案', sidebar_active(chrome) == ['诊疗档案'], str(sidebar_active(chrome)), results)
        check('默认展示历史病历页签', chrome.evaluate("document.querySelector('.folder-tab.active')?.innerText.includes('历史病历')"), chrome.evaluate("document.querySelector('.folder-tab.active')?.innerText.trim()"), results)
        check('历史病历按年月分组', chrome.evaluate("document.querySelectorAll('.archive-month').length") > 0, chrome.evaluate("document.querySelectorAll('.archive-month').length"), results)
        check('历史病历卡片首屏可见', chrome.evaluate("document.querySelectorAll('.record-card').length") >= 3, chrome.evaluate("document.querySelectorAll('.record-card').length"), results)
        check('患者端不显示患者选择栏', not chrome.evaluate("!!document.querySelector('.patient-rail')"), '', results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-patient-records.png'))

        chrome.evaluate("""(()=>{const cards=[...document.querySelectorAll('.record-card')];const target=cards.find(card=>card.innerText.includes('检查 '))||cards[0];target?.click()})()""")
        chrome.wait_for("document.querySelector('.record-paper')")
        sections = chrome.evaluate("[...document.querySelectorAll('.record-paper-section h3')].map(node=>node.innerText.trim())")
        check('病历阅读器展示完整字段', all(name in sections for name in ('主诉', '现病史', '既往史', '诊断', '处理意见')), str(sections), results)
        check('病历阅读器展示关联检查区', any('关联检查' in name for name in sections) or chrome.evaluate("document.querySelectorAll('.record-exam').length") > 0, str(sections), results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-record-reader.png'))
        bridged = click_text(chrome, 'button', '查看检查报告')
        if bridged:
            chrome.wait_for("document.querySelector('.report-paper')")
            check('病历阅读器可直达关联报告', chrome.evaluate("!!document.querySelector('.report-paper')"), '', results)
            check('关联报告打开后病历阅读器关闭', chrome.wait_for("!document.querySelector('.record-paper')", timeout=4), '', results)
            click_text(chrome, 'button', '关闭')
            time.sleep(0.5)
        else:
            chrome.evaluate("document.querySelector('.el-drawer__close-btn')?.click()")
            time.sleep(0.4)

        # 2. 患者：检查报告、A4 阅读器、深链
        check('切换到检查报告页签', click_text(chrome, '.folder-tab', '检查报告'), '', results)
        time.sleep(1.1)
        check('页签切换保留同一患者上下文', route_state(chrome)['path'] == '/app/patient/records' and 'tab=reports' in route_state(chrome)['search'], str(route_state(chrome)), results)
        chrome.wait_for("document.querySelectorAll('.report-card').length>0")
        report_count = chrome.evaluate("document.querySelectorAll('.report-card').length")
        check('报告卡片首屏可见', report_count >= 3, report_count, results)
        check('报告卡片直接展示结论', bool(chrome.evaluate("document.querySelector('.report-card-conclusion')?.innerText.trim()")), chrome.evaluate("document.querySelector('.report-card-conclusion')?.innerText.trim()"), results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-patient-reports.png'))

        chrome.evaluate("document.querySelector('.report-card')?.click()")
        chrome.wait_for("document.querySelector('.report-paper')")
        check('报告阅读器按 A4 纸张展示', chrome.evaluate("!!document.querySelector('.report-paper') && !!document.querySelector('.report-paper-conclusion')"), chrome.evaluate("document.querySelector('.report-paper-title')?.innerText.trim()"), results)
        open_state = route_state(chrome)
        query = urllib.parse.parse_qs(open_state['search'].lstrip('?'))
        report_no = (query.get('report') or [''])[0]
        check('打开报告写入可分享 URL', bool(report_no), report_no, results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-report-reader.png'))
        click_text(chrome, 'button', '关闭')
        time.sleep(0.5)

        if report_no:
            chrome.goto(f"{BASE}/app/patient/records?tab=reports&report={report_no}", 1.4)
            chrome.wait_for("document.querySelector('.report-paper')")
            check('报告深链可直接打开阅读器', chrome.evaluate("!!document.querySelector('.report-paper')"), report_no, results)
            click_text(chrome, 'button', '关闭')
            time.sleep(0.4)

        # 3. 旧地址兼容
        for path, expected_path, expected_tab in [
            ('/app/patient/care?tab=records', '/app/patient/records', 'tab=records'),
            ('/app/patient/care?tab=reports', '/app/patient/records', 'tab=reports'),
            ('/app/patient/reports', '/app/patient/records', 'tab=reports'),
        ]:
            chrome.goto(f'{BASE}{path}', 0.9)
            state = route_state(chrome)
            check(f'患者旧地址 {path} 重定向正确', state['path'] == expected_path and expected_tab in state['search'], f"{state['path']}{state['search']}", results)

        # 4. 医师：患者选择、病历与报告
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        chrome.goto(f'{BASE}/app/doctor/records', 1.5)
        chrome.wait_for("document.querySelector('.patient-rail')")
        check('医师端默认提示选择患者', chrome.evaluate("!!document.querySelector('.archive-placeholder')"), '', results)
        rail_count = chrome.evaluate("document.querySelectorAll('.patient-rail-item').length")
        check('医师端患者栏有可访问患者', rail_count > 0, rail_count, results)
        chrome.evaluate("document.querySelector('.patient-rail-item')?.click()")
        chrome.wait_for("document.querySelector('.archive-patient')")
        selected = route_state(chrome)
        check('选择患者写入 URL 并可刷新', 'patient=' in selected['search'], str(selected), results)
        check('医师端展示患者信息带', chrome.evaluate("document.querySelector('.archive-patient')?.innerText.includes('过敏史')"), chrome.evaluate("document.querySelector('.archive-patient')?.innerText.replace(/\\n+/g,' | ').slice(0,120)"), results)
        check('医师端病历时间轴可见', chrome.evaluate("document.querySelectorAll('.record-card').length") >= 3, chrome.evaluate("document.querySelectorAll('.record-card').length"), results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-doctor-records.png'))

        check('医师切换到检查报告', click_text(chrome, '.folder-tab', '检查报告'), '', results)
        time.sleep(1.1)
        chrome.wait_for("document.querySelectorAll('.report-card').length>0")
        check('医师端报告时间轴可见', chrome.evaluate("document.querySelectorAll('.report-card').length") >= 3, chrome.evaluate("document.querySelectorAll('.report-card').length"), results)
        check('医师端可见报告状态筛选', chrome.evaluate("[...document.querySelectorAll('.archive-toolbar .el-select')].some(node=>node.innerText.includes('全部状态'))"), '', results)
        chrome.evaluate("document.querySelector('.report-card')?.click()")
        chrome.wait_for("document.querySelector('.report-paper')")
        check('医师端可打开报告阅读器', chrome.evaluate("!!document.querySelector('.report-paper')"), '', results)
        click_text(chrome, 'button', '关闭')
        time.sleep(0.4)

        # 5. 窄屏
        chrome.goto(f'{BASE}/app/doctor/records?tab=reports', 1.2)
        chrome.viewport(375, 900)
        time.sleep(0.7)
        check('诊疗档案窄屏不横向溢出', not chrome.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'), f"{chrome.evaluate('document.documentElement.scrollWidth')} / {chrome.evaluate('window.innerWidth')}", results)
        chrome.screenshot(os.path.join(SHOTS, 'archive-mobile.png'))
    finally:
        chrome.close()
    failed = [row for row in results if not row[1]]
    print(f"\n诊疗档案验收：{len(results) - len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
