"""一键出包：导入自动布线结果 -> DRC -> Gerber/钻孔/坐标 -> BOM。

用法（KiCad 自带 Python）：
    python release.py            # 若无 SES 则跳过布线，直接用当前板子出包（会报告未连线数）
前置：route/V1_USBC_9V.ses 由 Freerouting 生成（见 route.ps1）。
"""
import csv
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402
import pcbnew  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "V1_USBC_9V"))
RELEASE = os.path.normpath(os.path.join(HERE, "..", "release"))
PCB = os.path.join(OUT, "V1_USBC_9V.kicad_pcb")
SES = os.path.normpath(os.path.join(HERE, "..", "route", "V1_USBC_9V.ses"))
CLI = r"C:/Users/yuanrunze.vdi/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe"


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def import_ses():
    """SES 只导入一次；若板子上已有走线则跳过，避免重复布线。"""
    if not os.path.exists(SES):
        print("no SES, skip")
        return
    board = pcbnew.LoadBoard(PCB)
    if len(list(board.GetTracks())) > 0:
        print("board already routed, skip SES import")
        return
    ok = pcbnew.ImportSpecctraSES(board, SES)
    pcbnew.SaveBoard(PCB, board)
    print("imported SES:", ok)


def drc():
    rpt = os.path.join(OUT, "drc.rpt")
    rc, out = run([CLI, "pcb", "drc", "--refill-zones", "--exit-code-violations", "-o", rpt, PCB])
    text = open(rpt, encoding="utf-8", errors="replace").read() if os.path.exists(rpt) else ""
    errs = len(re.findall(r"^\*\* Found \d+ DRC violation", text, re.M))
    print("DRC rc", rc)
    for line in text.splitlines():
        if line.startswith("** Found") or "Violations" in line or "unconnected" in line.lower():
            print("  ", line)
    return rc


def gerbers():
    gdir = os.path.join(RELEASE, "gerber")
    os.makedirs(gdir, exist_ok=True)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,F.Fab,B.Fab,Edge.Cuts"
    rc, out = run([CLI, "pcb", "export", "gerbers", "-l", layers, "-o", gdir + os.sep, PCB])
    print("gerbers rc", rc, out.strip()[:200])
    rc, out = run([CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
                   "--generate-map", "--map-format", "gerberx2", "-o", gdir + os.sep, PCB])
    print("drill rc", rc, out.strip()[:200])
    pos = os.path.join(RELEASE, "V1_USBC_9V-pos.csv")
    rc, out = run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                   "--exclude-dnp", "-o", pos, PCB])
    print("pos rc", rc, out.strip()[:200])


def bom():
    os.makedirs(RELEASE, exist_ok=True)
    path = os.path.join(RELEASE, "V1_USBC_9V-bom.csv")
    cols = ["Comment", "Designator", "Footprint", "LCSC"]
    groups = {}
    # LM2903 的 A/B/电源是同一颗芯片的多个单元，合并为一行
    for p in D.PARTS:
        val = "LM2903" if p["value"].startswith("LM2903") else p["value"]
        key = (val, p["unit"], p["lcsc"])
        groups.setdefault(key, []).append(p["ref"])
    def sortkey(r):
        m = re.match(r"([A-Za-z]+)(\d+)", r)
        return (m.group(1), int(m.group(2))) if m else (r, 0)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: sortkey(sorted(kv[1], key=sortkey)[0])):
            refs = sorted(refs, key=sortkey)
            # 同一封装被多个单元写入时去重
            uniq = []
            for r in refs:
                if r not in uniq:
                    uniq.append(r)
            w.writerow([val, ",".join(uniq), fp, lcsc])
    print("bom", path, len(groups), "lines")


def main():
    import_ses()
    drc()
    gerbers()
    bom()


if __name__ == "__main__":
    main()
