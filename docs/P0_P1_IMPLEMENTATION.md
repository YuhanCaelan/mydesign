# P0/P1 升级实施记录

> 对应计划：[UPGRADE_PLAN_V3.md](UPGRADE_PLAN_V3.md)。本文件记录实际落地范围、演示账号、关键路径与刻意保留的简化。

## 1. 已完成范围

### 1.1 角色与岗位

- `User.Role` 扩展为：管理员、科室事务员、医师、护士、患者。
- 新增事务员岗位 `User.Station`：排班、住院处、收费退费、药房、医技执行。
- `User` 增加 `department`、`station`、`ward`，用于科室范围与岗位识别。
- 管理员主栏目收口为：账号与科室、基础字典、审计日志。
- 排班写权限从医生/管理员迁移到「科室事务员·排班岗」；管理员保留 superuser 兜底。

### 1.2 急诊

- `Appointment` 增加 `visit_type`、`source`、`triage_level`、`arrived_at`，`slot` 改为可空。
- 新增 `POST /api/v1/appointments/emergency/`：由护士/事务员现场登记，无号源、必填分诊级别。
- 医生接诊队列按急诊优先展示；患者预约页提示“急诊不支持预约”。

### 1.3 医生工作区承载开单

- 接诊工作区新增「医嘱」页签，内部四栏：处方、检查、处置、住院。
- 处方、检查、处置、住院申请均通过弹窗在工作区内完成，自动关联当前病历。
- 处方选择药品时显示库存；库存不足允许开具、药房发药时再次校验。
- 「本次病历」增加「套用模板」：选疾病模板，只填左右/轻重/病程，生成后可改。

### 1.4 费用与执行闭环

- 缴费与发药/执行分离：支付只把账单置为已缴费；药房确认后才发药并扣库存。
- 检查由医技岗确认开始（未缴费不可开始）；处置由医技/护士确认开始与完成。
- 医生工作区显示每张医嘱的派生状态：待缴费、待发药/待执行、执行中、已完成、已退费、已取消。
- 新增门诊退费：`POST /api/v1/billing-records/{id}/refund/`，仅收费岗，仅“已缴费 + 未发药/未执行”全额退费；生成 `RefundRecord`，回写账单已退费并取消关联医嘱。

### 1.5 疾病模板

- 新增 `RecordTemplate`，支持科室、诊断、主诉/现病史/既往史/查体/处理、变量 JSON。
- 通过 `seed_p0_upgrade` 写入 8 个模板（偏头痛、上呼吸道感染、急性胃肠炎、高血压复诊、膝关节骨关节炎、腰椎间盘突出、皮肤软组织感染、换药/拆线）。

### 1.6 报告二维码

- 新增 `ReportShareToken`：报告、token、7 天有效期、访问次数、撤销标记。
- `POST /api/v1/examination-reports/{id}/share/` 生成分享 token 与 URL。
- 前端使用 `qrcode` 生成二维码，显示在报告阅读器中；扫码进入公开 `/app/share/report/:token` 页面查看报告与附件。
- 二维码只保存安全链接，不包含影像二进制；过期 token 返回 403。

### 1.7 住院主线

- `InpatientAdmission` 增加 `received_at`、`receiving_nurse`、`admission_staff`。
- 新增 `InpatientRecord`（一次住院一份病志）与 `InpatientOrder`（长期/临时医嘱）。
- 流程：医生申请住院 → 住院处分床/入院 → 护士接诊 → 医生写病志/开医嘱 → 护士执行 → 医生/住院处办理出院。
- 新增页面 `/app/inpatient/:admissionId`，医生可写病志与医嘱，护士可执行医嘱；住院处页面可分配床位、办理入院/出院。

### 1.8 岗位工作台

- `/app/staff`：按岗位展示排班、住院处、收费退费、药房发药、医技执行。
- `/app/nurse`：急诊登记、住院接诊、医嘱执行。
- 护士/事务员登录后自动从 `/dashboard` 跳转到各自工作台。

## 2. 演示账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `Admin123!` |
| 医师 | `doctor` | `Doctor123!` |
| 患者 | `patient` | `Patient123!` |
| 排班岗 | `schedule_staff` | `Staff123!` |
| 住院处 | `admission_staff` | `Staff123!` |
| 收费岗 | `cashier` | `Staff123!` |
| 药房岗 | `pharmacy` | `Staff123!` |
| 医技岗 | `tech` | `Staff123!` |
| 护士 | `nurse` | `Nurse123!` |

账号由 `python manage.py seed_p0_upgrade` 创建/重置；可重复执行。

## 3. 关键路由

| 路由 | 角色 | 说明 |
| --- | --- | --- |
| `/staff` | 事务员 | 岗位工作台 |
| `/nurse` | 护士 | 护理工作台 |
| `/doctor/visits/:id` | 医师 | 接诊工作区（含医嘱页签） |
| `/inpatient/:id` | 医师/护士 | 住院病志与长期/临时医嘱 |
| `/doctor/records`、`/patient/records` | 医师/患者 | 诊疗档案（历史病历 + 报告） |
| `/share/report/:token` | 公开 | 扫码报告页 |

## 4. 刻意保留的简化

1. **角色数量**：没有拆成“排班员/住院处/收费员/药房/医技/护士”六个独立角色，而是 1 个事务员角色 + 岗位字段，避免毕业设计角色爆炸。
2. **就诊模型**：没有新建 `Encounter` 大模型，而是扩展 `Appointment`；模型名仍叫 Appointment，但支持急诊无号源。
3. **住院医嘱**：只做临床病志与长期/临时医嘱执行，不做住院药房计费、护理计划、MAR、交接班、手术室/麻醉。
4. **日间手术**：只作为处置目录的一个类别选项，不做手术间排程、术前评估、麻醉与复苏。
5. **退费**：只做全额、未发药/未执行的退费；部分退费、退药入库未实现。
6. **二维码**：不把影像放进二维码；扫码页对 JPG/PNG 预览，PDF/DICOM 提供下载。
7. **管理员兜底**：superuser 仍可调用业务接口，用于演示数据与异常处理；日常前端入口已收口。
8. **账号管理 UI**：事务员/护士账号当前由 `seed_p0_upgrade` 创建；管理员 UI 仍主要管理医师/患者，后续可扩展。
9. **支付方式**：保留演示支付；患者可自付，收费岗也可代收。
10. **模板管理**：模板由种子命令写入；暂未做管理员模板编辑页面。

## 5. 验证结果

```bash
python manage.py check                          # 通过
python manage.py makemigrations --check        # No changes detected
python manage.py test healthcare                # 60 项通过
cd frontend && npm run build                    # 通过
python verify_navigation_ui.py                  # 49/49 通过
python verify_archive_ui.py                     # 32/32 通过
python verify_p0p1_ui.py                        # 22/22 通过
```

## 6. 主要文件

- 后端：`healthcare/models.py`、`serializers.py`、`views.py`、`permissions.py`、`urls.py`、`migrations/0010_*`、`management/commands/seed_p0_upgrade.py`
- 前端工作区：`views/doctor/VisitWorkspace.vue`、`components/clinic/*`、`views/shared/InpatientWorkspace.vue`
- 岗位/护理：`views/staff/Workspace.vue`、`views/nurse/Workspace.vue`
- 患者：`views/shared/SharedReport.vue`、`components/reports/ReportReader.vue`
- 验收：`verify_p0p1_ui.py`
