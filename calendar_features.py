"""行事曆擴充模組：重複提醒 + CSV 匯入/匯出。

純 Python（標準函式庫），Streamlit 介面在 render_csv_and_repeat_ui()。
事件格式（dict）：
    title, date(YYYY-MM-DD), start(HH:MM), end(HH:MM), note,
    repeat(none/daily/weekly/monthly/yearly), until(YYYY-MM-DD 或空字串)
"""
import calendar
import csv
import io
from datetime import date, datetime, timedelta

REPEAT_OPTIONS = {"none": "不重複", "daily": "每天", "weekly": "每週",
                  "monthly": "每月", "yearly": "每年"}
CSV_FIELDS = ["title", "date", "start", "end", "note", "repeat", "until"]
# 中文欄位別名，方便直接用 Excel 編輯
_ALIASES = {"標題": "title", "日期": "date", "開始": "start", "結束": "end",
            "備註": "note", "重複": "repeat", "重複至": "until"}
_REPEAT_ZH = {v: k for k, v in REPEAT_OPTIONS.items()}
MAX_OCCURRENCES = 1000  # 無結束日時的安全上限


# ---------- 重複展開 ----------
def _add_months(d: date, n: int, anchor_day: int) -> date:
    """加 n 個月；當月沒有該日（如 31 號）時取月底。"""
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(anchor_day, calendar.monthrange(y, m)[1]))


def occurrences(event: dict, range_start: date, range_end: date):
    """回傳事件在 [range_start, range_end] 內的所有日期（同日期、同時段重複）。"""
    first = datetime.strptime(event["date"], "%Y-%m-%d").date()
    rep = event.get("repeat") or "none"
    until = event.get("until")
    last = datetime.strptime(until, "%Y-%m-%d").date() if until else range_end
    last = min(last, range_end)
    out, i = [], 0
    while i < MAX_OCCURRENCES:
        if rep == "none":
            d = first
        elif rep == "daily":
            d = first + timedelta(days=i)
        elif rep == "weekly":
            d = first + timedelta(weeks=i)
        elif rep == "monthly":
            d = _add_months(first, i, first.day)
        elif rep == "yearly":
            d = _add_months(first, 12 * i, first.day)
        else:
            raise ValueError(f"未知的重複類型：{rep}")
        if d > last:
            break
        if d >= range_start:
            out.append(d)
        if rep == "none":
            break
        i += 1
    return out


def expand_events(events, range_start: date, range_end: date):
    """展開所有事件為單次項目，依日期與開始時間排序。"""
    rows = []
    for e in events:
        for d in occurrences(e, range_start, range_end):
            rows.append({**e, "date": d.isoformat(), "source_date": e["date"]})
    return sorted(rows, key=lambda r: (r["date"], r["start"]))


# ---------- 驗證 ----------
def validate_event(e: dict) -> dict:
    """驗證並正規化一筆事件；錯誤時丟 ValueError。"""
    title = (e.get("title") or "").strip()
    if not title:
        raise ValueError("標題不可空白")
    d = datetime.strptime((e.get("date") or "").strip(), "%Y-%m-%d").date()
    start = datetime.strptime((e.get("start") or "").strip(), "%H:%M").strftime("%H:%M")
    end = datetime.strptime((e.get("end") or "").strip(), "%H:%M").strftime("%H:%M")
    if end <= start:
        raise ValueError("結束時間必須晚於開始時間")
    rep = (e.get("repeat") or "none").strip().lower()
    rep = _REPEAT_ZH.get(rep, rep)
    if rep not in REPEAT_OPTIONS:
        raise ValueError(f"重複類型不正確：{rep}")
    until = (e.get("until") or "").strip()
    if until:
        u = datetime.strptime(until, "%Y-%m-%d").date()
        if u < d:
            raise ValueError("重複結束日不可早於開始日")
    return {"title": title, "date": d.isoformat(), "start": start, "end": end,
            "note": (e.get("note") or "").strip(), "repeat": rep, "until": until}


# ---------- CSV ----------
def export_csv(events) -> bytes:
    """匯出為 UTF-8 with BOM，Excel 開啟中文不會亂碼。"""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    for e in events:
        w.writerow({k: e.get(k, "") or "" for k in CSV_FIELDS})
    return buf.getvalue().encode("utf-8-sig")


def import_csv(data: bytes, existing=()):
    """匯入 CSV。回傳 (新事件清單, 錯誤訊息清單)；與既有事件完全相同者會略過。"""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("big5", errors="replace")  # 舊版 Excel 的繁中編碼
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["檔案是空的"]
    reader.fieldnames = [_ALIASES.get(f.strip(), f.strip().lower())
                         for f in reader.fieldnames]
    missing = {"title", "date", "start", "end"} - set(reader.fieldnames)
    if missing:
        return [], [f"缺少必要欄位：{', '.join(sorted(missing))}"]
    key = lambda e: (e["title"], e["date"], e["start"], e["end"], e["repeat"])
    seen = {key(e) for e in existing if e.get("repeat")}
    added, errors = [], []
    for n, row in enumerate(reader, start=2):  # 第 1 列是標題
        try:
            ev = validate_event(row)
        except (ValueError, TypeError) as ex:
            errors.append(f"第 {n} 列：{ex}")
            continue
        if key(ev) in seen:
            continue
        seen.add(key(ev))
        added.append(ev)
    return added, errors


# ---------- Streamlit 介面 ----------
def render_csv_and_repeat_ui(events: list, save_event):
    """在你的 app 內呼叫。events=目前事件 list；save_event(ev) 負責寫入資料庫
    （Supabase insert 或 session_state append）。"""
    import streamlit as st

    with st.expander("➕ 新增（可重複）提醒"):
        with st.form("add_repeat", clear_on_submit=True):
            title = st.text_input("標題")
            d = st.date_input("日期")
            c1, c2 = st.columns(2)
            s = c1.time_input("開始", value=datetime.strptime("09:00", "%H:%M").time())
            e = c2.time_input("結束", value=datetime.strptime("10:00", "%H:%M").time())
            rep = st.selectbox("重複", list(REPEAT_OPTIONS), format_func=REPEAT_OPTIONS.get)
            until = st.date_input("重複至（不重複可忽略）", value=None)
            note = st.text_input("備註")
            if st.form_submit_button("新增"):
                try:
                    ev = validate_event({
                        "title": title, "date": d.isoformat(),
                        "start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"),
                        "note": note, "repeat": rep,
                        "until": until.isoformat() if until else ""})
                    save_event(ev)
                    st.success("已新增")
                except ValueError as ex:
                    st.error(str(ex))

    with st.expander("📁 CSV 匯入 / 匯出"):
        st.download_button("匯出 CSV", export_csv(events), "calendar.csv", "text/csv")
        up = st.file_uploader("匯入 CSV", type="csv")
        if up is not None and st.button("開始匯入"):
            added, errors = import_csv(up.getvalue(), events)
            for ev in added:
                save_event(ev)
            st.success(f"成功匯入 {len(added)} 筆")
            for m in errors:
                st.warning(m)
