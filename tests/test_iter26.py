"""第 26 輪：淺色／深色切換（不連網、不連資料庫）。
沒選過時跟系統；按頂欄按鈕在淺色、深色之間切換並存在 tw.theme；index.html 在載入 CSS 前先套用，避免閃一下；
切換後重畫目前頁面（圖表顏色是畫圖當下取的）。有 node 時，逐字取出 app.js 的 isDark、setupTheme 執行。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
HTML = (ROOT / "site" / "index.html").read_text(encoding="utf-8")


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b.*$", src, re.M)
    assert m, name
    return m.group(0)


def test_head_applies_saved_theme_before_css():
    head = HTML[:HTML.index("</head>")]
    pre = "<script>try{var t=localStorage.getItem('tw.theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>"
    assert pre in head and head.index(pre) < head.index('<link rel="stylesheet" href="app.css')
    assert '<button class="theme-btn" id="themeBtn" type="button"></button>' in HTML


def test_css_theme_blocks():
    assert ':root:not([data-theme="light"]){' in CSS and ':root[data-theme="dark"]{' in CSS   # 強制淺色時不吃系統深色、強制深色時不看系統
    assert ".theme-btn{" in CSS and ".theme-btn svg{" in CSS


def test_toggle_flow():
    js = "\n".join(_grab(APP, n) for n in ("isDark", "themeBtn", "redrawKeepScroll", "setupTheme")) + r"""
let sysDark = true, mqCb = null, routed = 0, scrolled = [];
const store = {}, btn = { innerHTML: '', title: '', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(t, f) { this.click = f; } };
const document = { documentElement: { dataset: {} } };
const window = { scrollY: 420, scrollTo: (x, y) => scrolled.push(y) };
const matchMedia = () => ({ get matches() { return sysDark; }, addEventListener: (t, f) => { mqCb = f; } });
const $ = () => btn, App = { latest: {} };
const localStore = (k, f, v) => { store[k] = v; };
const route = async () => { routed++; };
(async () => {
  setupTheme();
  const s0 = { dark: isDark(), title: btn.title, theme: document.documentElement.dataset.theme ?? null };
  btn.click(); await new Promise(r => setTimeout(r));
  const s1 = { theme: document.documentElement.dataset.theme, store: store.theme, title: btn.title, aria: btn.attrs['aria-label'], routed, scrolled: [...scrolled] };
  btn.click(); await new Promise(r => setTimeout(r));
  const s2 = { theme: document.documentElement.dataset.theme, store: store.theme, routed };
  sysDark = false; mqCb(); await new Promise(r => setTimeout(r));
  const s3 = { routed, dark: isDark() };                                   // 已選過：系統切換不影響
  delete document.documentElement.dataset.theme; mqCb(); await new Promise(r => setTimeout(r));
  const s4 = { routed, dark: isDark(), title: btn.title };                 // 沒選過：跟著系統重畫
  console.log(JSON.stringify({ s0, s1, s2, s3, s4 }));
})();"""
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return
    o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    assert o["s0"] == {"dark": True, "title": "切換為淺色", "theme": None}, o
    assert o["s1"] == {"theme": "light", "store": "light", "title": "切換為深色", "aria": "切換為深色", "routed": 1, "scrolled": [420]}, o
    assert o["s2"] == {"theme": "dark", "store": "dark", "routed": 2}, o
    assert o["s3"] == {"routed": 2, "dark": True}, o
    assert o["s4"] == {"routed": 3, "dark": False, "title": "切換為深色"}, o


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_dark_green_balanced():
    """深色模式漲跌同亮度：--dn 與 --up 亮度比在 0.9～1.1，且兩段深色區塊一致、對卡片底 ≥ 4.5。"""
    blocks = re.findall(r'(?::root:not\(\[data-theme="light"\]\)|:root\[data-theme="dark"\])\{(.*?)\}', CSS, re.S)
    assert len(blocks) == 2
    for b in blocks:
        up, dn, card = (re.search(rf"--{k}:(#[0-9a-f]{{6}})", b).group(1) for k in ("up", "dn", "card"))
        assert 0.9 <= _lum(dn) / _lum(up) <= 1.1, (up, dn)
        assert (_lum(dn) + .05) / (_lum(card) + .05) >= 4.5
        assert "rgba(63,191,127" not in b                                      # 淡底色跟著新綠色
    assert "--dn:#3fbf7f" not in CSS


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + CSS.splitlines() if "第 26 輪" in l or "theme" in l.lower())
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
