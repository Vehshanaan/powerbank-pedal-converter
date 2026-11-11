"""端到端构建（必须用 KiCad 自带 Python 运行）：python build_all.py

  1. gen_pcb.py              由 design.py 生成未布线 PCB（含板框、网络）
  2. ExportSpecctraDSN       导出 DSN
  3. Freerouting 2.1.0 jar   -Djava.awt.headless=true 严格无界面自动布线 -> SES
  4. ImportSpecctraSES       回注走线
  5. 后处理                  细线加宽、隐藏位号、功能丝印、GND 铺铜、NPTH
  6. DRC                     必须 0 违规 / 0 未连接
  7. 出包                    Gerber / 钻孔 / 坐标 / BOM
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PCB = os.path.join(ROOT, "V1_USBC_9V", "V1_USBC_9V.kicad_pcb")
DSN = os.path.join(ROOT, "route", "V1_USBC_9V.dsn")
SES = os.path.join(ROOT, "route", "V1_USBC_9V.ses")
LOG = os.path.join(ROOT, "route", "fr.log")
JAVA = r"C:/Program Files/Eclipse Adoptium/jre-25.0.5.8-hotspot/bin/java.exe"
FR = r"D:/Tools/Other/freerouting/fr210.jar"   # 2.1.0：唯一在 true headless 下稳定且不弹窗的版本
KCLI = r"C:/Users/yuanrunze.vdi/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe"

import pcbnew  # noqa: E402

MM = pcbnew.FromMM


def step(msg):
    print("\n=== " + msg, flush=True)


def post_process():
    b = pcbnew.LoadBoard(PCB)
    fixed = 0
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_TRACK) and not isinstance(t, pcbnew.PCB_VIA) and t.GetWidth() < MM(0.15):
            t.SetWidth(MM(0.25))
            fixed += 1
    for fp in b.GetFootprints():
        if fp.Reference().IsVisible() or fp.Value().IsVisible():
            fp.Reference().SetVisible(False)
            fp.Value().SetVisible(False)
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetNetCode() == 0 and pad.GetNumber() == "":
                pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
                ls = pad.GetLayerSet()
                ls.removeLayer(pcbnew.F_Cu)
                ls.removeLayer(pcbnew.B_Cu)

    def text(txt, x, y, size=1.2):
        if any(isinstance(d, pcbnew.PCB_TEXT) and d.GetText() == txt for d in b.GetDrawings()):
            return
        t = pcbnew.PCB_TEXT(b)
        t.SetText(txt)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(0.2))
        b.Add(t)

    text("USB-C IN 5V", 24, 17.0, 1.0)
    text("9V OUT 200mA", 97, 19.0, 1.0)
    text("CENTER NEG.", 99, 20.6, 0.9)
    text("V1 2026-11", 55, 72.5)
    text("VBST", 75, 71.0, 1.0)
    text("OUT", 102, 73.0, 1.0)
    text("GND", 95, 73.0, 1.0)

    if len(list(b.Zones())) == 0:
        gnd = b.FindNet("GND")
        xs, ys = [], []
        for d in b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts:
                for p in (d.GetStart(), d.GetEnd()):
                    xs.append(p.x)
                    ys.append(p.y)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        m = MM(0.3)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(b)
            z.SetIsRuleArea(False)
            z.SetLayer(layer)
            z.SetNet(gnd)
            z.SetLocalClearance(MM(0.2))
            z.SetMinThickness(MM(0.2))
            z.SetIsFilled(False)
            outline = z.Outline()
            outline.NewOutline()
            for x, y in ((x0 + m, y0 + m), (x1 - m, y0 + m), (x1 - m, y1 - m), (x0 + m, y1 - m)):
                outline.Append(int(x), int(y))
            b.Add(z)
    unroute_hanging_and_fill(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    print("post-process: widened", fixed, "tracks; zones", len(list(b.Zones())))


def unroute_hanging_and_fill(board):
    """清理 Freerouting 留下的悬空 GND 短头，然后把真正未连通的焊盘用直线补齐（0.25mm，B 层）。"""
    ci = board.GetConnectivity()
    ci.RecalculateRatsnest()
    removed = 0
    for t in list(board.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        if not ci.GetConnectedTracks(t) and t.GetNetname() == "GND":
            board.Remove(t)
            removed += 1
    ci.RecalculateRatsnest()
    stitched = 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if not pad.GetNetCode():
                continue
            if ci.GetConnectedTracks(pad):
                continue
            best = None
            for fp2 in board.GetFootprints():
                for pad2 in fp2.Pads():
                    if pad2.GetNetCode() == pad.GetNetCode() and pad2.GetPadToDieLength() == pad.GetPadToDieLength() and pad2.GetPosition() != pad.GetPosition() and ci.GetConnectedTracks(pad2):
                        d = (pad2.GetPosition() - pad.GetPosition()).EuclideanNorm()
                        if best is None or d < best[0]:
                            best = (d, pad2)
            if best is None:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetLayer(pcbnew.B_Cu)
            t.SetStart(pad.GetPosition())
            t.SetEnd(best[1].GetPosition())
            t.SetWidth(pcbnew.FromMM(0.25))
            t.SetNetCode(pad.GetNetCode())
            board.Add(t)
            stitched += 1
    print("cleanup: removed", removed, "hanging tracks; stitched", stitched)


def incomplete_count():
    n = 0
    for line in open(LOG, encoding="utf-8", errors="replace"):
        if '"incomplete_count"' in line:
            n = int(line.split(":")[1].strip().rstrip(","))
    return n


def autoroute():
    """每轮从当前最佳板重新导出 DSN 并布线，直到 0 未布通；最多 6 轮。"""
    for attempt in range(1, 7):
        b = pcbnew.LoadBoard(PCB)
        pcbnew.ExportSpecctraDSN(b, DSN)
        if os.path.exists(SES):
            os.remove(SES)
        with open(LOG, "a" if attempt > 1 else "w", encoding="utf-8") as f:
            f.write("##### attempt %d\n" % attempt)
            subprocess.run([JAVA, "-Djava.awt.headless=true", "-jar", FR,
                            "-de", os.path.basename(DSN), "-do", os.path.basename(SES),
                            "-mp", "24", "-mt", "8"],
                           stdout=f, stderr=subprocess.STDOUT, timeout=3600,
                           cwd=os.path.dirname(SES))
        n = incomplete_count()
        print("  attempt %d: incomplete=%d" % (attempt, n))
        if not os.path.exists(SES):
            continue
        b = pcbnew.LoadBoard(PCB)
        pcbnew.ImportSpecctraSES(b, SES)
        pcbnew.SaveBoard(PCB, b)
        if n == 0:
            return True
    return n <= 1      # 允许偶发 1 条未布通，由 post_process 手工补齐并再次 DRC 校验


def main():
    # 先备份当前成品，任何阶段失败都能恢复到最近一次全绿状态
    if os.path.exists(PCB):
        snap = os.path.join(ROOT, "V1_USBC_9V", "V1_USBC_9V.routed_backup.kicad_pcb")
        import shutil
        shutil.copyfile(PCB, snap)
        print("backup ->", snap)
    step("1. generate unrouted PCB")
    subprocess.run([sys.executable, os.path.join(HERE, "gen_pcb.py")], check=True)
    step("2+3+4. autoroute (headless)")
    if not autoroute():
        restore = os.path.join(ROOT, "V1_USBC_9V", "V1_USBC_9V.routed_backup.kicad_pcb")
        if os.path.exists(restore):
            import shutil
            shutil.copyfile(restore, PCB)
            raise SystemExit("autorouting failed; restored previous routed board from backup")
        raise SystemExit("autorouting left unrouted connections; see route/fr.log")
    step("5. post-process")
    post_process()
    step("6. DRC")
    rpt = os.path.join(ROOT, "V1_USBC_9V", "drc.rpt")
    r = subprocess.run([KCLI, "pcb", "drc", "--exit-code-violations", "-o", rpt, PCB],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip())
    if r.returncode != 0:
        raise SystemExit("DRC failed; see drc.rpt")
    step("7. release files")
    subprocess.run([sys.executable, os.path.join(HERE, "release.py")], check=True)


if __name__ == "__main__":
    main()
