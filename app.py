"""行事曆 - Streamlit 版 (純 Python)
執行: streamlit run app.py
"""
import calendar
import hashlib
import hmac
import html
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
            "end": r["end_time"][:5], "cat": r["cat"], "repeat": r["repeat"], "note": r["note"] or ""}


def _to_db(e):
    return {"id": e["id"], "username": st.session_state.user, "title": e["title"], "date": e["date"],
            "start_time": e["start"], "end_time": e["end"], "cat": e["cat"],
            "repeat": e.get("repeat", "無"), "note": e.get("note", "")}


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


def events_on(events, day):
    out = []
    for e in events:
        d0 = date.fromisoformat(e["date"])
        if d0 == day or (e.get("repeat") == "每週" and d0 <= day and (day - d0).days % 7 == 0):
            out.append(e)
    return sorted(out, key=lambda e: e["start"])


def chip(e, with_time=True):
    t = f'{e["start"]} ' if with_time else ""
    return (f'<span class="chip" style="background:{CATS.get(e["cat"], "#8E8E93")}" '
            f'title="{html.escape(e.get("note", ""))}">{t}{html.escape(e["title"])}</span>')


# ---------- 檢視 ----------
def event_card(e):
    color = CATS.get(e["cat"], "#8E8E93")
    rep = " · 🔁 每週" if e.get("repeat") == "每週" else ""
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
        for k in ("user", "cur", "selected"):
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
        repeat = st.selectbox("重複", ["無", "每週"])
        note = st.text_area("備註", height=70)
        if st.form_submit_button("新增", use_container_width=True):
            if not title.strip():
                st.error("請輸入標題")
            elif t2 <= t1:
                st.error("結束時間需晚於開始時間")
            else:
                add_event({"id": uuid.uuid4().hex[:8], "title": title.strip(),
                           "date": d.isoformat(), "start": t1.strftime("%H:%M"),
                           "end": t2.strftime("%H:%M"), "cat": cat,
                           "repeat": repeat, "note": note})
                st.session_state.cur = d
                if st.session_state.get("selected"):
                    st.session_state.selected = d
                st.rerun()

    st.divider()
    st.header("刪除事件")
    if events:
        labels = {e["id"]: f'{e["date"]} {e["start"]} {e["title"]}' for e in
                  sorted(events, key=lambda e: (e["date"], e["start"]))}
        pick = st.selectbox("選擇事件", list(labels), format_func=labels.get)
        if st.button("刪除", use_container_width=True):
            delete_event(pick)
            st.rerun()
    else:
        st.caption("目前沒有事件")

    st.divider()
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
