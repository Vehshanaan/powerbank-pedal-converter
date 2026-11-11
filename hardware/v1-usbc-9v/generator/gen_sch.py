"""从 design.py 生成 KiCad 10 原理图，并调用 check_netlist.py 自检连通性。

所有器件都用本文件生成的统一符号（两引脚或矩形黑盒），引脚端点处接一段导线 + 标签。
GND 用 global label "GND"（不叠加电源符号，避免同一坐标多重对象）。
"""
import json
import os
import re
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402
import klib  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "V1_USBC_9V"))
CLI = r"C:/Users/yuanrunze.vdi/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe"
PROJ = "V1_USBC_9V"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "v1-usbc-9v/root"))
LIBS = klib.Libraries()
STUB = 6.35


def uid(s):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "v1-usbc-9v/" + s))


def q(v):
    return f"{round(v, 3):g}"


def sym_name(lib):
    return lib.replace(":", "")


def graphics(name):
    if name == "SELFR":
        return ["(rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none)))"]
    if name == "SELFC":
        return ["(polyline (pts (xy -1.778 -0.508) (xy 1.778 -0.508)) (stroke (width 0.4) (type default)) (fill (type none)))",
                "(polyline (pts (xy -1.778 0.508) (xy 1.778 0.508)) (stroke (width 0.4) (type default)) (fill (type none)))"]
    if name == "SELFL":
        return ["(rectangle (start -0.762 -1.524) (end 0.762 1.524) (stroke (width 0.254) (type default)) (fill (type none)))"]
    if name == "SELFF":
        return ["(rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none)))",
                "(polyline (pts (xy 0 -2.54) (xy 0 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))"]
    if name in ("SELFD", "SELFTVS", "SELFLED"):
        g = ["(polyline (pts (xy -1.524 1.27) (xy 1.524 1.27) (xy 0 -1.27) (xy -1.524 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))",
             "(polyline (pts (xy -1.524 -1.27) (xy 1.524 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))"]
        if name == "SELFTVS":
            g.append("(polyline (pts (xy -2.032 1.905) (xy -2.032 0.635) (xy -0.762 0.635)) (stroke (width 0.254) (type default)) (fill (type none)))")
        if name == "SELFLED":
            g.append("(polyline (pts (xy 1.524 1.905) (xy 2.794 3.175)) (stroke (width 0.254) (type default)) (fill (type none)))")
        return g
    return []


def box_of(lib, pins):
    if lib == "SELF:CMP":
        return (-7.62, -5.08, 7.62, 5.08)
    if lib == "SELF:VCC":
        return (-5.08, -5.08, 5.08, 5.08)
    if lib == "SELF:REF":
        return (-1.27, -5.08, 5.08, 5.08)
    xs = [p[2] for p in pins]
    ys = [p[3] for p in pins]
    return (min(xs) - 2.54, min(ys) - 5.08, max(xs) + 2.54, max(ys) + 5.08)


def lib_symbol(lib):
    name = sym_name(lib)
    pins = LIBS.pins(lib)
    box = None if len(pins) == 2 and lib.startswith("SELF:") and name in (
        "SELFR", "SELFC", "SELFL", "SELFF", "SELFD", "SELFTVS", "SELFLED") else box_of(lib, pins)
    gfx = graphics(name)
    if box:
        gfx = [f"(rectangle (start {q(box[0])} {q(box[3])}) (end {q(box[2])} {q(box[1])}) "
               f"(stroke (width 0.254) (type default)) (fill (type none)))"]
    pin_lines = []
    for num, pname, x, y, dirn in pins:
        rot = {"left": 0, "up": 90, "right": 180, "down": 270}[dirn]
        pin_lines.append(f'(pin passive line (at {q(x)} {q(y)} {rot}) (length 0) '
                         f'(name "{pname}" (effects (font (size 1.016 1.016)))) '
                         f'(number "{num}" (effects (font (size 1.016 1.016)))))')
    ymax = box[3] if box else 5.08
    ymin = box[1] if box else -5.08
    return "\n".join([
        f'    (symbol "{name}" (exclude_from_sim no) (in_bom yes) (on_board yes)',
        f'      (property "Reference" "U" (at 0 {q(ymax + 3.81)} 0) (effects (font (size 1.27 1.27))))',
        f'      (property "Value" "{name}" (at 0 {q(ymin - 3.81)} 0) (effects (font (size 1.27 1.27))))',
        '      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        '      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        f'      (property "Description" "{lib}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        f'      (symbol "{name}_0_1"', *("        " + g for g in gfx), "      )",
        f'      (symbol "{name}_1_1"', *("        " + p for p in pin_lines), "      )",
        "    )",
    ])


def resolve(pins, want):
    out = {}
    for key, net in want.items():
        hit = [p for p in pins if p[0] == key]
        if not hit:
            hit = [p for p in pins if p[1] == key or p[1].replace("~", "") == key]
        if not hit:
            raise SystemExit(f"pin {key} not found among {[p[0] + ':' + p[1] for p in pins]}")
        out[hit[0][0]] = net
    return out


def main():
    libs = sorted({p["lib"] for p in D.PARTS})
    lib_text = "\n".join(lib_symbol(l) for l in libs)
    two = [p for p in D.PARTS if len(LIBS.pins(p["lib"])) == 2]
    multi = [p for p in D.PARTS if len(LIBS.pins(p["lib"])) > 2]
    pos = {}
    for i, p in enumerate(two):
        pos[id(p)] = (30.48 + (i % 8) * 40.64, 38.1 + (i // 8) * 33.02)
    y0 = 38.1 + ((len(two) + 7) // 8) * 33.02 + 15.24
    for i, p in enumerate(multi):
        pos[id(p)] = (40.64 + (i % 4) * 90.17, y0 + (i // 4) * 76.2)

    items, values = [], {}
    for p in D.PARTS:
        lib, name = p["lib"], sym_name(p["lib"])
        pins = LIBS.pins(lib)
        x, y = pos[id(p)]
        s = [f'  (symbol (lib_id "{name}") (at {q(x)} {q(y)} 0) (unit 1)',
             "    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)",
             f"    (uuid {uid('sym/' + p['ref'] + '/' + name)})",
             f'    (property "Reference" "{p["ref"]}" (at {q(x)} {q(y + 17.78)} 0) (effects (font (size 1.27 1.27))))',
             f'    (property "Value" "{p["value"]}" (at {q(x)} {q(y + 15.24)} 0) (effects (font (size 1.27 1.27))))',
             f'    (property "Footprint" "{p["fp"]}" (at {q(x)} {q(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
             '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
             f'    (property "LCSC" "{p["lcsc"]}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        for pn in pins:
            s.append(f'    (pin "{pn[0]}" (uuid {uid("pin/" + p["ref"] + "/" + name + "/" + pn[0])}))')
        s.append(f'    (instances (project "{PROJ}" (path "/{ROOT}" (reference "{p["ref"]}") (unit 1))))')
        s.append("  )")
        items.append("\n".join(s))
        values[p["ref"]] = p["value"]

        pmap = resolve(pins, p["pins"])
        for num, pname, px, py, dirn in pins:
            ex, ey = x + px, y - py
            dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[dirn]
            sx, sy = ex + dx * STUB, ey + dy * STUB
            items.append(f'  (wire (pts (xy {q(ex)} {q(ey)}) (xy {q(sx)} {q(sy)})) (stroke (width 0) (type default)) '
                         f'(uuid {uid(f"w/{p["ref"]}/{num}")}))')
            net = pmap.get(num)
            if not net:
                continue
            rot = {"right": 0, "left": 180, "up": 90, "down": 270}[dirn]
            power = net in D.POWER_NETS
            kind = "global_label" if power else "label"
            shape = " (shape passive)" if power else ""
            just = "(justify left)" if rot in (0, 90) else "(justify right)"
            items.append(f'  ({kind} "{net}"{shape} (at {q(sx)} {q(sy)} {rot}) '
                         f'(effects (font (size 1.016 1.016)) {just}) (uuid {uid(f"l/{p["ref"]}/{num}")}))')

    doc = ['(kicad_sch (version 20231120) (generator "gen_sch")',
           f'  (uuid {ROOT})', '  (paper "A2")',
           '  (title_block (title "V1 USB-C to 9V pedal supply") (rev "A"))',
           '  (lib_symbols', lib_text, '  )', *items,
           '  (sheet_instances (path "/" (page "1")))', ')']
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, PROJ + ".kicad_sch")
    open(path, "w", encoding="utf-8").write("\n".join(doc) + "\n")
    print("wrote", path, "libs", len(libs), "parts", len(D.PARTS), "items", len(items))
    net_path = os.path.join(OUT, PROJ + "_netlist.net")
    r = subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net_path, path],
                       capture_output=True, text=True, encoding="gbk", errors="replace")
    msg = ((r.stdout or "") + (r.stderr or "")).strip()
    if "加载原理图失败" in msg:
        raise SystemExit("schematic failed to load: " + msg)
    json.dump(values, open(os.path.join(OUT, "values.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(subprocess.run([sys.executable, os.path.join(HERE, "check_netlist.py")]).returncode)


if __name__ == "__main__":
    main()
