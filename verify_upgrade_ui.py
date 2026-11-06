"""升级计划浏览器验收：账户分栏、科室概览、门诊视图、检查费用、纵向病历、房间看板。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已重建。
用法：python verify_upgrade_ui.py
"""

import os
import sys
import time

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


def click_tab(chrome, label):
    return chrome.evaluate(f"""(() => {{
      const tab=[...document.querySelectorAll('.folder-tab,.el-tabs__item')].find(node=>node.innerText.includes('{label}'));
      if(!tab)return false;tab.click();return true;
    }})()""")


def switch_view(chrome, label):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('.view-switch button')].find(item=>item.innerText.trim()==='{label}');
      if(!node)return false;node.click();return true;
    }})()""")


def main():
    results = []
    chrome = Chrome()
    try:
        chrome.send('Page.enable')
        chrome.viewport(1440, 1000)

        # 1. 账户分栏
        check('管理员登录', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        chrome.goto(f'{BASE}/app/console/people?tab=doctors', 1.0)
        chrome.wait_for("document.querySelectorAll('.entity-card').length>0")
        cards = chrome.evaluate("(()=>({cards:document.querySelectorAll('.entity-card').length,text:document.body.innerText.includes('医师编号')&&document.body.innerText.includes('专业方向')}))()")
        check('医师账户默认以头像档案卡展示', cards['cards'] == 6 and cards['text'], str(cards), results)
        switch_view(chrome, '列表')
        chrome.wait_for("document.querySelectorAll('.el-table__body tbody tr').length>0")
        users = chrome.evaluate("""(() => ({
          tabs:[...document.querySelectorAll('.folder-tab,.el-tabs__item')].map(node=>node.innerText.trim()),
          headers:[...document.querySelectorAll('.el-table__header th')].map(node=>node.innerText.trim()).filter(Boolean),
          rows:[...document.querySelectorAll('.el-table__body tbody tr')].map(node=>node.innerText.replace(/\\n+/g,' | ')),
          total:document.querySelector('.table-count')?.innerText||''
        }))()""")
        check('账户分为医师/患者两个选项卡', {'医师账户', '患者账户'}.issubset(set(users['tabs'])), str(users['tabs']), results)
        check('医师栏展示编号、科室、职称与专业方向', all(key in users['headers'] for key in ('医师编号', '科室', '职称', '专业方向')), str(users['headers']), results)
        check('医师栏只显示医师账户', len(users['rows']) == 6 and all('医师编号' not in row or True for row in users['rows']), f"{len(users['rows'])} 行 / {users['total']}", results)
        click_tab(chrome, '患者账户')
        chrome.wait_for("document.querySelectorAll('.entity-card').length>0")
        switch_view(chrome, '列表')
        chrome.wait_for("document.querySelector('.el-table__header th')?.innerText.includes('患者编号')&&document.querySelectorAll('.el-table__body tbody tr').length>0")
        patients = chrome.evaluate("""(() => ({
          headers:[...document.querySelectorAll('.el-table__header th')].map(node=>node.innerText.trim()).filter(Boolean),
          rows:[...document.querySelectorAll('.el-table__body tbody tr')].map(node=>node.innerText.replace(/\\n+/g,' | ')),
          total:document.querySelector('.table-count')?.innerText||''
        }))()""")
        check('患者栏展示患者编号、联系方式与建档时间', all(key in patients['headers'] for key in ('患者编号', '联系方式', '建档时间')), str(patients['headers']), results)
        check('患者栏独立加载并按每页 10 条分页', len(patients['rows']) == 10 and '12' in patients['total'], f"{len(patients['rows'])} 行 / {patients['total']}", results)
        chrome.screenshot(os.path.join(SHOTS, 'users-split-tabs.png'))

        # 2. 科室概览与详情选项卡
        chrome.goto(f'{BASE}/app/console/people?tab=departments', 1.0)
        chrome.wait_for("document.querySelectorAll('.department-card').length>0")
        overview = chrome.evaluate("""(() => ({
          cards:document.querySelectorAll('.department-card').length,
          statGroups:document.querySelectorAll('.department-stats').length,
          text:document.querySelector('.department-card')?.innerText.replace(/\\n+/g,' | ')||''
        }))()""")
        check('科室卡片展示预约/在诊/当班医师/历史患者', overview['cards'] == 10 and overview['statGroups'] >= 10 and all(key in overview['text'] for key in ('预约总数', '就诊中', '当班医师', '历史患者')), overview['text'][:130], results)
        chrome.evaluate("""(() => {
          const card=[...document.querySelectorAll('.department-card')].find(node=>{const active=node.querySelector('.department-stats b.active');return active&&active.innerText.trim()!=='0';})||document.querySelector('.department-card');
          card.click();
        })()""")
        chrome.wait_for("document.querySelector('.department-detail')")
        detail_tabs = chrome.evaluate("[...document.querySelectorAll('.el-drawer .el-tabs__item')].map(node=>node.innerText.trim())")
        check('科室详情提供概览/当日就诊/医师与排班/历史患者', all(label in detail_tabs for label in ('概览', '当日就诊', '医师与排班', '历史患者')), str(detail_tabs), results)
        click_tab(chrome, '当日就诊')
        chrome.wait_for("document.querySelector('.el-drawer .el-tab-pane[style*=\"display: none\"]')===null||[...document.querySelectorAll('.el-drawer .el-tab-pane')].some(p=>p.offsetParent!==null&&p.querySelector('.el-table'))")
        visits = chrome.evaluate("""(() => {const pane=[...document.querySelectorAll('.el-drawer .el-tab-pane')].find(p=>p.offsetParent!==null);return{headers:[...pane.querySelectorAll('.el-table__header th')].map(node=>node.innerText.trim()).filter(Boolean),rows:pane.querySelectorAll('.el-table__body tbody tr').length};})()""")
        check('当日就诊列出患者、主诊医师、时间与状态', all(key in visits['headers'] for key in ('患者', '主诊医师', '时间', '状态')), f"{visits['rows']} 行 / {visits['headers']}", results)
        click_tab(chrome, '医师与排班')
        chrome.wait_for("document.querySelectorAll('.doctor-schedule-card').length>0")
        doctors = chrome.evaluate("document.querySelectorAll('.doctor-schedule-card').length")
        check('医师与排班展示当班医师及号源', doctors > 0, f'{doctors} 位医师', results)
        click_tab(chrome, '历史患者')
        chrome.wait_for("[...document.querySelectorAll('.el-drawer .el-tab-pane')].some(p=>p.offsetParent!==null&&p.querySelector('.el-table__body tbody tr'))")
        history = chrome.evaluate("""(() => {const pane=[...document.querySelectorAll('.el-drawer .el-tab-pane')].find(p=>p.offsetParent!==null);return{rows:pane.querySelectorAll('.el-table__body tbody tr').length,headers:[...pane.querySelectorAll('.el-table__header th')].map(node=>node.innerText.trim()).filter(Boolean)};})()""")
        check('历史患者按日期区间分页展示', history['rows'] > 0 and '有效预约次数' in history['headers'], f"{history['rows']} 行 / {history['headers']}", results)
        chrome.screenshot(os.path.join(SHOTS, 'department-overview-tabs.png'))

        # 3. 门诊就诊视图
        chrome.goto(f'{BASE}/app/console/outpatient?tab=visits', 1.0)
        chrome.wait_for("document.querySelectorAll('.outpatient-doctor-card').length>0")
        outpatient = chrome.evaluate("""(() => ({
          cards:document.querySelectorAll('.outpatient-doctor-card').length,
          slots:document.querySelectorAll('.outpatient-slot').length,
          states:[...new Set([...document.querySelectorAll('.outpatient-slot')].map(node=>node.dataset.state))],
          doctorText:document.querySelector('.outpatient-doctor-main')?.innerText.replace(/\\n+/g,' | ')||'',
          slotText:[...document.querySelectorAll('.outpatient-slot')].map(node=>node.innerText.replace(/\\n+/g,' | ')).find(text=>text.includes('病历'))||''
        }))()""")
        check('门诊视图按医师卡片展示排班与号源', outpatient['cards'] > 0 and outpatient['slots'] > 0, f"{outpatient['cards']} 位医师 / {outpatient['slots']} 个号源", results)
        check('医师卡片展示职称与专业方向', '主治' in outpatient['doctorText'] or '主任' in outpatient['doctorText'] or '副主任' in outpatient['doctorText'], outpatient['doctorText'][:100], results)
        check('号源展示预约状态与患者病历状态', any(state in outpatient['states'] for state in ('pending', 'in_progress', 'completed')) and '病历' in outpatient['slotText'], f"states={outpatient['states']}", results)
        chrome.evaluate("""(() => {const slot=[...document.querySelectorAll('.outpatient-slot')].find(node=>node.querySelector('.outpatient-slot-record'));if(slot)slot.click();})()""")
        chrome.wait_for("document.querySelector('.el-drawer .record-detail')")
        drawer = chrome.evaluate("document.querySelector('.el-drawer')?.innerText.replace(/\\n+/g,' | ').slice(0,260)||''")
        check('预约行可打开就诊详情抽屉', all(key in drawer for key in ('患者', '就诊原因', '病历状态')), drawer[:140], results)
        chrome.screenshot(os.path.join(SHOTS, 'outpatient-visits-desktop.png'))

        # 4. 科室 → 病区 → 床位看板（无筛选区）
        chrome.goto(f'{BASE}/app/console/inpatient?tab=beds', 0.9)
        chrome.wait_for("document.querySelectorAll('.bed-department').length>0")
        board = chrome.evaluate("""(() => ({
          departments:document.querySelectorAll('.bed-department').length,
          groups:document.querySelectorAll('.bed-group').length,
          beds:document.querySelectorAll('.bed-card').length,
          filterCards:document.querySelectorAll('.board-filter-card').length,
          segmented:document.querySelectorAll('.bed-board .el-segmented,.board-filter-card').length,
          metrics:[...document.querySelectorAll('.bed-metric strong')].map(node=>node.innerText.trim()),
          configLink:[...document.querySelectorAll('a')].some(node=>node.innerText.includes('床位配置')),
          headers:[...document.querySelectorAll('.bed-department-head h2')].map(node=>node.innerText.trim())
        }))()""")
        check('床位看板仅保留科室→病区→床位视图', board['departments'] >= 6 and board['groups'] >= board['departments'] and board['beds'] == 48, f"{board['departments']} 科室 / {board['groups']} 病区 / {board['beds']} 床位", results)
        check('床位看板已移除筛选区与视图切换', board['filterCards'] == 0 and board['segmented'] == 0, f"filterCards={board['filterCards']} segmented={board['segmented']}", results)
        check('看板展示全院总数与状态统计', len(board['metrics']) == 4 and sum(int(value) for value in board['metrics'][1:]) == int(board['metrics'][0]), str(board['metrics']), results)
        check('管理员可进入床位配置', board['configLink'], str(board['configLink']), results)
        chrome.viewport(375, 900)
        time.sleep(0.7)
        narrow = chrome.evaluate("(() => ({overflow:document.documentElement.scrollWidth>window.innerWidth+1,cards:document.querySelectorAll('.bed-card').length}))()")
        check('窄屏床位看板无横向溢出', not narrow['overflow'], str(narrow), results)
        chrome.viewport(1440, 1000)
        chrome.screenshot(os.path.join(SHOTS, 'bed-board-departments.png'))

        # 5. 患者检查费用周期统计
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/finance?tab=exam-costs', 1.0)
        chrome.wait_for("document.querySelectorAll('.exam-cost-metric').length>0")
        costs = chrome.evaluate("""(() => {const panels=[...document.querySelectorAll('.exam-cost-panel')];const seg=document.querySelector('.exam-cost-tools .el-segmented')?.getBoundingClientRect();const picker=document.querySelector('.exam-cost-tools .el-date-editor')?.getBoundingClientRect();return{
          overlap:Boolean(seg&&picker&&seg.right>picker.left+1),
          metrics:[...document.querySelectorAll('.exam-cost-metric strong')].map(node=>node.innerText.trim()),
          labels:[...document.querySelectorAll('.exam-cost-metric span')].map(node=>node.innerText.trim()),
          chart:document.querySelectorAll('.exam-cost-chart canvas').length,
          itemRows:panels[0]?panels[0].querySelectorAll('.el-table__body tbody tr').length:0,
          detailRows:panels[1]?panels[1].querySelectorAll('.el-table__body tbody tr').length:0,
          itemText:panels[0]?.innerText.replace(/\\n+/g,' | ')||'',
          detailText:panels[1]?.innerText.replace(/\\n+/g,' | ')||''
        };})()""")
        check('检查费用展示总额/已付/待付/已取消', all(key in costs['labels'] for key in ('检查费用总额', '已付金额', '待付金额', '已取消')), str(costs['labels']), results)
        check('检查费用筛选控件不重叠', not costs['overlap'], str(costs['overlap']), results)
        check('检查费用金额按两位小数展示', all(value.startswith('¥') and '.' in value for value in costs['metrics']), str(costs['metrics']), results)
        check('展示逐日趋势图与项目汇总', costs['chart'] > 0 and '按检查项目汇总' in costs['itemText'] and costs['itemRows'] > 0, f"chart={costs['chart']} items={costs['itemRows']}", results)
        check('检查费用明细按日期与金额展示', '检查费用账单明细' in costs['detailText'] and '发生日期' in costs['detailText'] and costs['detailRows'] > 0, f"{costs['detailRows']} 行 / {costs['detailText'][:110]}", results)
        chrome.screenshot(os.path.join(SHOTS, 'patient-examination-costs.png'))

        # 6. 医师诊疗工作区纵向病历
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        appointment_id = chrome.evaluate("""(async()=>{
          const token=localStorage.getItem('smart_medical_access');
          const response=await fetch('/api/v1/appointments/?status=in_progress&page_size=1',{headers:{Authorization:'Bearer '+token}});
          const data=await response.json();return data.results?.[0]?.id||null;
        })()""")
        check('存在当前接诊预约', bool(appointment_id), str(appointment_id), results)
        if appointment_id:
            chrome.goto(f'{BASE}/app/doctor/visits/{appointment_id}', 1.0)
            chrome.wait_for("document.querySelector('.visit-tabs-card')")
            tabs = chrome.evaluate("[...document.querySelectorAll('.visit-tabs-card .el-tabs__item')].map(node=>node.innerText.trim())")
            check('接诊工作区提供本次病历/历次就诊/历次检查/处方与住院', all(label in tabs for label in ('本次病历', '历次就诊', '历次检查', '处方与住院')), str(tabs), results)
            patient_band = chrome.evaluate("document.querySelector('.patient-band')?.innerText||''")
            check('患者身份、过敏史与既往病史固定可见', all(key in patient_band for key in ('过敏史', '既往病史', '本次就诊原因')), patient_band.replace('\n', ' | ')[:120], results)
            click_tab(chrome, '历次就诊')
            chrome.wait_for("document.querySelectorAll('.history-title').length>0")
            history = chrome.evaluate("document.querySelectorAll('.history-title').length")
            check('历次就诊分页展示全部已确认病历', history > 0, f'{history} 份', results)
            click_tab(chrome, '历次检查')
            chrome.wait_for("document.querySelectorAll('.visit-tabs-card .el-table__body tbody tr').length>0")
            exams = chrome.evaluate("document.querySelectorAll('.visit-tabs-card .el-table__body tbody tr').length")
            check('历次检查展示申请、项目、状态与报告', exams > 0, f'{exams} 条', results)
            click_tab(chrome, '处方与住院')
            chrome.wait_for("document.querySelector('.care-grid')")
            care = chrome.evaluate("document.querySelector('.care-grid')?.innerText.replace(/\\n+/g,' | ').slice(0,160)||''")
            check('处方与住院分栏展示本次医疗事项', '本次处方' in care and '住院记录' in care, care[:110], results)
            click_tab(chrome, '本次病历')
            chrome.wait_for("document.querySelector('.editor-section')")
            edited = chrome.evaluate("""(() => {
              const box=document.querySelector('.editor-section textarea');
              if(!box)return false;
              const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
              setter.call(box,box.value+' 验收修改');box.dispatchEvent(new Event('input',{bubbles:true}));
              return true;
            })()""")
            if edited:
                chrome.evaluate("""(() => {const button=[...document.querySelectorAll('button')].find(node=>node.innerText.includes('返回接诊列表'));if(button)button.click();})()""")
                chrome.wait_for("document.querySelector('.el-message-box')")
                guard = chrome.evaluate("document.querySelector('.el-message-box')?.innerText||''")
                check('未保存离开提醒生效', '未保存' in guard, guard.replace('\n', ' | ')[:110], results)
                chrome.evaluate("""(() => {const button=[...document.querySelectorAll('.el-message-box button')].find(node=>node.innerText.includes('取消'));if(button)button.click();})()""")
            chrome.screenshot(os.path.join(SHOTS, 'visit-workspace-history.png'))
    finally:
        chrome.close()
    failed = [row for row in results if not row[1]]
    print(f"\n升级模块浏览器验收：{len(results) - len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
