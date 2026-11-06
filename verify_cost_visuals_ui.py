"""费用统计与面板可视化验收：药品费用子页、状态矩阵、收入矩形块图、住院分段条。

前置：Django 已在 127.0.0.1:8000 提供服务，frontend/dist 已构建，演示数据已重建。
用法：python verify_cost_visuals_ui.py
"""

import json
import os
import sys
import time

from verify_ui import BASE, Chrome, SHOTS, check, login_expression


def login(chrome, username, password):
    chrome.goto(f'{BASE}/app/login')
    return chrome.evaluate(login_expression(username, password))


def api_get(chrome, path):
    return chrome.evaluate(f"""(async()=>{{
      const token=localStorage.getItem('smart_medical_access');
      const response=await fetch('/api/v1/{path}',{{headers:{{Authorization:'Bearer '+token}}}});
      return await response.json();
    }})()""")


def click_text(chrome, selector, text):
    return chrome.evaluate(f"""(() => {{
      const node=[...document.querySelectorAll('{selector}')].find(item=>item.innerText.includes('{text}'));
      if(!node)return false;node.click();return true;
    }})()""")


def set_range(chrome, label):
    chrome.evaluate(f"""(() => {{
      const item=[...document.querySelectorAll('.el-segmented__item')].find(node=>node.innerText.includes('{label}'));
      if(item)item.click();
    }})()""")
    time.sleep(0.9)


def matrix_rows(chrome, panel_title):
    return chrome.evaluate(f"""(() => {{
      const panel=[...document.querySelectorAll('.chart-panel')].find(node=>node.innerText.includes('{panel_title}'));
      if(!panel)return [];
      return [...panel.querySelectorAll('.status-matrix-row')].map(row=>({{
        label:row.querySelector('.status-matrix-label')?.innerText.trim()||'',
        value:Number((row.querySelector('.status-matrix-value')?.innerText||'0').replace(/[^0-9]/g,'')),
        percent:row.querySelector('.status-matrix-percent')?.innerText.trim()||''
      }}));
    }})()""")


def pie_legend(chrome):
    return chrome.evaluate("""(() => [...document.querySelectorAll('.revenue-pie-legend li')].map(row=>({
      label:row.querySelector('span')?.innerText.trim()||'',
      amount:row.querySelector('b')?.innerText.trim()||'',
      percent:row.querySelector('em')?.innerText.trim()||'',
      aria:row.getAttribute('aria-label')||''
    })))()""")


def segment_rows(chrome):
    return chrome.evaluate("""(() => [...document.querySelectorAll('.segment-legend>div')].map(row=>({
      label:row.querySelector('.segment-legend-label')?.innerText.trim()||'',
      value:Number((row.querySelector('b')?.innerText||'0').replace(/[^0-9]/g,'')),
      percent:row.querySelector('em')?.innerText.trim()||''
    })))()""")


def normalize_matrix(rows):
    return sorted((row['label'], row['value']) for row in rows)


def mock_dashboard_script(payload):
    return """(() => {
      const origOpen=XMLHttpRequest.prototype.open,origSend=XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open=function(method,url){this.__mockUrl=url;return origOpen.apply(this,arguments)};
      XMLHttpRequest.prototype.send=function(body){
        if(this.__mockUrl&&this.__mockUrl.includes('/statistics/dashboard/')){
          const xhr=this,data=%s;
          setTimeout(()=>{
            try{
              Object.defineProperty(xhr,'readyState',{value:4,configurable:true});
              Object.defineProperty(xhr,'status',{value:200,configurable:true});
              Object.defineProperty(xhr,'statusText',{value:'OK',configurable:true});
              Object.defineProperty(xhr,'responseText',{value:JSON.stringify(data),configurable:true});
              Object.defineProperty(xhr,'response',{value:JSON.stringify(data),configurable:true});
              if(xhr.onreadystatechange)xhr.onreadystatechange();
              if(xhr.onload)xhr.onload();
              if(xhr.onloadend)xhr.onloadend();
              xhr.dispatchEvent(new Event('load'));
              xhr.dispatchEvent(new Event('loadend'));
            }catch(e){}
          },0);return;
        }
        return origSend.apply(this,arguments);
      };
    })();""" % json.dumps(payload)


def main():
    results = []
    chrome = Chrome()
    try:
        chrome.send('Page.enable');chrome.send('Network.enable');chrome.viewport(1440, 1000)

        # 1. 管理员面板：状态矩阵与收入矩形块图（7/30/90 天）
        check('管理员登录', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        chrome.goto(f'{BASE}/app/dashboard', 1.1)
        chrome.wait_for("document.querySelectorAll('.status-matrix-row').length>0")
        for label, key in [('7 天', '7d'), ('30 天', '30d'), ('90 天', '90d')]:
            set_range(chrome, label)
            api = api_get(chrome, f'statistics/dashboard/?range={key}')
            matrix = matrix_rows(chrome, '诊疗状态')
            expected = [(row['name'], row['value']) for row in api['appointment_status']]
            check(f'管理员 {label} 状态矩阵数值与接口一致', normalize_matrix(matrix) == sorted(expected), f"DOM {normalize_matrix(matrix)} / API {sorted(expected)}", results)
            percent_total = sum(float(row['percent'].replace('%', '')) for row in matrix if row['percent'])
            check(f'管理员 {label} 状态占比合计约 100%', abs(percent_total - 100) < 0.6, f'{percent_total:.1f}%', results)
            legend = pie_legend(chrome)
            labels = {'registration': '挂号费', 'examination': '检查费', 'medicine': '药品费', 'inpatient': '住院费', 'other': '其他'}
            expected_billing = sorted((labels.get(row['name'], row['name']), float(row['value'])) for row in api['billing_categories'] if float(row['value']) > 0)
            parsed = sorted((row['label'], float(row['amount'].replace('¥', ''))) for row in legend)
            check(f'管理员 {label} 收入扇形图例金额与接口一致', parsed == expected_billing, f'DOM {parsed} / API {expected_billing}', results)
            total_dom = float(chrome.evaluate("document.querySelector('.revenue-total b')?.innerText.replace('¥','')||'0'"))
            check(f'管理员 {label} 扇形图金额合计等于已结算总额', abs(sum(amount for _, amount in parsed) - total_dom) < 0.01, f'扇区合计 {sum(amount for _, amount in parsed):.2f} / 标题总额 {total_dom:.2f}', results)
        chrome.screenshot(os.path.join(SHOTS, 'dashboard-status-matrix-revenue-pie.png'))

        # 2. 管理员统计页：住院分段比例条
        chrome.goto(f'{BASE}/app/console/operations?tab=statistics', 1.1)
        chrome.wait_for("document.querySelectorAll('.segment-legend>div').length>0")
        for label, key in [('7 天', '7d'), ('30 天', '30d'), ('90 天', '90d')]:
            set_range(chrome, label)
            api = api_get(chrome, f'statistics/dashboard/?range={key}')
            rows = segment_rows(chrome)
            expected = sorted((row['name'], row['value']) for row in api['inpatient_status'])
            check(f'统计页 {label} 住院分段数值与接口一致', normalize_matrix(rows) == expected, f'DOM {normalize_matrix(rows)} / API {expected}', results)
        chrome.screenshot(os.path.join(SHOTS, 'statistics-inpatient-segment.png'))

        # 3. 医师工作台状态矩阵
        check('医师登录', login(chrome, 'doctor', 'Doctor123!') == 'doctor', '', results)
        chrome.goto(f'{BASE}/app/dashboard', 1.1)
        chrome.wait_for("document.querySelectorAll('.status-matrix-row').length>0")
        for label, key in [('7 天', '7d'), ('30 天', '30d'), ('90 天', '90d')]:
            set_range(chrome, label)
            api = api_get(chrome, f'statistics/dashboard/?range={key}')
            matrix = matrix_rows(chrome, '诊疗状态')
            expected = sorted((row['name'], row['value']) for row in api['appointment_status'])
            check(f'医师 {label} 状态矩阵数值与接口一致', normalize_matrix(matrix) == expected, f'DOM {normalize_matrix(matrix)} / API {expected}', results)

        # 4. 零数据 / 单一类别空状态（XHR mock）
        check('管理员登录（空状态校验）', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        mock = {
            'meta': {'range': '30d', 'start': '2026-01-01', 'end': '2026-01-30', 'generated_at': '2026-01-30T00:00:00Z', 'role': 'admin'},
            'kpis': [], 'timeseries': [], 'recent_activity': [], 'alerts': [],
            'appointment_status': [{'name': '待就诊', 'value': 0}, {'name': '就诊中', 'value': 0}, {'name': '已完成', 'value': 0}, {'name': '已取消', 'value': 0}, {'name': '爽约', 'value': 0}],
            'department_workload': [], 'doctor_workload': [],
            'billing_categories': [{'name': 'medicine', 'value': 250}],
            'inpatient_status': [{'name': '待入院', 'value': 0}, {'name': '住院中', 'value': 0}, {'name': '已出院', 'value': 0}, {'name': '已取消', 'value': 0}],
            'workflow': [], 'bed_utilization': {'total': 0, 'occupied': 0, 'available': 0, 'rate': 0}, 'inventory_alerts': [],
        }
        injected = chrome.send('Page.addScriptToEvaluateOnNewDocument', {'source': mock_dashboard_script(mock)})['identifier']
        chrome.send('Page.reload', {'ignoreCache': True});time.sleep(1.2)
        chrome.wait_for("document.querySelector('.matrix-empty')&&document.querySelectorAll('.revenue-pie-legend li').length>0")
        empty = chrome.evaluate("""(() => {
          const panel=[...document.querySelectorAll('.chart-panel')].find(node=>node.innerText.includes('诊疗状态'));
          return {matrixEmpty:Boolean(panel?.querySelector('.matrix-empty')),text:panel?.querySelector('.matrix-empty')?.innerText||'',slices:document.querySelectorAll('.revenue-pie-legend li').length,legend:document.querySelector('.revenue-pie-legend')?.innerText.replace(/\\n+/g,' | ')||'',canvas:document.querySelectorAll('.revenue-pie-chart canvas').length};
        })()""")
        check('全零数据矩阵显示明确空状态', empty['matrixEmpty'] and '暂无预约' in empty['text'], str(empty), results)
        check('单一收入类别完整显示为 100% 扇形', empty['slices'] == 1 and '药品费' in empty['legend'] and '¥250.00' in empty['legend'] and '100.0%' in empty['legend'] and empty['canvas'] > 0, str(empty), results)
        chrome.goto(f'{BASE}/app/console/operations?tab=statistics', 1.0)
        chrome.wait_for("[...document.querySelectorAll('.chart-panel')].some(node=>node.innerText.includes('住院状态构成')&&node.querySelector('.matrix-empty'))")
        empty_segment = chrome.evaluate("""(() => {
          const panel=[...document.querySelectorAll('.chart-panel')].find(node=>node.innerText.includes('住院状态构成'));
          return {empty:Boolean(panel?.querySelector('.matrix-empty')),text:panel?.querySelector('.matrix-empty')?.innerText||''};
        })()""")
        check('全零住院状态显示明确空状态', empty_segment['empty'] and '没有住院记录' in empty_segment['text'], str(empty_segment), results)
        chrome.send('Page.removeScriptToEvaluateOnNewDocument', {'identifier': injected})
        # 零收入单独校验：仍保留预约状态数据，仅收入类别为空
        zero_revenue = dict(mock);zero_revenue['billing_categories'] = []
        injected_zero = chrome.send('Page.addScriptToEvaluateOnNewDocument', {'source': mock_dashboard_script(zero_revenue)})['identifier']
        chrome.goto(f'{BASE}/app/dashboard', 1.0)
        chrome.wait_for("(()=>{const p=[...document.querySelectorAll('.chart-panel')].find(n=>n.innerText.includes('收入构成'));return Boolean(p&&p.querySelector('.matrix-empty'))})()")
        zero = chrome.evaluate("""(() => {const panel=[...document.querySelectorAll('.chart-panel')].find(node=>node.innerText.includes('收入构成'));return{empty:Boolean(panel?.querySelector('.matrix-empty')),text:panel?.querySelector('.matrix-empty')?.innerText||'',total:document.querySelector('.revenue-total b')?.innerText||''};})()""")
        check('零收入显示明确空状态且总额为零', zero['empty'] and '暂无已结算收入' in zero['text'] and zero['total'] in ('¥0.00', '¥0'), str(zero), results)
        chrome.send('Page.removeScriptToEvaluateOnNewDocument', {'identifier': injected_zero})
        chrome.send('Page.reload', {'ignoreCache': True});time.sleep(1.0)

        # 5. 药品费用子页（患者）
        check('患者登录', login(chrome, 'patient', 'Patient123!') == 'patient', '', results)
        chrome.goto(f'{BASE}/app/patient/finance?tab=medicine-costs', 1.2)
        chrome.wait_for("document.querySelectorAll('.exam-cost-metric').length>0")
        cost = chrome.evaluate("""(() => {
          const inputs=[...document.querySelectorAll('.exam-cost-tools .el-date-editor input')].map(node=>node.value);
          return {
            title:document.querySelector('h1')?.innerText||'',
            labels:[...document.querySelectorAll('.exam-cost-metric span')].map(node=>node.innerText.trim()),
            metrics:[...document.querySelectorAll('.exam-cost-metric strong')].map(node=>node.innerText.trim()),
            dates:inputs,
            chart:document.querySelectorAll('.exam-cost-chart canvas').length,
            medicineRows:document.querySelectorAll('.exam-cost-panel')[0]?.querySelectorAll('.el-table__body tbody tr').length||0,
            detailRows:document.querySelectorAll('.exam-cost-panel')[1]?.querySelectorAll('.el-table__body tbody tr').length||0
          };
        })()""")
        check('患者药品费用子页展示独立指标与趋势', cost['title'] == '药品费用' and '药品费用总额' in cost['labels'] and cost['chart'] > 0, str(cost['labels']), results)
        check('药品费用展示按药品汇总与分页明细', cost['medicineRows'] > 0 and cost['detailRows'] > 0, f"{cost['medicineRows']} / {cost['detailRows']}", results)
        api = api_get(chrome, f"billing-records/medicine-costs/?date_from={cost['dates'][0]}&date_to={cost['dates'][1]}&page_size=10")
        check('药品费用总额与接口一致', cost['metrics'][0] == f"¥{float(api['summary']['total_amount']):.2f}", f"DOM {cost['metrics'][0]} / API {api['summary']['total_amount']}", results)
        chrome.evaluate("document.querySelectorAll('.exam-cost-panel')[1]?.querySelector('.el-table__expand-icon')?.click()");time.sleep(0.4)
        detail = chrome.evaluate("document.querySelector('.charge-detail-panel')?.innerText.replace(/\\n+/g,' | ')||''")
        check('处方账单可展开查看药品、数量与金额', all(key in detail for key in ('数量', '¥')), detail[:160], results)
        # 独立状态：药品费用选择近 7 天，检查费用仍保持自己的 30 天
        set_range(chrome, '近 7 天')
        click_text(chrome, '.folder-tab', '检查费用');time.sleep(1.1)
        exam_preset = chrome.evaluate("document.querySelector('.el-segmented__item.is-selected')?.innerText.trim()||''")
        click_text(chrome, '.folder-tab', '药品费用');time.sleep(1.1)
        medicine_preset = chrome.evaluate("document.querySelector('.el-segmented__item.is-selected')?.innerText.trim()||''")
        check('检查费用与药品费用维护独立日期状态', '近 30 天' in exam_preset and '近 7 天' in medicine_preset, f'{exam_preset} / {medicine_preset}', results)
        chrome.viewport(375, 900);time.sleep(0.6)
        mobile = chrome.evaluate("""(() => ({table:document.querySelector('.exam-cost-panel .desktop-table')?getComputedStyle(document.querySelector('.exam-cost-panel .desktop-table')).display:'none',cards:document.querySelectorAll('.exam-cost-panel .mobile-card-list .mobile-info-card').length,overflow:document.documentElement.scrollWidth>window.innerWidth+1}))()""")
        check('窄屏药品费用改为纵向信息卡', mobile['table'] == 'none' and mobile['cards'] > 0 and not mobile['overflow'], str(mobile), results)
        chrome.viewport(1440, 1000)
        chrome.screenshot(os.path.join(SHOTS, 'patient-medicine-costs.png'))

        # 6. 管理员药品费用子页
        check('管理员重新登录', login(chrome, 'admin', 'Admin123!') == 'admin', '', results)
        chrome.goto(f'{BASE}/app/console/operations?tab=medicine-costs', 1.2)
        chrome.wait_for("document.body.innerText.includes('请选择患者后查询药品费用')")
        chrome.evaluate("document.querySelector('.exam-cost-tools .el-select__wrapper')?.click()");time.sleep(0.5)
        selected = chrome.evaluate("""(() => {
          const drops=[...document.querySelectorAll('.el-select-dropdown')].filter(node=>node.getBoundingClientRect().height>0);
          const drop=drops[drops.length-1];const option=drop?.querySelector('.el-select-dropdown__item');if(!option)return null;option.click();return option.innerText.trim();
        })()""");time.sleep(1.1)
        chrome.wait_for("document.querySelectorAll('.exam-cost-metric').length>0")
        admin_cost = chrome.evaluate("""(() => ({labels:[...document.querySelectorAll('.exam-cost-metric span')].map(node=>node.innerText.trim()),total:document.querySelector('.exam-cost-metric strong')?.innerText||'',dates:[...document.querySelectorAll('.exam-cost-tools .el-date-editor input')].map(node=>node.value)}))()""")
        check('管理员可按患者查询药品费用', '药品费用总额' in admin_cost['labels'] and selected is not None, str(selected), results)
        patients = api_get(chrome, f"patients/?search={selected.split('·')[-1].strip() if selected else ''}")
        if patients.get('results'):
            patient_id = patients['results'][0]['id']
            admin_api = api_get(chrome, f"billing-records/medicine-costs/?patient={patient_id}&date_from={admin_cost['dates'][0]}&date_to={admin_cost['dates'][1]}&page_size=10")
            check('管理员药品费用金额与接口一致', admin_cost['total'] == f"¥{float(admin_api['summary']['total_amount']):.2f}", f"DOM {admin_cost['total']} / API {admin_api['summary']['total_amount']}", results)
        chrome.screenshot(os.path.join(SHOTS, 'admin-medicine-costs.png'))

        # 7. 窄屏与减少动态效果
        chrome.viewport(375, 900)
        chrome.goto(f'{BASE}/app/dashboard', 1.1)
        chrome.wait_for("document.querySelectorAll('.status-matrix-row').length>0")
        narrow = chrome.evaluate("""(() => ({overflow:document.documentElement.scrollWidth>window.innerWidth+1,legendColumns:getComputedStyle(document.querySelector('.revenue-pie-legend')).gridTemplateColumns.split(' ').filter(Boolean).length,rows:document.querySelectorAll('.status-matrix-row').length,pie:document.querySelectorAll('.revenue-pie-chart').length}))()""")
        check('窄屏面板纵向排列且无横向溢出', narrow['legendColumns'] == 1 and narrow['pie'] > 0 and not narrow['overflow'] and narrow['rows'] > 0, str(narrow), results)
        chrome.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        chrome.send('Page.reload', {'ignoreCache': True});time.sleep(1.0);chrome.wait_for("document.querySelectorAll('.status-matrix-track i').length>0")
        motion = chrome.evaluate("""(() => ({media:matchMedia('(prefers-reduced-motion: reduce)').matches,duration:getComputedStyle(document.querySelector('.status-matrix-track i')).transitionDuration}))()""")
        check('减少动态效果设置生效', motion['media'] and float(motion['duration'].replace('s', '')) < 0.01, str(motion), results)
        chrome.send('Emulation.setEmulatedMedia', {'features': []})
        chrome.viewport(1440, 1000)
    finally:
        chrome.close()
    failed = [row for row in results if not row[1]]
    print(f"\n费用与可视化验收：{len(results) - len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
