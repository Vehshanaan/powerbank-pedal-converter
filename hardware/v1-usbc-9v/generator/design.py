"""V1 USB-C -> 9V 转换器：电路定义（唯一设计源）。

原理图生成器、PCB 生成器、检查器都只读本文件。
每颗器件：ref / value / 符号库 lib / 封装 unit / 立创料号 lcsc / 引脚网络 pins。

安全模型（全硬件，无固件；用户 2026-11-11 确认：插上即输出、单口 200mA）：
  输出开关 Q2(P-MOS) 栅极默认由 R21 拉地 => 导通；
  三路开集比较器经隔离二极管共同驱动 EN 上拉点，任一动作都让 Q3 导通、Q2 栅极升到 VBST、输出断开：
      UV : VIN 经 100k/100k 低于 4.3V 稳压管基准（VIN < 约 8.2V）
      OV : VBST 经 220k/62k 高于 2.5V 基准（VBST > 11.4V）
      OC : 输出电流 > 220mA（20mR 采样、50 倍差分、与 2.5V 缓冲基准比较）
  OV 触发时 Q6 同时拉低 TPS61170 的 FB（crowbar），让升压主动降压。
  硬保护：D6(SMAJ12A) 直接钳在 VBST 对地；F2(200mA 自恢复保险) 串在输出。
  拔电：VBST 放电后 Q2 栅极仍有 R21 到地 => 关断；Q1 体二极管朝 VBUS，不倒灌。
"""

STATE = dict(vin_nom=5.0, vout=9.03, iout_max=0.20, uv_threshold=8.2,
             ov_threshold=11.4, oc_threshold=0.22)

POWER_NETS = ["GND", "VBUS", "VIN", "VBST", "PEDAL", "PEDAL_OUT"]

PARTS = []


def P(ref, value, lib, unit, lcsc, **pins):
    PARTS.append(dict(ref=ref, value=value, lib=lib, unit=unit, lcsc=lcsc, pins=pins))


R = "SELF:R"
C = "SELF:C"
L = "SELF:L"
F = "SELF:F"
D = "SELF:D"
TVS = "SELF:TVS"
LED = "SELF:LED"
Z = "SELF:ZENER"
NP = "EASY:MMBT3904-C20526"
PM = "EASY:AO3401A"

# 1. USB-C
P("J1", "TYPE-C-31-M-12", "EASY:TYPE-C-31-M-12", "TYPE-C-31-M-12", "C165948",
  A1B12="GND", B1A12="GND", A4B9="VBUS", B4A9="VBUS", A5="CC1", B5="CC2",
  **{"1": "GND", "2": "GND", "3": "GND", "4": "GND"})
P("R1", "5.1k", R, "R_0603_1608Metric", "C23186", **{"1": "CC1", "2": "GND"})
P("R2", "5.1k", R, "R_0603_1608Metric", "C23186", **{"1": "CC2", "2": "GND"})

# 2. 输入保护（Q1：反灌阻断，S=VBUS、D=VIN）
P("F1", "500mA", F, "Fuse_1812_4532Metric", "C17313", **{"1": "VBUS", "2": "VIN"})
P("D1", "SMBJ5.0A", TVS, "D_SMB", "C61069", **{"1": "VIN", "2": "GND"})
P("C1", "22uF", C, "C_1206_3216Metric", "C2178233", **{"1": "VIN", "2": "GND"})
P("C2", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "VIN", "2": "GND"})
P("Q1", "AO3401A", PM, "SOT-23", "C15127", **{"2": "VBUS", "1": "GATE1", "3": "VIN"})
P("R3", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "GATE1", "2": "GND"})
P("D2", "BZT52C10", Z, "D_SOD-123", "C2103", **{"1": "VBUS", "2": "GATE1"})

# 3. 升压 TPS61170（FB 20k/127k -> 9.03V）
P("U2", "TPS61170DRVR", "EASY:TPS61170DRVR", "WSON-6-1EP_2x2mm_P0.65mm", "C15163",
  **{"6": "VIN", "3": "GND", "4": "SW", "1": "FB", "2": "COMP", "5": "VIN", "7": "GND"})
P("L1", "10uH", L, "L_Bourns-SRN4018", "C602032", **{"1": "VIN", "2": "SW"})
P("D3", "SS34", D, "D_SMA", "C8678", **{"1": "SW", "2": "VBST"})
P("C3", "4.7uF", C, "C_0805_2012Metric", "C354262", **{"1": "VIN", "2": "GND"})
P("C4", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "VIN", "2": "GND"})
P("C5", "4.7uF", C, "C_0805_2012Metric", "C354262", **{"1": "VBST", "2": "GND"})
P("C6", "22uF", C, "C_1206_3216Metric", "C2178233", **{"1": "VBST", "2": "GND"})
P("R4", "20k", R, "R_0603_1608Metric", "C4184", **{"1": "FB", "2": "GND"})
P("R5", "127k", R, "R_0603_1608Metric", "C23261", **{"1": "FB", "2": "VBST"})
P("R6", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "COMP", "2": "GND"})
P("C7", "680pF", C, "C_0603_1608Metric", "C1445", **{"1": "COMP", "2": "GND"})
P("C8", "10pF", C, "C_0603_1608Metric", "C1547", **{"1": "COMP", "2": "GND"})
# crowbar：OV_B 高 -> Q6 导通 -> FB 被 Q6 拉到地 -> 升压降到最低
P("Q6", "MMBT3904", NP, "SOT-23", "C20526", **{"1": "OV", "2": "GND", "3": "FB"})
P("R28", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "OV", "2": "GND"})

# 4. 2.5V 基准
P("U3", "LM4040C25", "SELF:REF", "SOT-23", "C44215", **{"1": "VREF", "2": "GND"})
P("R7", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "VBST", "2": "VREF"})
P("C9", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "VREF", "2": "GND"})

# 5. 比较器 U4 = UV(A) / OV(B)；U4 由 VIN 供电（≤18V）
P("U4", "LM2903A", "SELF:CMP", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"1": "UV", "2": "UVP", "3": "UVREF"})
P("U4", "LM2903B", "SELF:CMP", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"7": "OV", "6": "OVP", "5": "VREF"})
P("U4", "LM2903-PWR", "SELF:VCC", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"8": "VIN", "4": "GND"})
P("C10", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "VIN", "2": "GND"})
P("R8", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "VIN", "2": "UVP"})
P("R9", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "UVP", "2": "GND"})
P("D4", "BZT52C4V3", Z, "D_SOD-123", "C2115", **{"1": "VIN", "2": "UVREF"})
P("R10", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "UVREF", "2": "GND"})
P("C11", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "UVP", "2": "GND"})
P("R11", "220k", R, "R_0603_1608Metric", "C22961", **{"1": "VBST", "2": "OVP"})
P("R12", "62k", R, "R_0603_1608Metric", "C23221", **{"1": "OVP", "2": "GND"})
P("C12", "10nF", C, "C_0603_1608Metric", "C1589", **{"1": "OVP", "2": "GND"})
P("R13", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "OV", "2": "VIN"})
P("R14", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "EN", "2": "UV"})
P("R15", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "EN", "2": "OV"})

# 6. 比较器 U6 = OC(A) / 基准缓冲(B)；U6 由 VBST 供电
# + 端为采样差分（高于基准=过流）；U6B 把 2.5V 基准缓冲到 OCREF
P("U6", "LM2903A", "SELF:CMP", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"1": "OC", "2": "OCREF", "3": "OCP"})
P("U6", "LM2903B", "SELF:CMP", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"7": "OCREF", "6": "OCP", "5": "VREF"})
P("U6", "LM2903-PWR", "SELF:VCC", "SOIC-8_3.9x4.9mm_P1.27mm", "C7549", **{"8": "VBST", "4": "GND"})
P("C13", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "VBST", "2": "GND"})
P("R16", "0.02", R, "R_2512_6332Metric", "C105366", **{"1": "Q2D", "2": "PEDAL"})
P("R17", "1k", R, "R_0603_1608Metric", "C21190", **{"2": "PEDAL", "1": "OCN"})
P("R18", "27k", R, "R_0603_1608Metric", "C22967", **{"1": "OCN", "2": "OCP"})
P("R19", "1k", R, "R_0603_1608Metric", "C21190", **{"1": "Q2D", "2": "OCP"})
P("C14", "100nF", C, "C_0603_1608Metric", "C14663", **{"1": "OCP", "2": "OCREF"})
P("R20", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "EN", "2": "OC"})

# 7. 输出开关：Q2 栅极默认拉地=导通；EN 低 -> Q3 关断 -> R22 把栅极升到 VBST=关断
P("Q2", "AO3401A", PM, "SOT-23", "C15127", **{"2": "VBST", "1": "GATE2", "3": "Q2D"})
P("R21", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "GATE2", "2": "GND"})
P("D5", "BZT52C8V2", Z, "D_SOD-123", "C173432", **{"1": "VBST", "2": "GATE2"})
P("Q3", "MMBT3904", NP, "SOT-23", "C20526", **{"1": "Q3B", "2": "GND", "3": "GATE2"})
P("R23", "100k", R, "R_0603_1608Metric", "C22775", **{"1": "Q3B", "2": "GND"})
P("R24", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "UV", "2": "Q3B"})
P("D8", "BAT54S", "EASY:BAT54S-SOT23", "SOT-23", "C8592", **{"1": "UV", "2": "OV", "3": "Q3B"})
P("R25", "10k", R, "R_0603_1608Metric", "C25804", **{"1": "EN", "2": "VBST"})

# 8. 输出钳位、保险、插座
P("D6", "SMAJ12A", TVS, "D_SMA", "C113957", **{"1": "VBST", "2": "GND"})
P("J2", "DC-005-5.5x2.1", "EASY:DC005_C431533", "DC-005-TH", "C431533",
  **{"1": "PEDAL_OUT", "2": "GND"})
P("F2", "200mA", F, "Fuse_1812_4532Metric", "C17313", **{"1": "PEDAL", "2": "PEDAL_OUT"})
P("D7", "SMBJ12A", TVS, "D_SMB", "C10215", **{"1": "PEDAL_OUT", "2": "GND"})
P("C15", "47uF", C, "C_1206_3216Metric", "C6119973", **{"1": "PEDAL_OUT", "2": "GND"})
P("TP1", "TEST_VBST", "SELF:TP", "TestPoint_Pad_D1.0mm", "", **{"1": "VBST"})
P("TP2", "TEST_OUT", "SELF:TP", "TestPoint_Pad_D1.0mm", "", **{"1": "PEDAL_OUT"})

# 9. 指示
P("D9", "LED_GREEN", LED, "LED_0603_1608Metric", "C965804", **{"1": "VIN", "2": "LEDG"})
P("R26", "4.7k", R, "R_0603_1608Metric", "C23162", **{"1": "LEDG", "2": "GND"})
P("D10", "LED_RED", LED, "LED_0603_1608Metric", "C965799", **{"1": "VIN", "2": "LEDR"})
P("R27", "1k", R, "R_0603_1608Metric", "C21190", **{"1": "LEDR", "2": "Q3B"})
