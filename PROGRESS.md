# 设计进度

最后更新：2026-11-11 16:30

## 状态：V1 暂缓投板（独立安全评审存在 P0 阻断项；DRC 0 违规 ≠ 功能安全）

用户需求：充电宝 USB-C → 效果器 9V（中心负），**插上即输出、单口 200mA、不做内置电池**；安全第一；交付"能无脑投板的结果图"；文件分类；多模型干净上下文评审（注意开销）。

**安全提示（2026-11-11）**：独立静态复核发现 Boost 整流极性、输出开关关断逻辑、输入保险旁路、过流/过压/欠压检测与补偿网络等阻断项。当前 `release/` 制造文件仅供审阅，不应直接下单、上电进行故障注入或连接效果器。详见 `docs/07-评审/20261111 安全与使用体验复核.md`。上述结论尚未经硬件实测验证。

## 交付物

- 投板文件包：`hardware/v1-usbc-9v/release/`
  - `gerber/`：F/B 铜层、阻焊、钢网、丝印、Fab、板框、钻孔、钻孔图、job 文件
  - `V1_USBC_9V-pos.csv`、`V1_USBC_9V-bom.csv`（40 行，含立创料号）
  - `preview.pdf`（版面预览）
- KiCad 工程：`hardware/v1-usbc-9v/V1_USBC_9V/`（.kicad_pcb / .kicad_dru / .kicad_pro / drc.rpt / `*.routed_backup.kicad_pcb`）
- 设计源与构建：`hardware/v1-usbc-9v/generator/`
  - `design.py`（唯一网表来源）、`klib.py`、`gen_pcb.py`（布局+封装+网络）、`build_all.py`（布线/后处理/DRC/出包）、`release.py`、`gen_sch.py`（阅读用原理图）、`check_netlist.py`、`geometry_check.py`
- 文档：`docs/01~07`（需求、方案、原理说明、下单与组装、测试步骤、评审记录）

## 复现

```bash
cd hardware/v1-usbc-9v
"C:/Users/yuanrunze.vdi/AppData/Local/Programs/KiCad/10.0/bin/python.exe" generator/build_all.py
```

依赖：KiCad 10（pcbnew + kicad-cli）、JRE 25、`D:/Tools/Other/freerouting/fr210.jar`（2.1.0，必须 `-Djava.awt.headless=true`）。

## 已知待办

1. 板级实测（`docs/06-测试与验收/`），特别是 DC-005 中心针极性。
2. 布线为自动布线 + 少量手工补线（CC2），如需更美观可手工优化电源回路。
