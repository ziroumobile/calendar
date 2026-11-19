"""課表匯入 - 解析各校課表 HTML（目前僅支援北科大「網路加退選系統 → 顯示課表」頁面）

新增其他學校時：寫一個 parse_xxx(text) -> (sessions, meta)，再登記到 PARSERS 即可。
sessions 每筆格式：
    {"code", "name", "teacher", "room", "weekday"(0=週一…6=週日), "start"("HH:MM"), "end"("HH:MM")}
"""
import re
from datetime import date, timedelta
from html.parser import HTMLParser

PERIOD_ORDER = list("1234N56789ABCD")  # 北科大節次順序
DEFAULT_TIMES = {
    "1": ("08:10", "09:00"), "2": ("09:10", "10:00"), "3": ("10:10", "11:00"),
    "4": ("11:10", "12:00"), "N": ("12:10", "13:00"), "5": ("13:10", "14:00"),
    "6": ("14:10", "15:00"), "7": ("15:10", "16:00"), "8": ("16:10", "17:00"),
    "9": ("17:10", "18:00"), "A": ("18:30", "19:20"), "B": ("19:20", "20:10"),
    "C": ("20:20", "21:10"), "D": ("21:10", "22:00"),
}


class _CellCollector(HTMLParser):
    """依序收集所有 <td>；以 <br> 切段。頁面的 <tr> 結構不規則，所以不依賴 <tr>。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self._cur = None

    def _close(self):
        self.cells.append(self._cur)
        self._cur = None

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            if self._cur is not None:
                self._close()
            self._cur = {"style": dict(attrs).get("style", "") or "", "segs": [""]}
        elif tag == "br" and self._cur is not None:
            self._cur["segs"].append("")

    def handle_endtag(self, tag):
        if tag == "td" and self._cur is not None:
            self._close()

    def handle_data(self, data):
        if self._cur is not None:
            self._cur["segs"][-1] += data


def _is_label(cell):
    """節次標籤格（左側 1~9、N、A~D）的背景色為 #c1b300 / #918600。"""
    s = cell["style"].replace(" ", "").lower()
    txt = "".join(cell["segs"]).strip()
    return ("background:#c1b300" in s or "background:#918600" in s) and txt in PERIOD_ORDER


def _parse_cell(cell):
    segs = [s.strip() for s in cell["segs"] if s.strip()]
    if len(segs) < 2 or not re.fullmatch(r"\d{4,8}", segs[0]):
        return None
    info = {"code": segs[0], "name": segs[1], "teacher": "", "room": ""}
    for s in segs[2:]:
        if s.startswith("(") and s.endswith(")"):
            info["teacher"] = s[1:-1].strip()
        elif not info["room"]:
            info["room"] = s
    return info


def parse_ntut(text):
    """解析北科大「顯示課表」HTML。回傳 (sessions, meta)。連續節次的同一門課會合併成一筆。"""
    times = dict(DEFAULT_TIMES)
    for p, a, b in re.findall(r"第\s*([1-9NABCD])\s*節\s*[：:]\s*(\d{1,2}:\d{2})\s*[~～-]\s*(\d{1,2}:\d{2})", text):
        times[p] = (a.zfill(5), b.zfill(5))

    m = re.search(r"(\d{2,3})\s*學年度\s*第\s*(\d)\s*學期", text)
    meta = {"year": int(m.group(1)), "sem": int(m.group(2))} if m else {}

    parser = _CellCollector()
    parser.feed(text)
    cells = parser.cells

    # (code, 星期) -> {節次index: info}
    slots = {}
    i = 0
    while i < len(cells):
        if not _is_label(cells[i]):
            i += 1
            continue
        period = "".join(cells[i]["segs"]).strip()
        row = cells[i + 1:i + 8]
        i += 1
        if len(row) < 7 or any(_is_label(c) for c in row):
            continue
        for col, c in enumerate(row):  # 欄位 0=週日 … 6=週六
            info = _parse_cell(c)
            if info:
                weekday = (col - 1) % 7  # 轉成 Python：0=週一
                slots.setdefault((info["code"], weekday), {})[PERIOD_ORDER.index(period)] = info
        i += 7

    sessions = []
    for (code, weekday), by_idx in slots.items():
        idxs = sorted(by_idx)
        groups, run = [], [idxs[0]]
        for k in idxs[1:]:
            if k == run[-1] + 1:
                run.append(k)
            else:
                groups.append(run)
                run = [k]
        groups.append(run)
        for g in groups:
            info = by_idx[g[0]]
            sessions.append({**info, "weekday": weekday,
                             "start": times[PERIOD_ORDER[g[0]]][0],
                             "end": times[PERIOD_ORDER[g[-1]]][1]})
    sessions.sort(key=lambda s: (s["weekday"], s["start"]))
    return sessions, meta


PARSERS = {"北科大": parse_ntut}


def default_semester(meta):
    """依「115學年度第1學期」推測學期起訖日（只是預設值，介面上可自行修改）。"""
    if meta.get("year"):
        y = meta["year"] + 1911 + (0 if meta["sem"] == 1 else 1)
        anchor = date(y, 9, 8) if meta["sem"] == 1 else date(y, 2, 16)
    else:
        anchor = date.today()
    start = anchor + timedelta(days=(0 - anchor.weekday()) % 7)  # 該日起第一個週一
    return start, start + timedelta(weeks=18) - timedelta(days=1)


def decode_bytes(raw):
    for enc in ("utf-8-sig", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")
