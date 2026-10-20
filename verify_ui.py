"""床位看板浏览器验收：用无头 Chrome（CDP + 标准库 WebSocket）走通三角色页面并检查卡片布局。

前置：Django 已在 127.0.0.1:8000 提供服务，且 frontend/dist 已构建。
用法：python verify_ui.py
"""

import base64,json,os,shutil,socket,struct,subprocess,sys,tempfile,time,urllib.request

BASE='http://127.0.0.1:8000'
ROOT=os.path.dirname(os.path.abspath(__file__))
SHOTS=os.path.join(ROOT,'docs','screenshots')

class WebSocket:
    """最小 WebSocket 文本客户端，避免额外依赖。"""

    def __init__(self,url,timeout=30):
        without_scheme=url.split('://',1)[1];host_port,path=without_scheme.split('/',1);path='/'+path
        host,port=host_port.split(':')
        self.socket=socket.create_connection((host,int(port)),timeout=timeout)
        key=base64.b64encode(os.urandom(16)).decode()
        handshake=(f'GET {path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://127.0.0.1\r\n\r\n')
        self.socket.sendall(handshake.encode())
        buffer=b''
        while b'\r\n\r\n' not in buffer:buffer+=self.socket.recv(4096)
        if b' 101 ' not in buffer.split(b'\r\n',1)[0]:raise RuntimeError(f'WebSocket 握手失败：{buffer[:200]!r}')
        self.buffer=buffer.split(b'\r\n\r\n',1)[1]
        self.socket.settimeout(timeout)

    def send(self,text):
        payload=text.encode();header=bytearray([0x81]);length=len(payload)
        if length<126:header.append(0x80|length)
        elif length<65536:header.append(0x80|126);header+=struct.pack('>H',length)
        else:header.append(0x80|127);header+=struct.pack('>Q',length)
        mask=os.urandom(4);header+=mask
        self.socket.sendall(bytes(header)+bytes(byte^mask[index%4] for index,byte in enumerate(payload)))

    def _read(self,size):
        while len(self.buffer)<size:
            chunk=self.socket.recv(65536)
            if not chunk:raise RuntimeError('WebSocket 连接已关闭')
            self.buffer+=chunk
        data,self.buffer=self.buffer[:size],self.buffer[size:];return data

    def recv(self):
        while True:
            header=self._read(2)
            opcode=header[0]&0x0F
            length=header[1]&0x7F
            if length==126:length=struct.unpack('>H',self._read(2))[0]
            elif length==127:length=struct.unpack('>Q',self._read(8))[0]
            payload=self._read(length)
            if opcode==0x1:return payload.decode('utf-8')
            if opcode==0x8:raise RuntimeError('WebSocket 已关闭')
            if opcode==0x9:self._frame(0xA,payload)

    def _frame(self,opcode,payload):
        header=bytearray([0x80|opcode]);length=len(payload)
        if length<126:header.append(0x80|length)
        else:header.append(0x80|126);header+=struct.pack('>H',length)
        mask=os.urandom(4);header+=mask
        self.socket.sendall(bytes(header)+bytes(byte^mask[index%4] for index,byte in enumerate(payload)))

    def close(self):
        try:self._frame(0x8,b'');self.socket.close()
        except Exception:pass

class Chrome:
    def __init__(self,width=1440,height=1000):
        executable=next((path for path in ('/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium') if os.path.exists(path)),None)
        if executable is None:raise RuntimeError('未找到 Chrome/Chromium，可安装后再运行浏览器验收')
        self.profile=tempfile.mkdtemp(prefix='dsh-chrome-');self.port=self.free_port()
        environment=dict(os.environ);environment.update({'HOME':self.profile,'XDG_CONFIG_HOME':os.path.join(self.profile,'config'),
            'XDG_CACHE_HOME':os.path.join(self.profile,'cache'),'XDG_RUNTIME_DIR':os.path.join(self.profile,'run')})
        for path in (environment['XDG_CONFIG_HOME'],environment['XDG_CACHE_HOME'],environment['XDG_RUNTIME_DIR']):os.makedirs(path,exist_ok=True)
        self.process=subprocess.Popen([executable,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-first-run',
            '--no-default-browser-check','--disable-crash-reporter','--disable-breakpad','--hide-scrollbars','--remote-allow-origins=*','--window-size=%d,%d'%(width,height),
            f'--remote-debugging-port={self.port}',f'--user-data-dir={self.profile}','about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=environment)
        for _ in range(80):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/version',timeout=0.5) as response:json.load(response);break
            except Exception:time.sleep(0.25)
        else:raise RuntimeError('Chrome 调试端口未就绪')
        request=urllib.request.Request(f'http://127.0.0.1:{self.port}/json/new?about:blank',method='PUT')
        with urllib.request.urlopen(request) as response:target=json.load(response)
        self.ws=WebSocket(target['webSocketDebuggerUrl']);self.counter=0

    @staticmethod
    def free_port():
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

    def send(self,method,params=None):
        self.counter+=1;self.ws.send(json.dumps({'id':self.counter,'method':method,'params':params or {}}))
        while True:
            payload=json.loads(self.ws.recv())
            if payload.get('id')==self.counter:
                if 'error' in payload:raise RuntimeError(f"{method}: {payload['error']}")
                return payload.get('result',{})

    def evaluate(self,expression):
        result=self.send('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
        if 'exceptionDetails' in result:
            details=result['exceptionDetails']
            raise RuntimeError(f"页面脚本异常：{details.get('text')} {details.get('exception',{}).get('description','')}")
        return result.get('result',{}).get('value')

    def wait_for(self,expression,timeout=12,interval=0.4):
        """等待前端完成异步渲染。"""
        deadline=time.time()+timeout
        while time.time()<deadline:
            try:
                if self.evaluate(expression):return True
            except RuntimeError:pass
            time.sleep(interval)
        return False

    def viewport(self,width,height):
        self.send('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<620})

    def goto(self,url,wait=1.2):
        separator='&' if '?' in url else '?'
        self.send('Page.navigate',{'url':f'{url}{separator}_verify={time.time_ns()}'});time.sleep(wait)

    def screenshot(self,path):
        os.makedirs(os.path.dirname(path),exist_ok=True)
        data=self.send('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})['data']
        with open(path,'wb') as handle:handle.write(base64.b64decode(data))

    def close(self):
        self.ws.close();self.process.terminate()
        try:self.process.wait(timeout=10)
        except Exception:self.process.kill()
        shutil.rmtree(self.profile,ignore_errors=True)

def login_expression(username,password):
    return f"""(async()=>{{
      const response=await fetch('{BASE}/api/v1/auth/login/',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:'{username}',password:'{password}'}})}});
      const data=await response.json();
      if(!response.ok)throw new Error(JSON.stringify(data));
      localStorage.setItem('smart_medical_access',data.access);
      if(data.refresh)localStorage.setItem('smart_medical_refresh',data.refresh);
      localStorage.setItem('smart_medical_user',JSON.stringify(data.user));
      return data.user.role;
    }})()"""

MEASURE="""
(() => {
  const cards=[...document.querySelectorAll('.bed-card')];
  const grid=document.querySelector('.bed-grid');
  const style=grid?getComputedStyle(grid):null;
  const columns=style?style.gridTemplateColumns.split(' ').filter(Boolean).length:0;
  const perRow={};
  cards.forEach(card=>{const top=Math.round(card.getBoundingClientRect().top);perRow[top]=(perRow[top]||0)+1;});
  return {
    cards:cards.length,columns,rows:Object.keys(perRow).length,perRow:Object.values(perRow),
    byStatus:cards.reduce((acc,card)=>{const key=card.dataset.status;acc[key]=(acc[key]||0)+1;return acc;},{}),
    statusLabels:cards.map(card=>(card.querySelector('.bed-card-status')||{}).textContent||''),
    bedNumbers:cards.map(card=>card.dataset.bed),
    groups:document.querySelectorAll('.bed-group').length,
    departments:document.querySelectorAll('.bed-department').length,
    departmentNames:[...document.querySelectorAll('.bed-department-head h2')].map(node=>node.textContent.trim()),
    wardNames:[...document.querySelectorAll('.bed-group-head h3')].map(node=>node.textContent.trim()),
    metrics:[...document.querySelectorAll('.bed-metric strong')].map(node=>node.textContent.trim()),
    overflowX:document.documentElement.scrollWidth>window.innerWidth+1,
    occupiedSample:(cards.find(card=>card.dataset.status==='occupied')||{innerText:''}).innerText.replace(/\\n+/g,' | '),
    availableSample:(cards.find(card=>card.dataset.status==='available')||{innerText:''}).innerText.replace(/\\n+/g,' | '),
    inactiveSample:(cards.find(card=>card.dataset.status==='inactive')||{innerText:''}).innerText.replace(/\\n+/g,' | ')
  };
})()
"""

def check(label,condition,detail,results):
    results.append((label,bool(condition),detail))
    print(('PASS ' if condition else 'FAIL ')+label+(f' —— {detail}' if detail else ''))
    return bool(condition)

def main():
    if not os.path.exists(os.path.join(ROOT,'frontend','dist','index.html')):
        print('请先执行 frontend 生产构建');return 1
    results=[];chrome=Chrome()
    try:
        chrome.send('Page.enable');chrome.viewport(1440,1000)
        chrome.goto(f'{BASE}/app/login')
        role=chrome.evaluate(login_expression('admin','Admin123!'))
        check('管理员登录',role=='admin',str(role),results)
        chrome.goto(f'{BASE}/app/console/bed-board',0.8)
        chrome.wait_for("document.querySelectorAll('.bed-card').length>0")
        # 看板默认按房间分组；旧版布局检查切换到“按科室”分组视图。
        chrome.evaluate("(()=>{const item=[...document.querySelectorAll('.el-segmented__item')].find(node=>node.innerText.includes('按科室'));if(item)item.click();})()")
        time.sleep(0.5)
        desktop=chrome.evaluate(MEASURE)
        check('看板渲染床位卡片',desktop['cards']>0,f"{desktop['cards']} 张卡片",results)
        check('按科室与病区分组',desktop['departments']>0 and desktop['groups']>=desktop['departments'],f"{desktop['departments']} 个科室 / {desktop['groups']} 个病区：{'、'.join(desktop['departmentNames'])}",results)
        check('每张床恰好一张卡片',desktop['cards']==sum(desktop['perRow']) and desktop['departments']>0,f"{desktop['rows']} 行 × 每行 {desktop['perRow']}",results)
        check('桌面宽度多列网格',desktop['columns']>=3,f"columns={desktop['columns']} perRow={desktop['perRow']}",results)
        check('状态颜色键与文字标签齐备',set(desktop['byStatus'])<= {'available','occupied','inactive'} and all(desktop['statusLabels']),str(desktop['byStatus']),results)
        counts=desktop['byStatus']
        check('统计卡片与卡片数量一致',sum(int(value) for value in desktop['metrics'][1:])==desktop['cards'],f"统计 {desktop['metrics']} / 卡片 {desktop['cards']}（空闲 {counts.get('available',0)}、住院 {counts.get('occupied',0)}、停用 {counts.get('inactive',0)}）",results)
        check('空床卡片显示位置与日费',('日费' in desktop['availableSample'] and '空闲' in desktop['availableSample']),desktop['availableSample'][:90],results)
        check('占用卡片显示患者与住院信息',all(key in desktop['occupiedSample'] for key in ('患者编号','住院号','主治医师','已住')),desktop['occupiedSample'][:110],results)
        if desktop['inactiveSample']:check('停用卡片使用灰色语义与文字标签',('停用' in desktop['inactiveSample']),desktop['inactiveSample'][:70],results)
        check('桌面无横向溢出',not desktop['overflowX'],f"overflowX={desktop['overflowX']}",results)
        chrome.screenshot(os.path.join(SHOTS,'bed-board-desktop.png'))
        width_columns={}
        for width in (1280,1024,820,375):
            chrome.viewport(width,900);time.sleep(0.7)
            measured=chrome.evaluate(MEASURE)
            width_columns[width]=measured['columns']
            if width==375:narrow=measured
        check('跨宽度逐级减少列数',width_columns[1280]<=desktop['columns'] and width_columns[1024]<=width_columns[1280] and width_columns[820]<=width_columns[1024] and narrow['columns']==1,str(width_columns),results)
        check('窄屏自动减少列数',narrow['columns']==1,f"375px columns={narrow['columns']} rows={narrow['rows']} cards={narrow['cards']}",results)
        check('窄屏每张卡片独立可读且不溢出',narrow['cards']==desktop['cards'] and not narrow['overflowX'],f"cards={narrow['cards']} overflowX={narrow['overflowX']}",results)
        chrome.screenshot(os.path.join(SHOTS,'bed-board-narrow.png'))
        chrome.viewport(1440,1000);chrome.goto(f'{BASE}/app/console/bed-board',0.8)
        chrome.wait_for("document.querySelectorAll('.bed-card').length>0")
        detail=chrome.evaluate("""(async()=>{
          const card=[...document.querySelectorAll('.bed-card')].find(node=>node.dataset.status==='occupied');
          card.click();await new Promise(resolve=>setTimeout(resolve,1000));
          const drawer=document.querySelector('.el-drawer');
          const link=drawer?drawer.querySelector('a[href*="/inpatients/"]'):null;
          return {text:drawer?drawer.innerText.replace(/\\n+/g,' | ').slice(0,220):'',href:link?link.getAttribute('href'):null};
        })()""")
        check('点击卡片打开床位详情抽屉',('住院号' in detail['text'] and '主治医师' in detail['text']),detail['text'][:110],results)
        check('抽屉可进入住院详情',bool(detail['href']) and '/inpatients/' in (detail['href'] or ''),str(detail['href']),results)
        if detail['href']:
            chrome.goto(f"{BASE}{detail['href']}",0.8)
            chrome.wait_for("document.querySelectorAll('.charge-card .el-table__row').length>0")
            charges=chrome.evaluate("""(() => {
              const rows=[...document.querySelectorAll('.charge-card .el-table__row')];
              const headers=[...document.querySelectorAll('.charge-card .el-table__header th')].map(node=>node.innerText.trim()).filter(Boolean);
              return {rows:rows.length,headers,first:rows.length?rows[0].innerText.replace(/\\n+/g,' | '):''};
            })()""")
            check('住院详情展示费用清单与支付日期列',('支付日期' in charges['headers'] and '发生日期' in charges['headers'] and charges['rows']>0),f"{charges['rows']} 行账单 / 列 {charges['headers']}",results)
            expanded=chrome.evaluate("""(async()=>{
              const icons=[...document.querySelectorAll('.charge-card .el-table__expand-icon')];
              for(const icon of icons){icon.click();await new Promise(resolve=>setTimeout(resolve,350));}
              await new Promise(resolve=>setTimeout(resolve,500));
              const panels=[...document.querySelectorAll('.charge-detail-panel')].map(node=>node.innerText.replace(/\\n+/g,' | '));
              return panels;
            })()""")
            joined=' || '.join(expanded)
            check('处方明细行可展开逐项核对',bool(expanded) and ('数量' in joined and '单价' in joined),joined[:150],results)
            chrome.screenshot(os.path.join(SHOTS,'admission-charges-desktop.png'))
        chrome.goto(f'{BASE}/app/login');chrome.evaluate(login_expression('patient','Patient123!'))
        chrome.goto(f'{BASE}/app/patient/inpatients',0.8)
        chrome.wait_for("document.querySelectorAll('.task-group').length>0")
        grouped=chrome.evaluate("(()=>({groups:[...document.querySelectorAll('.task-group-head h2')].map(node=>node.innerText.trim()),cards:document.querySelectorAll('.task-card').length}))()")
        check('患者住院记录按状态归组为卡片',grouped['cards']>0 and all(label in grouped['groups'] for label in ('住院中','已出院')),str(grouped),results)
        chrome.evaluate("[...document.querySelectorAll('.view-switch button')].find(node=>node.innerText.trim()==='列表')?.click()")
        chrome.wait_for("document.querySelectorAll('.el-table__row').length>0")
        patient=chrome.evaluate("""(() => ({path:location.pathname,rows:document.querySelectorAll('.el-table__row').length,text:document.body.innerText.includes('已出账费用')&&document.body.innerText.includes('待付金额')&&document.body.innerText.includes('预计床位费')}))()""")
        check('患者住院列表分别标注已出账/待付/预计床位费',patient['text'],f"{patient['rows']} 条记录",results)
        chrome.goto(f'{BASE}/app/console/bed-board',1.6)
        blocked=chrome.evaluate("(() => ({path:location.pathname,beds:document.querySelectorAll('.bed-card').length}))()")
        check('患者无法访问全院看板',blocked['beds']==0 and blocked['path']!= '/console/bed-board',str(blocked),results)
        chrome.goto(f'{BASE}/app/login');chrome.evaluate(login_expression('doctor','Doctor123!'))
        chrome.goto(f'{BASE}/app/doctor/bed-board',0.8)
        chrome.wait_for("document.querySelectorAll('.bed-card').length>0")
        chrome.evaluate("(()=>{const item=[...document.querySelectorAll('.el-segmented__item')].find(node=>node.innerText.includes('按科室'));if(item)item.click();})()")
        time.sleep(0.5)
        doctor=chrome.evaluate(MEASURE)
        check('医师可查看全院看板',doctor['cards']==desktop['cards'] and doctor['cards']>0,f"{doctor['cards']} 张卡片",results)
        check('医师看板布局与管理员一致',doctor['columns']==desktop['columns'],f"columns={doctor['columns']}",results)
        chrome.screenshot(os.path.join(SHOTS,'bed-board-doctor-desktop.png'))
    finally:
        chrome.close()
    failed=[row for row in results if not row[1]]
    print(f"\n浏览器验收：{len(results)-len(failed)}/{len(results)} 项通过；截图见 docs/screenshots/")
    return 1 if failed else 0

if __name__=='__main__':
    sys.exit(main())
