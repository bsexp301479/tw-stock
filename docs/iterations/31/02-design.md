# 第 31 輪｜UI/UX 設計師：首頁「籌碼因子觀察」長條改畫 z 分數（A31-6）

- 撰寫日期：2026-11-17（週二）
- 依據：
  - `31/01-analyst.md` A31-6 與第五節選項 1。
  - 使用者 11/17「修正因子長條」。
- 做法：
  - 在 scratchpad 副本做原型：`orig` 是專案現況（**含第 30 輪尚未 commit 的改動**），`proj` 是修改後。
  - `site/data` 連到專案資料；沒有 `export`，沒有寫資料庫。
  - 8001 實測 375 淺色、1024 深色。實測時 8001 是從副本 `proj` 啟動，不是專案。
  - 測完已關閉 8001，瀏覽器恢復桌面大小與淺色，localStorage 還原成 `{"tw.todayTab":"credit","tw.stockTab":"k"}`。
  - 專案的 `site/`、`tests/` 都沒有動。附錄是完整 diff，另存為 `31/02-design.diff`。

---

## 〇、結論摘要

| 項目 | 結果 |
|---|---|
| 範圍 | D31-01：只改降級模式（模型沒勝過基準）的因子長條與說明文字 |
| 不改 | 模型、`export.py`、`latest.json` 欄位、勝過基準時的顯示、摺疊區的機率與回測、卡片標題「籌碼因子觀察」 |
| 變更量 | `app.js` ＋5／−3，`index.html` `?v=` 1 行 |
| 舊測試 | **不用改**（沒有測試鎖定這段文字） |
| 新測試 | `tests/test_iter31.py`：3 個測試，82 行 |
| 測試結果 | `proj` 執行 `test_iter01～31` **全部通過**；`node --check` 通過 |
| 反向驗證 | 用 `orig` 跑：`test_downgraded_bars_use_z` 失敗 ✅。另外兩個通過，屬預期：`test_beat_mode_unchanged` 驗證勝過基準時不變；`test_no_advice_words` 驗證用詞 |
| 套用檢查 | 對專案現況 `patch -p1 --dry-run` 乾淨。**要在第 30 輪的改動之後套用**（`index.html` 的 `?v=` 以第 30 輪為基準） |

---

## 一、問題與原則

### 1-1 問題（A31-6）

- 現行降級模式的長條是「模型權重 × z 分數」，顏色紅綠，說明寫「長條往右 = 對隔日上漲有利，往左 = 不利」。
- 模型 602 天回測沒有勝過基準（AUC 0.475），所以長條的方向與顏色都沒有根據。
- 實例（11/16）：

  | 因子 | z 分數 | 模型 effect | 現行長條 |
  |---|---|---|---|
  | 外資未平倉 1 日增減 | **+0.71**（比平常增加） | −0.006 | 往**左**、綠色：讀成「不利」 |
  | 投信未平倉 1 日增減 | −4.49（很少見的大減） | −0.176 | 往左、最長、綠色：讀成「強烈不利」 |

  - 外資那一列，籌碼的實際方向和長條方向相反。

### 1-2 原則

- 長條只描述**籌碼相對近 60 日的位置**，不帶隔天漲跌的意思。
- 用中性色 `--blue`，不用紅漲綠跌。紅綠在本站代表漲跌，用在這裡會被讀成看漲或看跌。
- 文字只描述，不推論；避開禁用詞。
- 模型若日後勝過基準，切回「大盤漲跌預測」，長條照舊用模型權重與紅綠，這時方向才有意義。

---

## 二、規格（D31-01）

| 項目 | 降級模式（現況） | 降級模式（改後） | 勝過基準時 |
|---|---|---|---|
| 長條長度 | \|effect\| ÷ 最大 \|effect\| | **\|z\| ÷ 3**，超過 3 截斷成滿格 | 不變 |
| 長條方向 | effect 正負 | **z 正負** | 不變 |
| 顏色 | 紅／綠 | **`--blue`（兩個方向同色）** | 不變 |
| `title` | `z 分數 X（相對近 60 日）` | 同左；\|z\| > 3 時加「，長條截在 3」 | 不變 |
| 說明 | 長條往右 = 對隔日上漲有利，往左 = 不利 | **長條往右 = 比近 60 日平常偏多（水位較高或增加較多），往左 = 偏少，越長越少見；只描述籌碼，不代表隔天漲跌** | 不變（推升上漲機率／壓低） |

為什麼截在 3：
- |z| > 3 在常態下約千分之三，已經是「很少見」。
- 不截斷的話，一個極端值會把其他長條壓得很短。11/16 投信 −4.49 就是這種情況。

11/16 改後實測（375）：

| 因子 | 數值 | z | 長條 |
|---|---|---|---|
| 外資淨未平倉水位 | −97,225 口 | −1.54 | 往左 25.7% |
| 外資未平倉 1 日增減 | +2,263 口 | +0.71 | 往右 11.8% |
| 外資未平倉 5 日增減 | +3,101 口 | +0.70 | 往右 11.7% |
| 投信未平倉 1 日增減 | −7,521 口 | −4.49 | 往左滿格（截斷） |
| 自營商未平倉 1 日增減 | +3,423 口 | +3.06 | 往右滿格（截斷） |

- 375 淺色：說明文字 2 行（36px），`scrollWidth` 375。
- 1024 深色：長條 `rgb(72, 139, 217)`，`scrollWidth` 1024。
- 摺疊區仍是「中性 下一交易日上漲機率 53.2%」與回測，沒有長條。
- 錯誤攔截器 0 個。

---

## 三、不能破壞的事項

- 沒有測試鎖定這段文字（`grep` 舊測試沒有「長條往」「fc-bar」「oiHTML」）。
- `test_iter23` 檢查 `?v=`，原型已更新 `app.js?v=0bde7e1c`。
  - 若 PG 套用前第 30 輪已 commit，值不變。
  - 若 `app.js` 有其他改動，要重算 sha1 前 8 碼。
- 第 29 輪階段二的 B diff 不動 `app.js` 的 `oiHTML`，不衝突；只有 `index.html` 的 `?v=` 要重算。

---

## 四、需使用者決定

無。說明文字照分析師第五節選項 1 的方向；若想改字，PG 前告知即可。

---

## 五、給 PG

```bash
cd tw-stock && patch -p1 < docs/iterations/31/02-design.diff
```

- 套完跑 `for f in tests/test_iter*.py; do python3 $f; done`，以及 `node --check site/app.js`。
- 不需要 `export`，`site/data` 不變。

## 六、給 QA

| 檢查 | 方法 | 期望 |
|---|---|---|
| 長條方向 = z 正負 | 今日 → 期貨分頁 →「籌碼因子觀察」，逐列比對 `title` 的 z 與長條方向 | 一致；外資 1 日 z +0.71 往右 |
| 截斷 | \|z\| > 3 的列 | 滿格，`title` 有「長條截在 3」 |
| 顏色 | 長條 `backgroundColor` | 淺 `--blue` `#286dbf`、深 `#488bd9`；降級模式卡片沒有紅綠長條 |
| 說明 | 文字 | 和第二節相同，沒有「對隔日上漲有利」 |
| 摺疊區 | 打開「模型回測」 | 機率、回測、最近 10 次照舊 |
| 版面 | 375／1024 × 淺／深 | 不橫捲 |
| 反證 | 副本把 `bar` 改回 effect | `test_iter31` 失敗 |

---

## 附錄：完整 diff（`orig` → `proj`；`site/` 與 `tests/`，不含 `site/data`）

```diff
diff -ruN -x data -x __pycache__ orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-17 01:47:07
+++ proj/site/app.js	2026-11-17 01:47:17
@@ -646,10 +646,12 @@
     const head = `<div class="fc-head"><span class="fc-view ${vcls}">${FC.view}</span>
         <span>下一交易日上漲機率 <b class="num ${vcls}">${pctTxt(FC.p_up)}</b></span>
         <span class="muted small">依 ${md(FC.date)} 收盤後未平倉</span></div>`;
-    const factors = `<div class="fc-factors">${FC.factors.map(f => `<div class="fc-f" title="z 分數 ${f.z}（相對近 60 日）">
+    // 第 31 輪 D31-01：模型沒勝過基準時，長條改畫 z 分數本身（±3 截斷、中性藍色），只描述籌碼相對近 60 日的位置
+    const bar = f => beat ? [f.effect / maxE, `var(--${f.effect >= 0 ? 'up' : 'dn'})`] : [Math.max(-3, Math.min(3, f.z)) / 3, 'var(--blue)'];
+    const factors = `<div class="fc-factors">${FC.factors.map(f => { const [v, c] = bar(f); return `<div class="fc-f" title="z 分數 ${f.z}（相對近 60 日${!beat && Math.abs(f.z) > 3 ? '，長條截在 3' : ''}）">
           <span class="nm">${f.name}</span><span class="num muted">${sgn(f.value, 0)} 口</span>
-          <span class="fc-bar"><span style="${f.effect >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(f.effect) / maxE * 50}%;background:var(--${f.effect >= 0 ? 'up' : 'dn'})"></span></span></div>`).join('')}
-        <div class="muted small">${beat ? '長條往右 = 推升上漲機率，往左 = 壓低' : '長條往右 = 對隔日上漲有利，往左 = 不利'}</div></div>`;
+          <span class="fc-bar"><span style="${v >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(v) * 50}%;background:${c}"></span></span></div>`; }).join('')}
+        <div class="muted small">${beat ? '長條往右 = 推升上漲機率，往左 = 壓低' : '長條往右 = 比近 60 日平常偏多（水位較高或增加較多），往左 = 偏少，越長越少見；只描述籌碼，不代表隔天漲跌'}</div></div>`;
     const bt = `<div class="fc-bt ${beat ? '' : 'warn'}">回測 ${B.from.slice(0, 7).replace('-', '/')}～${B.to.slice(0, 7).replace('-', '/')} 共 ${B.n} 天：
         命中率 <b>${pctTxt(B.acc)}</b>，「永遠猜多數方向」基準 <b>${pctTxt(B.baseline)}</b>
         ${B.conf_acc != null ? `；機率偏離 5% 以上的 ${B.conf_n} 天命中 <b>${pctTxt(B.conf_acc)}</b>` : ''}。
diff -ruN -x data -x __pycache__ orig/site/index.html proj/site/index.html
--- orig/site/index.html	2026-11-17 01:47:07
+++ proj/site/index.html	2026-11-17 01:47:49
@@ -10,7 +10,7 @@
 <link rel="stylesheet" href="app.css?v=a69df04b">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js?v=895b2037" defer></script>
+<script src="app.js?v=0bde7e1c" defer></script>
 <script src="stock.js?v=41db19b1" defer></script>
 </head>
 <body>
diff -ruN -x __pycache__ orig/tests/test_iter31.py proj/tests/test_iter31.py
--- orig/tests/test_iter31.py	1970-01-01 08:00:00
+++ proj/tests/test_iter31.py	2026-11-17 01:48:08
@@ -0,0 +1,82 @@
+"""
+第 31 輪（不連網、不連資料庫）：
+D31-01 首頁「籌碼因子觀察」（模型沒勝過基準的降級模式）：因子長條改畫 z 分數本身（±3 截斷、中性藍色），
+       說明改成描述性文字，不再寫「對隔日上漲有利」；模型勝過基準時的長條（模型權重 × z、紅綠）不變。
+有 node 時逐字取出 app.js 的 oiHTML 執行。
+
+  python3 tests/test_iter31.py      （也相容 pytest）
+"""
+import json
+import re
+import sys
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import test_iter28 as t28  # noqa: E402
+
+APP = t28.APP
+
+O = {"date": "2026-11-16", "inv": [{"k": "foreign", "n": "外資", "long": 1, "short": 2, "net": -1, "chg": 0, "eq": -1, "eq_chg": 0}]}
+FACTORS = [{"key": "foreign_level", "name": "外資淨未平倉水位", "value": -97225, "z": -1.54, "effect": -0.098},
+           {"key": "trust_d1", "name": "投信未平倉 1 日增減", "value": -7521, "z": -4.49, "effect": -0.176},
+           {"key": "dealer_d1", "name": "自營商未平倉 1 日增減", "value": 3423, "z": 3.06, "effect": 0.139},
+           {"key": "foreign_d1", "name": "外資未平倉 1 日增減", "value": 2263, "z": 0.71, "effect": -0.006}]
+
+
+def _run(acc, base):
+    fc = {"date": "2026-11-16", "p_up": 0.532, "view": "中性", "factors": FACTORS,
+          "backtest": {"from": "2024-05-23", "to": "2026-11-13", "n": 602, "acc": acc, "baseline": base, "conf_n": 370, "conf_acc": 0.516},
+          "recent": [["2026-11-13", 0.518, 0]]}
+    js = t28.HELPERS + "\n" + "\n".join(t28._grab(APP, n) for n in ("OI_COLORS", "pctTxt", "oiHTML")) + \
+        f"\nconsole.log(JSON.stringify(oiHTML({json.dumps(O)}, {json.dumps(fc, ensure_ascii=False)})));"
+    return t28._node(js)
+
+
+def _bars(h):
+    return re.findall(r'<span class="fc-bar"><span style="(left|right):50%;width:([\d.]+)%;background:([^"]+)"></span></span>', h)
+
+
+def test_downgraded_bars_use_z():
+    h = _run(0.523, 0.54)          # 現況：命中 52.3% 沒勝過基準 54.0%
+    if h is None:
+        return
+    assert "<h2>籌碼因子觀察</h2>" in h
+    b = _bars(h)
+    assert [(s, round(float(w), 2), c) for s, w, c in b] == [
+        ("right", round(1.54 / 3 * 50, 2), "var(--blue)"),     # z −1.54 → 往左 25.7%
+        ("right", 50.0, "var(--blue)"),                       # z −4.49 → 截在 3，滿格
+        ("left", 50.0, "var(--blue)"),                        # z +3.06 → 截在 3
+        ("left", round(0.71 / 3 * 50, 2), "var(--blue)")], b  # 外資 1 日：z +0.71 往右（模型 effect −0.006 是往左，不能再用）
+    assert 'title="z 分數 -4.49（相對近 60 日，長條截在 3）"' in h and 'title="z 分數 -1.54（相對近 60 日）"' in h
+    assert "長條往右 = 比近 60 日平常偏多（水位較高或增加較多），往左 = 偏少，越長越少見；只描述籌碼，不代表隔天漲跌" in h
+    assert "對隔日上漲有利" not in h and "var(--up)" not in h.split("<details")[0] and "var(--dn)" not in h.split("<details")[0]
+    assert '<details class="fc-more"><summary>模型回測（實驗性，未勝過基準）</summary>' in h   # 機率與回測仍收在摺疊區
+
+
+def test_beat_mode_unchanged():
+    h = _run(0.60, 0.54)           # 模型勝過基準時：長條仍是模型權重 × z、紅綠
+    if h is None:
+        return
+    assert "<h2>大盤漲跌預測</h2>" in h and "長條往右 = 推升上漲機率，往左 = 壓低" in h
+    b = _bars(h)
+    assert [(s, round(float(w), 2), c) for s, w, c in b] == [
+        ("right", round(0.098 / 0.176 * 50, 2), "var(--dn)"), ("right", 50.0, "var(--dn)"),
+        ("left", round(0.139 / 0.176 * 50, 2), "var(--up)"), ("right", round(0.006 / 0.176 * 50, 2), "var(--dn)")], b
+    assert 'title="z 分數 -4.49（相對近 60 日）"' in h                                       # 勝過基準時不寫截斷
+
+
+def test_no_advice_words():
+    seg = t28._grab(APP, "oiHTML").replace("非投資建議", "")      # 原有的「僅供研究，非投資建議」免責句
+    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
+        assert w not in seg, w
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_"):
+            print("==", name)
+            fn()
+            print("✅", name)
+    print("全部通過")
```
