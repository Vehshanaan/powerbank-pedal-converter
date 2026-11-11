# Repository Guidelines

## 项目目标

设计一款"充电宝 USB-C → 效果器 9V（中心负）"的小型电源板，交付物是**可以直接投嘉立创的成套制造文件**（Gerber、钻孔、坐标、BOM、下单说明、测试步骤），而不只是文档。

- `docs/01-需求/`：用户原始需求。
- `docs/02-方案/`：架构与安全设计（早期稿，最终以 PCB 与 `generator/design.py` 为准）。
- `docs/03-原理设计/`：电气指标、器件、保护行为。
- `docs/04-元件与BOM/`：BOM 相关说明（实际 BOM 在 release）。
- `docs/05-PCB与下单/`：嘉立创下单参数、组装与上电检查。
- `docs/06-测试与验收/`：测试步骤与记录模板。
- `docs/07-评审/`：独立评审的原始意见与处理结论。
- `hardware/v1-usbc-9v/generator/`：**设计源与构建脚本**（唯一真相）。
- `hardware/v1-usbc-9v/V1_USBC_9V/`：生成的 KiCad 工程（原理图、PCB、DRC 报告）。
- `hardware/v1-usbc-9v/release/`：投板文件包（gerber/、坐标、BOM）。
- `hardware/v1-usbc-9v/route/`：自动布线的 DSN/SES 与日志。

## 构建命令

必须用 KiCad 自带 Python（有 pcbnew）：

```bash
cd hardware/v1-usbc-9v
"C:/Users/yuanrunze.vdi/AppData/Local/Programs/KiCad/10.0/bin/python.exe" generator/build_all.py
```

它会依次：生成未布线 PCB → 导出 DSN → Freerouting 自动布线 → 回注 → 铺铜/丝印/NPTH → DRC（必须 0 违规 0 未连接）→ 出 Gerber/钻孔/坐标/BOM。

单独步骤：

```bash
python generator/gen_sch.py      # 原理图（仅供阅读，不作为网表来源）
python generator/gen_pcb.py      # 只生成 PCB
python generator/check_netlist.py
python generator/geometry_check.py
```

## 关键约束

- **网表唯一来源是 `generator/design.py`**。KiCad 原理图的标签网表在本机 KiCad 10 上会丢电源网络，不可作为判据。
- 自动布线只允许 `Freerouting 2.1.0` + `-Djava.awt.headless=true`；2.5 版会弹窗，禁止使用。
- 设计规则：间距 0.1 mm、线宽 ≥ 0.15 mm（嘉立创经济型能力），见 `V1_USBC_9V.kicad_dru`。
- 本机有 ESAFENET 透明加密驱动：**不要用内联 python 打补丁修改脚本**，改文件用 Write/Edit 整段替换，改完立即 `ast.parse` 校验。

## 文档与提交

- 中文正文，保留英文型号与命令；文件名沿用"日期 + 主题"。
- 提交使用简短中文说明，每次围绕一个目的；提交前 `git status --short` 确认范围，不要 `git add -A`。
