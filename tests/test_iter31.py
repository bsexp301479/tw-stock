"""
第 31 輪（不連網、不連資料庫）：
D31-01 首頁「籌碼因子觀察」（模型沒勝過基準的降級模式）：因子長條改畫 z 分數本身（±3 截斷、中性藍色），
       說明改成描述性文字，不再寫「對隔日上漲有利」；模型勝過基準時的長條（模型權重 × z、紅綠）不變。
有 node 時逐字取出 app.js 的 oiHTML 執行。

  python3 tests/test_iter31.py      （也相容 pytest）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter28 as t28  # noqa: E402

APP = t28.APP

O = {"date": "2026-11-16", "inv": [{"k": "foreign", "n": "外資", "long": 1, "short": 2, "net": -1, "chg": 0, "eq": -1, "eq_chg": 0}]}
FACTORS = [{"key": "foreign_level", "name": "外資淨未平倉水位", "value": -97225, "z": -1.54, "effect": -0.098},
           {"key": "trust_d1", "name": "投信未平倉 1 日增減", "value": -7521, "z": -4.49, "effect": -0.176},
           {"key": "dealer_d1", "name": "自營商未平倉 1 日增減", "value": 3423, "z": 3.06, "effect": 0.139},
           {"key": "foreign_d1", "name": "外資未平倉 1 日增減", "value": 2263, "z": 0.71, "effect": -0.006}]


def _run(acc, base):
    fc = {"date": "2026-11-16", "p_up": 0.532, "view": "中性", "factors": FACTORS,
          "backtest": {"from": "2024-05-23", "to": "2026-11-13", "n": 602, "acc": acc, "baseline": base, "conf_n": 370, "conf_acc": 0.516},
          "recent": [["2026-11-13", 0.518, 0]]}
    js = t28.HELPERS + "\n" + "\n".join(t28._grab(APP, n) for n in ("OI_COLORS", "pctTxt", "oiHTML")) + \
        f"\nconsole.log(JSON.stringify(oiHTML({json.dumps(O)}, {json.dumps(fc, ensure_ascii=False)})));"
    return t28._node(js)


def _bars(h):
    return re.findall(r'<span class="fc-bar"><span style="(left|right):50%;width:([\d.]+)%;background:([^"]+)"></span></span>', h)


def test_downgraded_bars_use_z():
    h = _run(0.523, 0.54)          # 現況：命中 52.3% 沒勝過基準 54.0%
    if h is None:
        return
    assert "<h2>籌碼因子觀察</h2>" in h
    b = _bars(h)
    assert [(s, round(float(w), 2), c) for s, w, c in b] == [
        ("right", round(1.54 / 3 * 50, 2), "var(--blue)"),     # z −1.54 → 往左 25.7%
        ("right", 50.0, "var(--blue)"),                       # z −4.49 → 截在 3，滿格
        ("left", 50.0, "var(--blue)"),                        # z +3.06 → 截在 3
        ("left", round(0.71 / 3 * 50, 2), "var(--blue)")], b  # 外資 1 日：z +0.71 往右（模型 effect −0.006 是往左，不能再用）
    assert 'title="z 分數 -4.49（相對近 60 日，長條截在 3）"' in h and 'title="z 分數 -1.54（相對近 60 日）"' in h
    assert "長條往右 = 比近 60 日平常偏多（水位較高或增加較多），往左 = 偏少，越長越少見；只描述籌碼，不代表隔天漲跌" in h
    assert "對隔日上漲有利" not in h and "var(--up)" not in h.split("<details")[0] and "var(--dn)" not in h.split("<details")[0]
    assert '<details class="fc-more"><summary>模型回測（實驗性，未勝過基準）</summary>' in h   # 機率與回測仍收在摺疊區


def test_beat_mode_unchanged():
    h = _run(0.60, 0.54)           # 模型勝過基準時：長條仍是模型權重 × z、紅綠
    if h is None:
        return
    assert "<h2>大盤漲跌預測</h2>" in h and "長條往右 = 推升上漲機率，往左 = 壓低" in h
    b = _bars(h)
    assert [(s, round(float(w), 2), c) for s, w, c in b] == [
        ("right", round(0.098 / 0.176 * 50, 2), "var(--dn)"), ("right", 50.0, "var(--dn)"),
        ("left", round(0.139 / 0.176 * 50, 2), "var(--up)"), ("right", round(0.006 / 0.176 * 50, 2), "var(--dn)")], b
    assert 'title="z 分數 -4.49（相對近 60 日）"' in h                                       # 勝過基準時不寫截斷


def test_no_advice_words():
    seg = t28._grab(APP, "oiHTML").replace("非投資建議", "")      # 原有的「僅供研究，非投資建議」免責句
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
