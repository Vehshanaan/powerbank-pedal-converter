"""从 design.py 生成 KiCad PCB（.kicad_pcb），并用 Freerouting 自动布线。

流程：
  1. 解析 design.py 的器件表；按功能分区给出每个器件的位置与旋转。
  2. 加载封装（KiCad 官方库 / 立创库），把引用号、值、LCSC 写入字段。
  3. 每对 (ref, pin) 用网名建 NETINFO_ITEM 并设置到焊盘上 —— 连通性以本表为准，不依赖原理图标签。
  4. 校验：每个焊盘都有网络或属于"允许悬空"列表。
  5. 导出 DSN -> Freerouting -> 回注 SES -> 覆铜 -> 保存。
"""
import os
import re
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402

import pcbnew  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "V1_USBC_9V"))
PROJ = "V1_USBC_9V"
FP_LIBS = r"D:/Tools/Other/kicad-libs/footprints"
EASY = os.path.join(HERE, "libs", "easyeda_lcsc.pretty")
FR = r"D:/Tools/Other/freerouting/cli/freerouting-cli.exe"
MM = pcbnew.FromMM

# 封装 -> 库目录
FP_DIR = {
    "R_0603_1608Metric": "Resistor_SMD.pretty",
    "R_2512_6332Metric": "Resistor_SMD.pretty",
    "C_0603_1608Metric": "Capacitor_SMD.pretty",
    "C_0805_2012Metric": "Capacitor_SMD.pretty",
    "C_1206_3216Metric": "Capacitor_SMD.pretty",
    "Fuse_1812_4532Metric": "Fuse.pretty",
    "D_SMA": "Diode_SMD.pretty",
    "D_SMB": "Diode_SMD.pretty",
    "D_SOD-123": "Diode_SMD.pretty",
    "SOT-23": "Package_TO_SOT_SMD.pretty",
    "SOIC-8_3.9x4.9mm_P1.27mm": "Package_SO.pretty",
    "L_Bourns-SRN4018": "Inductor_SMD.pretty",
    "LED_0603_1608Metric": "LED_SMD.pretty",
    "TestPoint_Pad_D1.0mm": "TestPoint.pretty",
}
EASY_FP = {
    "TYPE-C-31-M-12": "USB-C_SMD-TYPE-C-31-M-12_1",
    "DC-005-TH": "DC-IN-TH_DC005",
    "WSON-6-1EP_2x2mm_P0.65mm": "QFN-6_L2.0-W2.0-P0.65-TL-EP",
}

# 布局（mm，x, y, 旋转）。上排 y≈25 为主功率路径，下排 y≈52 为检测与控制。
PLACE = {
    "J1": (13, 28, 0),
    # CC 下拉电阻贴近 J1 的 A5/B5 焊盘，短接到 GND，避免长距离并行
    # CC 下拉横放在 J1 正上方，A5/B5 短距离上引，GND 直接落在 J1 外壳地焊盘之间
    # R2 放在 B5(14.75,25.53) 正上方，CC2 只需一段垂直短线；R1 对应 A5
    "R1": (11.75, 18.0, 90), "R2": (14.75, 18.5, 90),
    "F1": (27, 25, 0), "D1": (36, 25, 0), "C1": (43, 25, 0), "C2": (46, 31, 0),
    "Q1": (51, 25, 90), "R3": (51, 32, 0), "D2": (51, 38, 0),
    "L1": (56, 25, 0), "D3": (63.5, 25, 0),
    "U2": (56, 34.5, 0), "C3": (44, 34, 0), "C4": (47, 43, 0),
    "R5": (61, 34, 90), "R4": (67, 37, 90), "R6": (61, 40, 0), "C7": (66, 40, 0), "C8": (70, 40, 0),
    "Q6": (66, 30, 0),
    "C5": (70, 25, 0), "C6": (75, 25, 0), "D6": (82.5, 25, 0),
    "U3": (75, 31, 0), "R7": (75, 18, 0), "C9": (80, 18, 0),
    "Q2": (92, 25, 0), "R21": (88, 33, 0), "D5": (92, 33, 90), "Q3": (96, 31, 0), "R23": (100, 31, 0), "R27": (104, 31, 0),
    "F2": (98, 25, 0), "D7": (105.5, 25, 0), "C15": (111.5, 25, 0), "J2": (125, 25, 0),
    # 下排：UV / OV / OC
    "U4": (50, 58, 0), "C10": (41, 64, 90), "R8": (41, 57, 0), "R9": (41, 70, 0), "C11": (45.5, 70, 0),
    "D4": (57.5, 58, 0), "R10": (57.5, 64, 0),
    "R11": (66, 58, 0), "R12": (66, 64, 0), "C12": (70.5, 58, 0),
    "R13": (45.5, 52, 90), "R14": (49.5, 52, 90), "R15": (53.5, 52, 90),
    "U6": (82, 58, 0), "C13": (72, 64, 90), "R16": (87, 52, 0), "R17": (76, 52, 90), "R18": (91, 64, 0),
    "R19": (86, 70, 0), "C14": (90.5, 70, 0), "R20": (95, 52, 0), "R28": (95, 58, 0),
    "D8": (104, 52, 0), "R24": (76, 64, 0), "R25": (104, 58, 0),
    "TP1": (100, 71, 0), "TP2": (104, 71, 0),
    "D9": (30, 58, 0), "R26": (34, 58, 0), "D10": (30, 64, 0),
}

# 允许悬空的引脚（外壳、未用信号）
NC_PINS = {
    ("J1", "A5"), ("J1", "B5"), ("J1", "A6"), ("J1", "A7"), ("J1", "B6"), ("J1", "B7"),
    ("J1", "A8"), ("J1", "B8"), ("J2", "3"), ("U3", "3"),
}


def load_fp(name):
    if name in EASY_FP:
        p = os.path.join(EASY, EASY_FP[name] + ".kicad_mod")
    else:
        p = os.path.join(FP_LIBS, FP_DIR[name], name + ".kicad_mod")
    fp = pcbnew.FootprintLoad(os.path.dirname(p), os.path.basename(p)[:-len(".kicad_mod")])
    if fp is None:
        raise SystemExit(f"cannot load footprint {name} from {p}")
    return fp


def check_place():
    refs = {p["ref"] for p in D.PARTS}
    missing = sorted(refs - set(PLACE))
    extra = sorted(set(PLACE) - refs)
    if missing or extra:
        raise SystemExit(f"PLACE mismatch: missing {missing} extra {extra}")


def build_board():
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_MinClearance = pcbnew.FromMM(0.15)
    ds.m_TrackMinWidth = pcbnew.FromMM(0.15)
    try:
        nc = board.GetDesignSettings().GetDefaultNetclass()
        nc.SetClearance(pcbnew.FromMM(0.15))
        nc.SetTrackWidth(pcbnew.FromMM(0.25))
        nc.SetViaDiameter(pcbnew.FromMM(0.6))
        nc.SetViaDrill(pcbnew.FromMM(0.3))
    except Exception as e:  # noqa: BLE001
        print("netclass warn:", e)

    nets = {}
    for name in D.POWER_NETS + sorted({n for p in D.PARTS for n in p["pins"].values()} - set(D.POWER_NETS)):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # 按引用号合并多个单元（U4/U6 的 A/B/电源共用同一封装）
    merged = {}
    order = []
    for p in D.PARTS:
        r = p["ref"]
        if r not in merged:
            merged[r] = dict(p, pins=dict(p["pins"]))
            order.append(r)
        else:
            for pin, net in p["pins"].items():
                if pin in merged[r]["pins"] and merged[r]["pins"][pin] != net:
                    raise SystemExit(f"{r}.{pin}: conflicting nets")
                merged[r]["pins"][pin] = net

    for ref in order:
        p = merged[ref]
        x, y, rot = PLACE[ref]
        fp = load_fp(p["unit"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)          # 先加入板子，FindPadByNumber 才会作用于本实例
        for pin, net in p["pins"].items():
            pad = fp.FindPadByNumber(pin)
            if pad is None:
                raise SystemExit(f"{ref}: pad {pin} not found in {p['unit']}")
            pad.SetNet(nets[net])

    # 校验：每个焊盘都有网络，或在 NC 名单里
    bad = []
    for fp in board.GetFootprints():
        nums = []
        for pad in fp.Pads():
            if pad.GetNumber():
                nums.append(pad.GetNumber())
        for num in nums:
            pad = fp.FindPadByNumber(num)
            if pad.GetNetCode() == 0 and (fp.GetReference(), num) not in NC_PINS:
                bad.append(f"{fp.GetReference()}.{num}")
    if bad:
        raise SystemExit("unassigned pads: " + ", ".join(bad))
    add_outline(board)
    return board


def add_outline(board):
    """板框：覆盖所有封装包围盒并留 3mm 边距，圆角矩形（用直线段近似）。"""
    box = None
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False, False)
        if box is None:
            box = [bb.GetPosition().x, bb.GetPosition().y,
                   bb.GetPosition().x + bb.GetSize().x, bb.GetPosition().y + bb.GetSize().y]
        else:
            box[0] = min(box[0], bb.GetPosition().x)
            box[1] = min(box[1], bb.GetPosition().y)
            box[2] = max(box[2], bb.GetPosition().x + bb.GetSize().x)
            box[3] = max(box[3], bb.GetPosition().y + bb.GetSize().y)
    m = pcbnew.FromMM(3)
    x0, y0 = (box[0] - m) // pcbnew.FromMM(1) * pcbnew.FromMM(1), (box[1] - m) // pcbnew.FromMM(1) * pcbnew.FromMM(1)
    x1, y1 = (box[2] + m + pcbnew.FromMM(1) - 1) // pcbnew.FromMM(1) * pcbnew.FromMM(1), (box[3] + m + pcbnew.FromMM(1) - 1) // pcbnew.FromMM(1) * pcbnew.FromMM(1)
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(*pts[i]))
        seg.SetEnd(pcbnew.VECTOR2I(*pts[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)
    print("outline mm:", [round(v / 1e6, 1) for v in (x0, y0, x1, y1)])


def main():
    os.makedirs(OUT, exist_ok=True)
    check_place()
    board = build_board()
    path = os.path.join(OUT, PROJ + ".kicad_pcb")
    pcbnew.SaveBoard(path, board)
    print("saved", path, "footprints", len(list(board.GetFootprints())),
          "nets", board.GetNetCount())
    print("ratsnest", board.GetConnectivity().GetUnconnectedCount(False))


if __name__ == "__main__":
    main()
