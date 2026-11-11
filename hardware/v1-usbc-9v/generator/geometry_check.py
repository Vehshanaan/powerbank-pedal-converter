"""几何自检：检查走线是否侵入异网焊盘 / 异网走线。
用法：KiCad 自带 python geometry_check.py [pcb]
输出：违规条数与前若干条明细（坐标、两个对象）。
"""
import sys

import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else r"../V1_USBC_9V/V1_USBC_9V.kicad_pcb"


def box_of(item):
    bb = item.GetBoundingBox()
    return (bb.GetPosition().x, bb.GetPosition().y,
            bb.GetPosition().x + bb.GetSize().x, bb.GetPosition().y + bb.GetSize().y)


def overlap(a, b, tol=0):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def main():
    b = pcbnew.LoadBoard(PCB)
    pads = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode():
                pads.append((fp.GetReference(), pad.GetNumber(), pad.GetNetCode(), pad.GetNetname(), box_of(pad)))
    tracks = []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        tracks.append((t.GetNetCode(), t.GetNetname(), box_of(t), t.GetStart(), t.GetEnd()))
    bad = []
    for code, name, tb, s, e in tracks:
        for ref, num, pcode, pname, pb in pads:
            if pcode == code:
                continue
            if overlap(tb, pb):
                bad.append((name, f"{ref}.{num}({pname})", s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6))
    print("track-in-foreign-pad:", len(bad))
    for x in bad[:25]:
        print("   ", x)


if __name__ == "__main__":
    main()
