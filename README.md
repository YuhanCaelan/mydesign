# 智慧医疗管理系统

基于 Vue 3 与 Django 的教学演示项目，覆盖管理员、医师、患者三个角色，将预约、接诊、病历、检查、处方、住院和费用串成一条可操作的业务流程。界面采用按角色组织的主栏目与文件夹式子页签，便于在同一工作区完成相关任务。

> 本项目用于毕业设计和教学演示。数据和支付流程均为演示用途，不可直接用于真实诊疗或收费。

## 主要功能

| 角色 | 可用工作区 |
| --- | --- |
| 管理员 | 人员与科室、门诊排班与就诊、医疗资源、住院与床位、账单与运营统计 |
| 医师 | 接诊队列、患者档案与历次病历、处方与检查、住院记录和床位看板 |
| 患者 | 医师与号源预约、病历与检查报告、住院信息、账单及按周期统计的检查和药品费用 |

典型流程：管理员配置科室、医师、号源和资源 → 患者预约 → 医师接诊、查阅患者既往病历与检查，记录本次诊疗 → 开具处方或检查 → 发布报告、处理账单 → 按需办理住院与出院。

系统还提供科室当日就诊概览、按医师与排班关联的门诊就诊视图，以及按科室和病区组织的床位看板。病历确认后保留更正记录；患者只能查看自己的已确认病历和已发布报告。主要业务列表提供卡片与紧凑列表视图，工作台用状态矩阵、收入扇形图等方式展示关键指标。

## 技术结构

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、ECharts。
- 后端：Django、Django REST Framework、Simple JWT；接口统一位于 `/api/v1/`。
- 数据：SQLite；医疗附件通过鉴权接口访问。本地数据库、附件和前端构建产物不纳入版本控制。

```text
frontend/             Vue 前端与页面组件
healthcare/           业务模型、接口、权限、迁移、测试与演示数据命令
smartmedical/         Django 配置与路由
manage.py             当前系统的 Django 管理入口
```

## 本地运行

准备 Python、Node.js 和 npm，然后在项目根目录执行：

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_smartmedical
cd frontend
npm ci
npm run build
cd ..
python manage.py runserver 127.0.0.1:8000
```

打开 <http://127.0.0.1:8000/app/>。`seed_smartmedical` 会生成虚构的演示数据；若演示管理员已存在，该命令会直接退出。**`seed_smartmedical --reset` 会清空当前系统数据并重建演示数据**，仅在明确需要重置本地演示环境时使用。

演示账号由数据命令创建：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `Admin123!` |
| 医师 | `doctor` | `Doctor123!` |
| 患者 | `patient` | `Patient123!` |

开发前端时可在 `frontend/` 执行 `npm run dev`；Vite 将 `/api` 请求代理到本地 Django 服务。

## 验证

```bash
python manage.py check
python manage.py test healthcare
cd frontend && npm run build
```
