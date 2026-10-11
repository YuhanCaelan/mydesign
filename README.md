# 基于 Vue 与 Django 的智慧医疗管理系统

面向中小型医疗机构的教学演示系统，采用 Vue 3、TypeScript、Element Plus、Django REST Framework、JWT 与 SQLite 构建。

新系统围绕管理员、医师、患者三类角色和一条核心业务流程设计：

> 管理员配置科室、医师与排班 → 患者选择号源预约 → 医师接诊并确认病历 → 开具处方与检查申请 → 检查医师反馈并发布报告 → 完成诊疗 → 住院/费用等后续业务

旧开源医院系统代码仍保留在仓库中作为字段和业务参考，但标准 `manage.py` 已切换到新的 `smartmedical` 项目，新系统使用独立数据库 `smartmedical.sqlite3`，不会继续依赖旧系统的十类角色和五十余个通用模型页面。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios、ECharts
- 后端：Django、Django REST Framework、Simple JWT
- 数据库：SQLite
- 文件：本地受控文件目录，必须通过鉴权 API 下载

## 快速启动

项目使用已有 Conda 环境 `hos`：

```bash
conda run -n hos python manage.py migrate
conda run -n hos python manage.py seed_smartmedical --reset
cd frontend
npm install
npm run build
cd ..
conda run -n hos python manage.py runserver 127.0.0.1:8000
```

访问：`http://127.0.0.1:8000/app/`

演示账号：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `Admin123!` |
| 医师 | `doctor` | `Doctor123!` |
| 患者 | `patient` | `Patient123!` |

首次或需要固定重建答辩数据时使用 `--reset`；它只会清空 `smartmedical.sqlite3` 和 `smartmedical_media`，不影响旧系统数据库。不带 `--reset` 且演示账号已存在时，命令会安全退出。

## 新项目结构

```text
smartmedical/            新 Django 项目配置
healthcare/              新智慧医疗核心领域与 /api/v1 接口
frontend/                Vue 3 三角色前端
smartmedical.sqlite3     新系统 SQLite 数据库（本地生成）
smartmedical_media/      受控医疗文件（本地生成）
legacy_manage.py         旧系统兼容入口
```

## 已实现的核心规则

- 患者可自主注册；医师账号只能由管理员创建。
- 预约绑定离散号源，数据库一对一约束防止重复占用。
- 预约只允许按 `待就诊 → 就诊中 → 已完成` 转换，并支持取消与爽约。
- 医师只能处理自己的预约和诊疗关系内患者。
- 全院医师均可协作处理检查申请；申请医师与实际执行、报告医师可以不同。
- 患者只能读取本人数据，且只能查看已确认病历和已发布检查报告。
- 病历确认后禁止覆盖，只能追加带作者和时间的更正记录。
- 已确认病历可直接完成并归档诊疗；系统同时提供住院、费用结算和药品库存链路。
- 医师可从接诊列表进入统一诊疗工作区，查看患者档案、历史病历和本次处方/检查/住院事项。
- 床位在入院时以事务占用，取消或出院时自动释放；出院按日费快照和住院天数生成唯一账单。
- 检查申请关联检查目录与价格快照，自动生成唯一检查账单；取消时同步取消未支付账单。
- 医师开具处方时自动生成药品账单；患者支付后在同一事务中扣减库存、完成发药并计入结算收入。
- 药品入库、人工调整和处方发药均留存可追溯库存流水。
- 演示医师为绑定全部演示科室的超级医师，便于跨科室流程展示。
- 医疗附件不暴露静态 `/media/` 地址，下载时再次执行对象级权限检查。
- AI 服务默认停用，没有模型时不会生成模拟诊断结论。

## 验证

```bash
conda run -n hos python manage.py check
conda run -n hos python manage.py test healthcare
cd frontend && npm run build
```

## 旧系统

如确需核对旧 Django Templates 系统，可执行：

```bash
conda run -n hos python legacy_manage.py runserver 127.0.0.1:8001
```

旧系统不再作为新毕业设计的产品入口，也不建议继续向其添加功能。

## 使用边界

本项目仅用于毕业设计和教学演示，不应录入未经授权的真实患者信息，也不能直接作为临床诊疗系统投入生产。
