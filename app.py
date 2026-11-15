"""行事曆 - Streamlit 版 (純 Python)
執行: streamlit run app.py
"""
import calendar
import csv
import hashlib
import hmac
import html
import io
import json
import os
import uuid
from datetime import date, datetime, timedelta

import streamlit as st

st.set_page_config(page_title="行事曆", page_icon="📅", layout="wide")

CATS = {
    "課程": "#4F8EF7",
    "作業": "#F7A24F",
    "考試": "#E5484D",
    "個人": "#30A46C",
    "其他": "#8E8E93",
}
REPEATS = ["無", "每天", "每週", "每月", "每年"]
WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
HOURS = range(7, 23)

CSS = """
<style>
.cal{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13px}
.cal th{background:rgba(79,142,247,.12);color:#4F8EF7;padding:6px;border:1px solid rgba(128,128,128,.25)}
.cal td{border:1px solid rgba(128,128,128,.25);vertical-align:top;height:96px;padding:4px;overflow:hidden}
.cal td.today{background:rgba(79,142,247,.10)}
.wk td{height:34px}
.wk td.h{width:56px;text-align:right;opacity:.65}
.chip{color:#fff;border-radius:6px;padding:2px 6px;margin:2px 0;font-size:11px;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.more{font-size:11px;opacity:.6}
.wd{text-align:center;font-weight:600;padding:6px 0;border-radius:8px;
    background:rgba(79,142,247,.12);color:#4F8EF7}
[class*="st-key-cell"]{border:1px solid rgba(128,128,128,.25);border-radius:12px;
    padding:6px 8px;min-height:112px;background:rgba(128,128,128,.04);gap:.2rem}
[class*="st-key-cellout-"]{opacity:.45}
[class*="st-key-celltoday-"]{border:2px solid #4F8EF7;background:rgba(79,142,247,.08)}
[class*="st-key-cell"] button{border:none;background:transparent;box-shadow:none;
    min-height:1.7rem;padding:0 .3rem;justify-content:flex-start;width:auto}
[class*="st-key-cell"] button p{font-weight:700;font-size:15px}
[class*="st-key-cell"] button:hover{background:rgba(79,142,247,.15)}
[class*="st-key-celltoday-"] button p{color:#4F8EF7}
.dayhead{display:flex;align-items:center;gap:16px;margin:6px 0 14px}
.dayhead .dn{font-size:48px;font-weight:800;line-height:1;color:#4F8EF7}
.dayhead .dw{font-size:18px;font-weight:600}
.dayhead .dc{font-size:13px;opacity:.6}
.dh{font-weight:700;margin:18px 0 4px;font-size:15px}
.ev{display:flex;gap:16px;align-items:center;padding:12px 16px;margin:10px 0;border-radius:12px;
    background:rgba(128,128,128,.07);border:1px solid rgba(128,128,128,.18)}
.ev-t{min-width:64px;text-align:center}
.ev-t .s{font-size:20px;font-weight:700}
.ev-t .e{font-size:12px;opacity:.6}
.ev-b{flex:1}
.ev .ti{font-size:16px;font-weight:600}
.ev .badge{color:#fff;font-size:11px;font-weight:500;border-radius:999px;padding:1px 9px;margin-left:8px}
.ev .no{font-size:13px;opacity:.7;margin-top:4px}
</style>
"""


# ---------- 帳號 ----------
def hash_pw(pw, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return {"salt": salt, "hash": h}


@st.cache_resource
def db():
    if "supabase" not in st.secrets:
        st.error("尚未設定 Supabase：請在 Streamlit Secrets 加入 [supabase] 的 url 與 key")
        st.stop()
    from supabase import create_client
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


def get_user(name):
    rows = db().table("users").select("*").eq("username", name).execute().data
    return rows[0] if rows else None


def create_user(name, pw):
    db().table("users").insert({"username": name, **hash_pw(pw)}).execute()


@st.cache_resource
def init_test_user():  # 測試帳號 1 / 111111（不存在才建立）
    if not get_user("1"):
        create_user("1", "111111")
    return True


def check_login(name, pw):
    u = get_user(name)
    return bool(u) and hmac.compare_digest(hash_pw(pw, u["salt"])["hash"], u["hash"])


def login_page():
    st.title("📅 行事曆")
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        tab_in, tab_up = st.tabs(["登入", "註冊"])
        with tab_in:
            with st.form("login"):
                name = st.text_input("帳號")
                pw = st.text_input("密碼", type="password")
                if st.form_submit_button("登入", use_container_width=True):
                    if check_login(name.strip(), pw):
                        st.session_state.user = name.strip()
                        st.rerun()
                    st.error("帳號或密碼錯誤")
        with tab_up:
            with st.form("signup"):
                name = st.text_input("新帳號")
                pw = st.text_input("新密碼", type="password")
                pw2 = st.text_input("再輸入一次密碼", type="password")
                if st.form_submit_button("建立帳號", use_container_width=True):
                    if not name.strip() or not pw:
                        st.error("帳號與密碼不可空白")
                    elif get_user(name.strip()):
                        st.error("此帳號已存在")
                    elif pw != pw2:
                        st.error("兩次密碼不一致")
                    else:
                        create_user(name.strip(), pw)
                        st.success("建立成功，請回到「登入」分頁")


# ---------- 資料（存在 Supabase，每個帳號各自一份） ----------
def _to_app(r):
    return {"id": r["id"], "title": r["title"], "date": r["date"], "start": r["start_time"][:5],
            "end": r["end_time"][:5], "cat": r["cat"], "repeat": r["repeat"],
            "until": r.get("repeat_until") or "", "note": r["note"] or ""}


def _to_db(e):
    return {"id": e["id"], "username": st.session_state.user, "title": e["title"], "date": e["date"],
            "start_time": e["start"], "end_time": e["end"], "cat": e["cat"],
            "repeat": e.get("repeat", "無"), "repeat_until": e.get("until") or None,
            "note": e.get("note", "")}


def load_events():
    rows = db().table("events").select("*").eq("username", st.session_state.user).execute().data
    return [_to_app(r) for r in rows]


def add_event(e):
    db().table("events").insert(_to_db(e)).execute()


def delete_event(eid):
    db().table("events").delete().eq("id", eid).eq("username", st.session_state.user).execute()


def replace_events(events):
    db().table("events").delete().eq("username", st.session_state.user).execute()
    if events:
        db().table("events").insert([_to_db({**e, "id": uuid.uuid4().hex[:8]}) for e in events]).execute()


def append_events(events):
    if events:
        db().table("events").insert([_to_db({**e, "id": uuid.uuid4().hex[:8]}) for e in events]).execute()


# ---------- 重複提醒（同日期、同時間段重複） ----------
def occurs_on(e, day):
    """事件 e 是否在 day 這天出現。每月/每年遇到沒有該日（如 31 號、2/29）時取月底。"""
    d0 = date.fromisoformat(e["date"])
    if day < d0:
        return False
    if e.get("until") and day > date.fromisoformat(e["until"]):
        return False
    if day == d0:
        return True
    rep = e.get("repeat", "無")
    last = calendar.monthrange(day.year, day.month)[1]
    if rep == "每天":
        return True
    if rep == "每週":
        return (day - d0).days % 7 == 0
    if rep == "每月":
        return day.day == min(d0.day, last)
    if rep == "每年":
        return day.month == d0.month and day.day == min(d0.day, last)
    return False


def events_on(events, day):
    return sorted((e for e in events if occurs_on(e, day)), key=lambda e: e["start"])


def find_conflicts(new, events, horizon_days=366):
    """回傳 new 與既有事件時段重疊的 [(日期, 事件)]。
    重複事件只檢查到「重複至」或一年內；首尾相接（10:00 結束、10:00 開始）不算衝突。"""
    d0 = date.fromisoformat(new["date"])
    end = d0 + timedelta(days=horizon_days)
    if new.get("until"):
        end = min(end, date.fromisoformat(new["until"]))
    out, day = [], d0
    while day <= end:
        if occurs_on(new, day):
            out += [(day, e) for e in events_on(events, day)
                    if new["start"] < e["end"] and e["start"] < new["end"]]
        day += timedelta(days=1)
    return out


def conflict_text(conflicts, limit=3):
    """同一個事件只列一次（顯示第一個衝突日期），多的用「等 N 項」帶過。"""
    firsts = {}
    for day, e in conflicts:
        firsts.setdefault(e["id"], (day, e))
    items = [f"「{e['title']}」（{d.month}/{d.day} {e['start']}–{e['end']}）"
             for d, e in list(firsts.values())[:limit]]
    more = f" 等 {len(firsts)} 項" if len(firsts) > limit else ""
    return "、".join(items) + more


# ---------- CSV 匯入 / 匯出 ----------
CSV_COLS = ["title", "date", "start", "end", "cat", "repeat", "until", "note"]
CSV_ALIAS = {"標題": "title", "日期": "date", "開始": "start", "結束": "end",
             "分類": "cat", "重複": "repeat", "重複至": "until", "備註": "note"}


def export_csv(events):
    """UTF-8 with BOM：Excel 開啟中文不會亂碼。"""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLS, extrasaction="ignore")
    w.writeheader()
    for e in sorted(events, key=lambda e: (e["date"], e["start"])):
        w.writerow({k: e.get(k, "") or "" for k in CSV_COLS})
    return buf.getvalue().encode("utf-8-sig")


def _parse(value, fmts):
    for f in fmts:
        try:
            return datetime.strptime(value.strip(), f)
        except ValueError:
            pass
    raise ValueError(f"格式不正確：{value}")


def _date(v):
    return _parse(v, ("%Y-%m-%d", "%Y/%m/%d")).date()


def _time(v):
    return _parse(v, ("%H:%M", "%H:%M:%S")).strftime("%H:%M")


def parse_csv(data, existing=()):
    """回傳 (新事件, 錯誤訊息)。與既有事件完全相同者略過。"""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("big5", errors="replace")  # 舊版 Excel 的繁中編碼
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["檔案是空的"]
    reader.fieldnames = [CSV_ALIAS.get(f.strip(), f.strip().lower()) for f in reader.fieldnames]
    missing = {"title", "date", "start", "end"} - set(reader.fieldnames)
    if missing:
        return [], [f"缺少必要欄位：{', '.join(sorted(missing))}"]
    key = lambda e: (e["title"], e["date"], e["start"], e["end"], e["repeat"])
    seen = {key(e) for e in existing}
    added, errors = [], []
    for n, row in enumerate(reader, start=2):  # 第 1 列是欄位標題
        try:
            title = (row.get("title") or "").strip()
            if not title:
                raise ValueError("標題不可空白")
            d, s, t = _date(row["date"]), _time(row["start"]), _time(row["end"])
            if t <= s:
                raise ValueError("結束時間需晚於開始時間")
            rep = (row.get("repeat") or "無").strip() or "無"
            if rep not in REPEATS:
                raise ValueError(f"重複需為 {'/'.join(REPEATS)}")
            until = (row.get("until") or "").strip()
            until = _date(until).isoformat() if until else ""
            if until and until < d.isoformat():
                raise ValueError("重複至不可早於日期")
            cat = (row.get("cat") or "").strip()
            ev = {"title": title, "date": d.isoformat(), "start": s, "end": t,
                  "cat": cat if cat in CATS else "其他", "repeat": rep, "until": until,
                  "note": (row.get("note") or "").strip()}
        except (ValueError, TypeError) as ex:
            errors.append(f"第 {n} 列：{ex}")
            continue
        if key(ev) in seen:
            continue
        seen.add(key(ev))
        added.append(ev)
    return added, errors


def finish_add(ev):
    add_event(ev)
    st.session_state.cur = date.fromisoformat(ev["date"])
    if st.session_state.get("selected"):
        st.session_state.selected = st.session_state.cur
    st.rerun()


def chip(e, with_time=True):
    t = f'{e["start"]} ' if with_time else ""
    return (f'<span class="chip" style="background:{CATS.get(e["cat"], "#8E8E93")}" '
            f'title="{html.escape(e.get("note", ""))}">{t}{html.escape(e["title"])}</span>')


# ---------- 檢視 ----------
def event_card(e):
    color = CATS.get(e["cat"], "#8E8E93")
    rep = f" · 🔁 {e['repeat']}" if e.get("repeat", "無") != "無" else ""
    note = (f"<div class='no'>備註: {html.escape(e['note']).replace(chr(10), '<br>')}</div>"
            if e.get("note") else "")
    return (f"<div class='ev' style='border-left:6px solid {color}'>"
            f"<div class='ev-t'><div class='s'>{e['start']}</div><div class='e'>{e['end']}</div></div>"
            f"<div class='ev-b'><div class='ti'>{html.escape(e['title'])}"
            f"<span class='badge' style='background:{color}'>{html.escape(e['cat'])}</span>{rep}</div>"
            f"{note}</div></div>")


def month_view(events, cur):
    for c, w in zip(st.columns(7), WEEKDAYS):
        c.markdown(f"<div class='wd'>週{w}</div>", unsafe_allow_html=True)
    for week in calendar.Calendar(0).monthdatescalendar(cur.year, cur.month):
        for col, d in zip(st.columns(7), week):
            kind = "celltoday" if d == date.today() else ("cellout" if d.month != cur.month else "cell")
            with col, st.container(key=f"{kind}-{d.isoformat()}"):
                label = f"{d.month}/{d.day}" if (d.month != cur.month or d.day == 1) else str(d.day)
                if st.button(label, key=f"day-{d.isoformat()}"):
                    st.session_state.selected = d
                    st.session_state.cur = d
                    st.rerun()
                evs = events_on(events, d)
                html_ = "".join(chip(e) for e in evs[:3])
                if len(evs) > 3:
                    html_ += f"<span class='more'>+{len(evs) - 3} 更多</span>"
                st.markdown(html_, unsafe_allow_html=True)


def day_view(events, d):
    evs = events_on(events, d)
    st.markdown(f"<div class='dayhead'><div class='dn'>{d.day}</div><div>"
                f"<div class='dw'>{d.year} 年 {d.month} 月 · 週{WEEKDAYS[d.weekday()]}</div>"
                f"<div class='dc'>共 {len(evs)} 項行程</div></div></div>", unsafe_allow_html=True)
    if not evs:
        st.info("這天沒有行程")
        return
    st.markdown("".join(event_card(e) for e in evs), unsafe_allow_html=True)


def week_view(events, cur):
    start = cur - timedelta(days=cur.weekday())
    days = [start + timedelta(days=i) for i in range(7)]
    rows = ["<table class='cal wk'><tr><th></th>" + "".join(
        f"<th>週{WEEKDAYS[i]}<br>{d.month}/{d.day}</th>" for i, d in enumerate(days)) + "</tr>"]
    per_day = {d: events_on(events, d) for d in days}
    for h in HOURS:
        rows.append(f"<tr><td class='h'>{h:02d}:00</td>")
        for d in days:
            hit = [e for e in per_day[d]
                   if int(e["start"][:2]) <= h < max(int(e["end"][:2]) + (e["end"][3:] != "00"),
                                                      int(e["start"][:2]) + 1)]
            cls = "today" if d == date.today() else ""
            rows.append(f"<td class='{cls}'>{''.join(chip(e, False) for e in hit)}</td>")
        rows.append("</tr>")
    rows.append("</table>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def list_view(events, cur):
    found = False
    for day in range(1, calendar.monthrange(cur.year, cur.month)[1] + 1):
        d = date(cur.year, cur.month, day)
        evs = events_on(events, d)
        if evs:
            found = True
            st.markdown(f"<div class='dh'>{d.month}/{d.day}（週{WEEKDAYS[d.weekday()]}）</div>"
                        + "".join(event_card(e) for e in evs), unsafe_allow_html=True)
    if not found:
        st.info("本月沒有事件")


# ---------- 主程式 ----------
init_test_user()
if "user" not in st.session_state:
    login_page()
    st.stop()

events = load_events()
if "cur" not in st.session_state:
    st.session_state.cur = date.today()
cur = st.session_state.cur

st.markdown(CSS, unsafe_allow_html=True)
if not st.session_state.get("selected"):
    st.title("📅 行事曆")

with st.sidebar:
    st.caption(f"👤 {st.session_state.user}")
    if st.button("登出", use_container_width=True):
        for k in ("user", "cur", "selected", "pending"):
            st.session_state.pop(k, None)
        st.rerun()
    st.divider()
    st.header("新增事件")
    with st.form("add", clear_on_submit=True):
        title = st.text_input("標題")
        d = st.date_input("日期", cur)
        c1, c2 = st.columns(2)
        t1 = c1.time_input("開始", datetime.strptime("09:00", "%H:%M").time())
        t2 = c2.time_input("結束", datetime.strptime("10:00", "%H:%M").time())
        cat = st.selectbox("分類", list(CATS))
        repeat = st.selectbox("重複（同日期、同時段）", REPEATS)
        until = st.date_input("重複至（可留空＝一直重複）", value=None)
        note = st.text_area("備註", height=70)
        if st.form_submit_button("新增", use_container_width=True):
            if not title.strip():
                st.error("請輸入標題")
            elif t2 <= t1:
                st.error("結束時間需晚於開始時間")
            elif until and until < d:
                st.error("「重複至」不可早於日期")
            else:
                new_ev = {"id": uuid.uuid4().hex[:8], "title": title.strip(),
                          "date": d.isoformat(), "start": t1.strftime("%H:%M"),
                          "end": t2.strftime("%H:%M"), "cat": cat,
                          "repeat": repeat, "until": until.isoformat() if until else "",
                          "note": note}
                if find_conflicts(new_ev, events):
                    st.session_state.pending = new_ev  # 先警告，等使用者確認
                    st.rerun()
                else:
                    finish_add(new_ev)

    pend = st.session_state.get("pending")
    if pend:
        st.warning(f"⚠️ 與 {conflict_text(find_conflicts(pend, events))} 時段重複，確認要新增"
                   f"「{pend['title']}」嗎？")
        b1, b2 = st.columns(2)
        if b1.button("仍要新增", use_container_width=True, type="primary"):
            st.session_state.pop("pending")
            finish_add(pend)
        if b2.button("取消", use_container_width=True):
            st.session_state.pop("pending")
            st.rerun()

    st.divider()
    st.header("刪除事件")
    if events:
        labels = {e["id"]: f'{e["date"]} {e["start"]} {e["title"]}'
                  + (f' 🔁{e["repeat"]}' if e["repeat"] != "無" else "") for e in
                  sorted(events, key=lambda e: (e["date"], e["start"]))}
        pick = st.selectbox("選擇事件", list(labels), format_func=labels.get)
        if st.button("刪除", use_container_width=True):
            delete_event(pick)
            st.rerun()
    else:
        st.caption("目前沒有事件")

    st.divider()
    st.header("匯入 / 匯出")
    st.download_button("匯出 CSV", export_csv(events), "events.csv", "text/csv",
                       use_container_width=True)
    up_csv = st.file_uploader("匯入 CSV（新增，不覆蓋）", type="csv")
    if up_csv and st.button("匯入 CSV", use_container_width=True):
        added, errors = parse_csv(up_csv.getvalue(), events)
        try:
            append_events(added)
            st.success(f"成功匯入 {len(added)} 筆")
        except Exception as ex:  # 資料庫寫入失敗
            st.error(f"寫入失敗：{ex}")
        for m in errors[:10]:
            st.warning(m)
        if len(errors) > 10:
            st.warning(f"另有 {len(errors) - 10} 筆錯誤未顯示")
    with st.expander("JSON（舊格式）"):
        st.download_button("匯出 JSON", json.dumps(events, ensure_ascii=False, indent=2),
                           "events.json", use_container_width=True)
        up = st.file_uploader("匯入 JSON", type="json")
        if up and st.button("匯入並覆蓋", use_container_width=True):
            try:
                data = json.load(up)
                assert isinstance(data, list)
                replace_events(data)
                st.rerun()
            except (json.JSONDecodeError, AssertionError, KeyError, TypeError):
                st.error("檔案格式錯誤")

sel = st.session_state.get("selected")
if sel:
    if st.button("← 返回"):
        st.session_state.selected = None
        st.rerun()
    day_view(events, sel)
    st.stop()

view = st.radio("檢視", ["月", "週", "清單"], horizontal=True, label_visibility="collapsed")
step = {"月": None, "週": 7, "清單": None}[view]

n1, n2, n3, n4 = st.columns([1, 1, 1, 5])
if n1.button("◀ 上一個"):
    st.session_state.cur = (cur - timedelta(days=step)) if step else \
        (cur.replace(day=1) - timedelta(days=1)).replace(day=1)
    st.rerun()
if n2.button("今天"):
    st.session_state.cur = date.today()
    st.rerun()
if n3.button("下一個 ▶"):
    st.session_state.cur = (cur + timedelta(days=step)) if step else \
        (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    st.rerun()
n4.subheader(f"{cur.year} 年 {cur.month} 月")

{"月": month_view, "週": week_view, "清單": list_view}[view](events, cur)
