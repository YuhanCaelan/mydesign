# 旧版 Vue 迁移记录（仅供历史参考）

> 本文记录的是早期“复用全部旧模型”的迁移方案，已被新的三角色 `smartmedical + healthcare + frontend` 架构取代。当前启动、接口和验收方式以根目录 `README.md` 与 `frontend/docs/REFACTOR_ROADMAP.md` 为准；请勿继续按照本文扩展旧通用工作区。

原项目的 `templates/` 中有 162 个 HTML 文件；其中包括布局片段、重复的列表/表单/详情页及打印页。新前端保留 Django 模型和数据库，通过 DRF 向 Vue 提供真实数据。53 个业务模型集中在 `/app/workspace/<资源名>`，其元数据、列表、详情、创建、编辑和受权限控制的删除均由 `/api/workspace/` 提供；患者、预约、护理、报表、个人中心和用户管理有专用页面。

| 原模板目录 | Vue 页面/入口 | 特殊业务 |
| --- | --- | --- |
| `accounts`, `core`, `base` | `/app/login`, `/app/`, `/app/profile`, `/app/users` | 三种角色工作台、个人身份、管理员用户权限 |
| `hospitals`, `departments`, `employees`, `doctors`, `hr` | 侧栏“组织与人员”“临床诊疗”下的工作区 | 排班/号源、考勤、请假审批、科室与人员档案 |
| `patients`, `appointments`, `opd`, `ipd` | `/app/patients`, `/app/patients/<id>`, `/app/appointments` 及临床工作区 | 360° 病历、预约状态、门诊、住院转床/出院 |
| `pharmacy`, `laboratory`, `radiology` | “医技与药房”工作区 | 处方发药、检验/影像结果、打印单据、药品库存/临期预警 |
| `billing`, `insurance` | “收费与保险”工作区 | 发票明细、缴费和收据、欠费筛选、发票打印 |
| `nursing`, `ambulance`, `inventory`, `notifications`, `auditlogs` | “护理与运营”工作区、`/app/nursing` | 护理任务/体征、救护车状态、采购入库、通知、审计 |
| `reports` | `/app/reports` | 7 类真实报表，CSV、XLSX、PDF 导出 |

`GET /api/workspace/catalog/` 按当前账号权限生成精简侧栏（23 个主要业务入口）；53 个原业务 API 仍保留，细目页面可通过关联入口或原链接访问。后端的 `permitted()`、`scoped_queryset()` 和原有 DRF 权限类执行最终校验。患者不是登录账号；新建档案由模型生成 `患者-000001` 起的业务编号，API 要求中文姓名及中国大陆 11 位手机号码。医师可跨科室读取患者历史，但只能修改自己负责的诊疗记录。

第一阶段权限升级后，角色、资源操作与数据范围统一定义在 `api/access.py`，详见 `ACCESS_POLICY.md`；原有旧角色不再可用于新 API 登录。

## 本机启动

```bash
conda run -n hos python manage.py migrate
cd frontend && npm install && npm run build
cd .. && conda run -n hos python manage.py runserver 127.0.0.1:8000
```

访问 `http://127.0.0.1:8000/app/`。开发热更新可另运行 `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`，并访问 `http://127.0.0.1:5173/`；Vite 将 `/api/` 代理到 Django。患者附件由受权限控制的 `/api/workspace/<资源>/<编号>/file/<字段>/` 下载，头像由 `/api/profile/avatar/` 读取，`/media/` 不直接公开。后端测试为 `conda run -n hos python manage.py test api`，前端检查为 `cd frontend && npm run build`。

## 部署边界

当前是本机开发配置（SQLite、`DEBUG=True`、开发服务器）。面向真实医院数据上线前，必须设置环境化密钥、受限的 `ALLOWED_HOSTS`、HTTPS、正式静态文件服务、数据库备份及附件审计；不能直接把开发服务器暴露到公网。原 Django Templates 路由仍保留，便于核对旧业务，不再作为新前端导航入口；旧模板中的直接 `/media/` 附件链接已停用，应使用新的受控下载 API。

2026-10-10 已依用户要求清空本地演示库中的 25 份患者档案及 1398 条关联诊疗/财务/护理数据，同时清空 10 条独立患者救护车请求、37 条患者相关审计、3 条患者通知，并释放 8 张床位。清空前备份位于 `backups/db-before-patient-clear-20261010.sqlite3`；数据库保持 0 份患者档案，不自动补入演示患者。旧演示库中患者与预约关联不一致的数据也随之清除。`seed_demo` 是破坏性的旧版全库重置脚本，当前默认拒绝运行，切勿用它恢复旧版英文演示患者。
