"""元件库辅助：立创 .kicad_sym 解析 + 统一黑盒引脚布局。

坐标：符号库内 Y 向上；direction 表示引脚朝外的方向。
所有器件在原理图中都使用本模块生成的统一符号（矩形黑盒或两引脚符号），
避免第三方符号格式差异带来的连接问题。
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.join(HERE, "libs")

# 两引脚件：(号, 名, 端点x, 端点y, 朝外方向)
TWO_PIN = {
    "R": [("1", "~", 0, 5.08, "up"), ("2", "~", 0, -5.08, "down")],
    "C": [("1", "~", 0, 5.08, "up"), ("2", "~", 0, -5.08, "down")],
    "L": [("1", "~", 0, 5.08, "up"), ("2", "~", 0, -5.08, "down")],
    "F": [("1", "~", 0, 5.08, "up"), ("2", "~", 0, -5.08, "down")],
    "D": [("1", "K", 0, 5.08, "up"), ("2", "A", 0, -5.08, "down")],
    "TVS": [("1", "~", 0, 5.08, "up"), ("2", "~", 0, -5.08, "down")],
    "LED": [("1", "A", 0, 5.08, "up"), ("2", "K", 0, -5.08, "down")],
    # 比较器单元与电源单元（LM2903 拆成三块，避免多单元符号）
    "CMP": [("3", "PLUS", -10.16, 2.54, "right"), ("2", "MINUS", -10.16, -2.54, "right"), ("1", "OUT", 10.16, 0, "left")],
    "VCC": [("8", "VPLUS", -2.54, 5.08, "down"), ("4", "VMINUS", -2.54, -5.08, "up")],
    "GND": [("1", "GND", 0, 0, "down")],
    "REF": [("1", "K", -7.62, 2.54, "right"), ("2", "A", -7.62, -2.54, "right")],
}


def _blocks(path):
    txt = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'\n  \(symbol "([^"]+)"\n', txt):
        name = m.group(1)
        i = m.start() + 1
        depth, j = 0, i
        while j < len(txt):
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[name] = txt[i:j + 1]
    return out


def _easy_pins(block):
    """返回 [(num, name, x, y, 朝外方向)]，坐标取 (at) 处，网格对齐到 1.27。"""
    pins = []
    for pm in re.finditer(
            r'\(pin\s+\w+\s+\w+\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)\)\s*\(length\s+[-\d.]+\)'
            r'[\s\S]*?\(name\s+"([^"]*)"[\s\S]*?\(number\s+"([^"]*)"', block):
        x, y, rot = float(pm.group(1)), float(pm.group(2)), int(pm.group(3))
        d = {0: "left", 90: "down", 180: "right", 270: "up"}[rot]
        pins.append((pm.group(5), pm.group(4), round(x / 1.27) * 1.27, round(y / 1.27) * 1.27, d))
    return pins


def blackbox(pins):
    """把任意引脚集合排成矩形：左侧多的一边放左边，其余依次右、下、上。"""
    groups = {"left": [], "right": [], "up": [], "down": []}
    for num, name, _x, _y, d in pins:
        groups[d].append((num, name))
    left, right = groups["left"], groups["right"]
    if not left and not right:
        # 没有左右引脚：在左右两侧平均分配
        half = (len(pins) + 1) // 2
        left, right = [(p[0], p[1]) for p in pins[:half]], [(p[0], p[1]) for p in pins[half:]]
    out = []
    half_w = 10.16
    for side, items in (("left", left), ("right", right)):
        n = len(items)
        for i, (num, name) in enumerate(items):
            y = (n - 1) * 1.27 - i * 2.54
            x = -half_w if side == "left" else half_w
            out.append((num, name, x, y, "right" if side == "left" else "left"))
    for side, items in (("down", groups["down"]), ("up", groups["up"])):
        n = len(items)
        for i, (num, name) in enumerate(items):
            x = (n - 1) * 1.27 - i * 2.54
            y = -half_w if side == "down" else half_w
            out.append((num, name, x, y, "up" if side == "down" else "down"))
    return out


class Libraries:
    def __init__(self):
        self.easy = {}
        for fn in os.listdir(LIBS):
            if fn.endswith(".kicad_sym"):
                self.easy.update(_blocks(os.path.join(LIBS, fn)))

    def pins(self, lib):
        if lib.startswith("SELF:"):
            return TWO_PIN[lib[5:]]
        key = lib[5:]
        if key not in self.easy:
            raise KeyError(f"library symbol {key} not found")
        return blackbox(_easy_pins(self.easy[key]))
