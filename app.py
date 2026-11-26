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

from schedule_import import PARSERS, decode_bytes, default_semester

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
IMPORT_PREFIX = "tt-"  # 匯入課表產生的事件 id 前綴，重新匯入時用來辨識並取代
HOLIDAY = "放假"  # 放假標記（整天事件）的分類，不在 CATS 內所以不會出現在新增事件的分類選單
HOLIDAY_PREFIX = "hol-"

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
[data-testid="stHorizontalBlock"]:has(.wd) > [data-testid="stColumn"]:nth-child(n+6) .wd{
    background:rgba(229,72,77,.12);color:#E5484D}
.wk th:nth-child(n+7){background:rgba(229,72,77,.12);color:#E5484D}
[class*="st-key-cell"]{border:1px solid rgba(128,128,128,.25);border-radius:12px;
    padding:6px 8px;min-height:112px;background:rgba(128,128,128,.04);gap:.2rem}
[class*="st-key-cellout-"]{opacity:.45}
[class*="st-key-celltoday-"]{border:2px solid #4F8EF7;background:rgba(79,142,247,.08)}
[class*="st-key-cellhol-"]{background:rgba(128,128,128,.22)}
.cal td.hol{background:rgba(128,128,128,.22)}
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


def import_courses(sessions, start, end):
    """把解析出的課程寫成「每週重複、到學期結束日為止」的事件，並取代先前匯入的課表。"""
    user = st.session_state.user
    rows = []
    for s in sessions:
        first = start + timedelta(days=(s["weekday"] - start.weekday()) % 7)
        if first > end:
            continue
        note = "\n".join(x for x in (f"課號：{s['code']}", f"教師：{s['teacher']}" if s["teacher"] else "",
                                     f"教室：{s['room']}" if s["room"] else "") if x)
        rows.append(_to_db({"id": IMPORT_PREFIX + uuid.uuid4().hex[:8], "title": s["name"],
                            "date": first.isoformat(), "start": s["start"], "end": s["end"],
                            "cat": "課程", "repeat": "每週", "note": note, "until": end.isoformat()}))
    old = [r["id"] for r in db().table("events").select("id").eq("username", user)
           .like("id", IMPORT_PREFIX + "%").execute().data]
    if rows:
        db().table("events").insert(rows).execute()  # 先寫入新的；失敗時舊課表不會被刪掉
    if old:
        db().table("events").delete().eq("username", user).in_("id", old).execute()
    return len(rows)


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


def holiday_dates(events):
    return {e["date"] for e in events if e.get("cat") == HOLIDAY}


def is_holiday(events, day):
    return day.isoformat() in holiday_dates(events)


def events_on(events, day):
    """當天出現的事件（放假標記本身不算）。放假日的事件仍會回傳，畫面上以灰底顯示。"""
    return sorted((e for e in events if e.get("cat") != HOLIDAY and occurs_on(e, day)),
                  key=lambda e: e["start"])


def busy_on(events, day):
    """放假日視為沒有行程（用於衝突檢查與共同空閒）。"""
    return [] if is_holiday(events, day) else events_on(events, day)


def set_holidays(days, events):
    """把指定日期標為放假（已是放假的略過），回傳新增天數。"""
    have = holiday_dates(events)
    rows = [_to_db({"id": HOLIDAY_PREFIX + uuid.uuid4().hex[:8], "title": "放假", "date": d.isoformat(),
                    "start": "00:00", "end": "23:59", "cat": HOLIDAY, "repeat": "無", "until": "",
                    "note": ""}) for d in days if d.isoformat() not in have]
    if rows:
        db().table("events").insert(rows).execute()
    return len(rows)


def clear_holidays(days, events):
    ids = [e["id"] for e in events if e.get("cat") == HOLIDAY and date.fromisoformat(e["date"]) in set(days)]
    if ids:
        db().table("events").delete().eq("username", st.session_state.user).in_("id", ids).execute()
    return len(ids)


def clear_courses(titles=None):
    """清除匯入的課表；titles 有值時只清除這些課程，否則全部清除。"""
    q = (db().table("events").delete().eq("username", st.session_state.user)
         .like("id", IMPORT_PREFIX + "%"))
    if titles:
        q = q.in_("title", list(titles))
    q.execute()


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
            out += [(day, e) for e in busy_on(events, day)
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
                  "cat": cat if (cat in CATS or cat == HOLIDAY) else "其他", "repeat": rep, "until": until,
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


@st.dialog("⚠️ 時段重複")
def confirm_dialog(ev, text):
    st.write(f"與 {text} 時段重複。")
    st.write(f"確認要新增「{ev['title']}」嗎？")
    b1, b2 = st.columns(2)
    if b1.button("仍要新增", use_container_width=True, type="primary"):
        finish_add(ev)
    if b2.button("取消", use_container_width=True):
        st.rerun()


def chip(e, with_time=True, off=False):
    t = f'{e["start"]} ' if with_time else ""
    bg = "#B5B5BA" if off else CATS.get(e["cat"], "#8E8E93")
    extra = ";opacity:.75;text-decoration:line-through" if off else ""
    return (f'<span class="chip" style="background:{bg}{extra}" '
            f'title="{html.escape(e.get("note", ""))}">{t}{html.escape(e["title"])}</span>')


# ---------- 檢視 ----------
def event_card(e, off=False):
    color = "#B5B5BA" if off else CATS.get(e["cat"], "#8E8E93")
    dim = ";opacity:.6" if off else ""
    rep = ""
    if e.get("repeat", "無") != "無":
        rep = f" · 🔁 {e['repeat']}" + (f"（至 {e['until']}）" if e.get("until") else "")
    note = (f"<div class='no'>備註: {html.escape(e['note']).replace(chr(10), '<br>')}</div>"
            if e.get("note") else "")
    return (f"<div class='ev' style='border-left:6px solid {color}{dim}'>"
            f"<div class='ev-t'><div class='s'>{e['start']}</div><div class='e'>{e['end']}</div></div>"
            f"<div class='ev-b'><div class='ti'>{html.escape(e['title'])}"
            f"<span class='badge' style='background:{color}'>{html.escape(e['cat'])}</span>{rep}</div>"
            f"{note}</div></div>")


def month_view(events, cur):
    hol = holiday_dates(events)
    for c, w in zip(st.columns(7), WEEKDAYS):
        c.markdown(f"<div class='wd'>週{w}</div>", unsafe_allow_html=True)
    for week in calendar.Calendar(0).monthdatescalendar(cur.year, cur.month):
        for col, d in zip(st.columns(7), week):
            off = d.isoformat() in hol
            kind = ("celltoday" if d == date.today() else "cellhol" if off
                    else "cellout" if d.month != cur.month else "cell")
            with col, st.container(key=f"{kind}-{d.isoformat()}"):
                label = f"{d.month}/{d.day}" if (d.month != cur.month or d.day == 1) else str(d.day)
                if st.button(label, key=f"day-{d.isoformat()}"):
                    st.session_state.selected = d
                    st.session_state.cur = d
                    st.rerun()
                evs = events_on(events, d)
                html_ = ("<span class='more'>🏖 放假</span>" if off else "") + "".join(chip(e, off=off) for e in evs[:3])
                if len(evs) > 3:
                    html_ += f"<span class='more'>+{len(evs) - 3} 更多</span>"
                st.markdown(html_, unsafe_allow_html=True)


def day_view(events, d):
    evs = events_on(events, d)
    off = is_holiday(events, d)
    st.markdown(f"<div class='dayhead'><div class='dn'>{d.day}</div><div>"
                f"<div class='dw'>{d.year} 年 {d.month} 月 · 週{WEEKDAYS[d.weekday()]}</div>"
                f"<div class='dc'>共 {len(evs)} 項行程</div></div></div>", unsafe_allow_html=True)
    if off:
        st.info("🏖 這天已設為放假，當日行程以灰底顯示。")
    if st.button("↩ 取消放假" if off else "🏖 設為放假", key=f"holtoggle-{d.isoformat()}"):
        if off:
            clear_holidays([d], events)
        else:
            set_holidays([d], events)
        st.rerun()
    if not evs:
        st.info("這天沒有行程")
        return
    if not st.session_state.get("delete_mode"):
        st.markdown("".join(event_card(e, off) for e in evs), unsafe_allow_html=True)
        return
    st.warning("清除模式：請選擇要清除的事件")
    for e in evs:
        st.markdown(event_card(e, off), unsafe_allow_html=True)
        series = e.get("repeat", "無") != "無"
        if st.button("🗑 刪除整個重複系列" if series else "🗑 刪除", key=f"del-{e['id']}"):
            delete_event(e["id"])
            st.rerun()


def week_view(events, cur):
    start = cur - timedelta(days=cur.weekday())
    days = [start + timedelta(days=i) for i in range(7)]
    rows = ["<table class='cal wk'><tr><th></th>" + "".join(
        f"<th>週{WEEKDAYS[i]}<br>{d.month}/{d.day}</th>" for i, d in enumerate(days)) + "</tr>"]
    per_day = {d: events_on(events, d) for d in days}
    hol = holiday_dates(events)
    for h in HOURS:
        rows.append(f"<tr><td class='h'>{h:02d}:00</td>")
        for d in days:
            hit = [e for e in per_day[d]
                   if int(e["start"][:2]) <= h < max(int(e["end"][:2]) + (e["end"][3:] != "00"),
                                                      int(e["start"][:2]) + 1)]
            off = d.isoformat() in hol
            cls = ("today" if d == date.today() else "") + (" hol" if off else "")
            rows.append(f"<td class='{cls}'>{''.join(chip(e, False, off) for e in hit)}</td>")
        rows.append("</tr>")
    rows.append("</table>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def list_view(events, cur):
    found = False
    hol = holiday_dates(events)
    for day in range(1, calendar.monthrange(cur.year, cur.month)[1] + 1):
        d = date(cur.year, cur.month, day)
        off = d.isoformat() in hol
        evs = events_on(events, d)
        if evs or off:
            found = True
            st.markdown(f"<div class='dh'>{d.month}/{d.day}（週{WEEKDAYS[d.weekday()]}）"
                        + ("　🏖 放假" if off else "") + "</div>"
                        + "".join(event_card(e, off) for e in evs), unsafe_allow_html=True)
    if not found:
        st.info("本月沒有事件")


# ---------- 共同空閒時段 ----------
def to_min(t):
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def fmt_min(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_dur(m):
    h, r = divmod(m, 60)
    return (f"{h} 小時" if h else "") + (f" {r} 分" if r else "")


def common_free(people, d1, d2, w1, w2, min_len):
    """people: 多份事件清單。回傳 [(日期, 起(分), 迄(分))]：所有人在 [w1, w2] 內都沒事、
    且長度 >= min_len 的時段（每份清單都會展開重複事件）。"""
    out, day = [], d1
    while day <= d2:
        busy = sorted((max(to_min(e["start"]), w1), min(to_min(e["end"]), w2))
                      for evs in people for e in busy_on(evs, day))
        cursor, slots = w1, []
        for s, e in busy:
            if e <= s:  # 完全在時間窗之外
                continue
            if s - cursor >= min_len:
                slots.append((cursor, s))
            cursor = max(cursor, e)
        if w2 - cursor >= min_len:
            slots.append((cursor, w2))
        out += [(day, a, b) for a, b in slots]
        day += timedelta(days=1)
    return out


def free_time_view(my_events):
    st.subheader("🤝 共同空閒時段")
    st.caption("匯入其他人用本系統匯出的 CSV（不限人數），檔案只在這次使用中處理，不會存進資料庫。")
    files = st.file_uploader("匯入其他人的行事曆 CSV（可多選）", type="csv",
                             accept_multiple_files=True)
    people = {"我": my_events}
    for f in files or []:
        name, n = os.path.splitext(f.name)[0], 2
        while name in people:  # 檔名重複時加編號
            name, n = f"{os.path.splitext(f.name)[0]}({n})", n + 1
        evs, errors = parse_csv(f.getvalue())
        people[name] = evs
        for m in errors[:3]:
            st.warning(f"{f.name}：{m}")
    picked = st.multiselect("參與的人", list(people), default=list(people))
    if not picked:
        st.info("請至少選擇一位")
        return

    c1, c2, c3 = st.columns(3)
    dr = c1.date_input("日期範圍", value=(date.today(), date.today() + timedelta(days=6)))
    w1 = c2.time_input("每天最早", datetime.strptime("08:00", "%H:%M").time())
    w2 = c2.time_input("每天最晚", datetime.strptime("22:00", "%H:%M").time())
    min_len = c3.selectbox("最短空檔（分鐘）", [30, 60, 90, 120, 180], index=1)
    if len(dr) < 2:
        st.info("請選擇範圍的結束日期")
        return
    d1, d2 = dr
    if (d2 - d1).days > 92:
        st.error("日期範圍最多 93 天")
        return
    a, b = to_min(w1.strftime("%H:%M")), to_min(w2.strftime("%H:%M"))
    if b <= a:
        st.error("「最晚」需晚於「最早」")
        return

    slots = common_free([people[p] for p in picked], d1, d2, a, b, min_len)
    st.markdown(f"**{len(picked)} 人**（{'、'.join(picked)}）｜{d1} ～ {d2}｜"
                f"共 **{len(slots)}** 個共同空閒時段")
    if not slots:
        st.info("這個範圍內沒有大家都有空的時段，試試縮短最短空檔或放寬每天時間")
        return
    html_, last = [], None
    for d, s, e in slots:
        if d != last:
            html_.append(f"<div class='dh'>{d.month}/{d.day}（週{WEEKDAYS[d.weekday()]}）</div>")
            last = d
        html_.append(
            "<div class='ev' style='border-left:6px solid #30A46C'>"
            f"<div class='ev-t'><div class='s'>{fmt_min(s)}</div><div class='e'>{fmt_min(e)}</div></div>"
            f"<div class='ev-b'><div class='ti'>全員有空 · {fmt_dur(e - s)}</div></div></div>")
    st.markdown("".join(html_), unsafe_allow_html=True)


# ---------- 放假設定 ----------
@st.dialog("🏖 放假設定")
def holiday_dialog(events, cur):
    st.caption("放假日的行程以灰底顯示，且不計入衝突檢查與共同空閒。單日也可在當天頁面設定。")
    rng = st.date_input("放假日期（可選一段）", (cur, cur), key="hol_range")
    days = list(rng) if isinstance(rng, (tuple, list)) else [rng]
    if len(days) < 1:
        return
    a, b = days[0], days[-1]
    span = [a + timedelta(days=i) for i in range((b - a).days + 1)]
    if len(span) > 120:
        st.error("一次最多設定 120 天")
        return
    if st.button("標為放假", use_container_width=True, type="primary"):
        set_holidays(span, events)
        st.session_state.cur = a
        st.toast(f"已標為放假：{len(span)} 天")
        st.rerun()
    if st.button("取消這段放假", use_container_width=True):
        clear_holidays(span, events)
        st.rerun()


# ---------- 課表匯入 ----------
@st.dialog("📥 匯入課表", width="large")
def import_dialog():
    mine = [e for e in events if e["id"].startswith(IMPORT_PREFIX)]
    if mine:
        titles = sorted({e["title"] for e in mine})
        st.caption(f"目前已匯入 {len(titles)} 門課")
        pick = st.multiselect("清除課程", titles, placeholder="選擇要清除的課程")
        if pick and st.button("清除所選課程", use_container_width=True):
            clear_courses(pick)
            st.rerun()
        sure = st.checkbox("確認要清除全部已匯入的課程", key="clr_all_ok")
        if st.button("🗑 清除全部課程", use_container_width=True, disabled=not sure):
            clear_courses()
            st.rerun()
        st.divider()
    school = st.selectbox("學校", list(PARSERS), help="目前僅支援北科大，其他學校之後再加入")
    st.caption("北科大：登入「網路加退選系統」→「顯示課表」→ 另存網頁（.html）上傳，"
               "或檢視原始碼全選後貼在下方。")
    f = st.file_uploader("上傳課表 HTML", type=["html", "htm", "txt"], key="tt_file")
    pasted = st.text_area("或貼上 HTML 原始碼", height=80, key="tt_paste")
    raw = decode_bytes(f.getvalue()) if f else (pasted if pasted.strip() else None)
    if not raw:
        return
    sessions, meta = PARSERS[school](raw)
    if not sessions:
        st.error("找不到課程，請確認是「顯示課表」頁面的內容")
        return
    n_course = len({s["code"] for s in sessions})
    st.success(f"解析到 {n_course} 門課、共 {len(sessions)} 個上課時段")
    st.dataframe(
        [{"星期": f"週{WEEKDAYS[s['weekday']]}", "時間": f"{s['start']}-{s['end']}",
          "課程": s["name"], "教室": s["room"]} for s in sessions],
        hide_index=True, use_container_width=True)
    d0, d1 = default_semester(meta)
    tag = f"{meta.get('year')}-{meta.get('sem')}"
    start = st.date_input("學期開始日", d0, key=f"tt_s_{tag}")
    end = st.date_input("學期結束日", d1, key=f"tt_e_{tag}")
    st.caption("課程會每週重複到結束日為止；重新匯入會取代先前匯入的課表。")
    if st.button("匯入課表", use_container_width=True, type="primary"):
        if end < start:
            st.error("結束日不可早於開始日")
            return
        try:
            import_courses(sessions, start, end)
        except Exception as ex:  # 最常見原因：events 資料表還沒有 repeat_until 欄位
            st.error(f"匯入失敗：請確認 Supabase 的 events 資料表有 repeat_until 欄位。（{ex}）")
            return
        today = date.today()
        if not start <= today <= end:
            st.session_state.cur = start
        st.toast(f"已匯入 {n_course} 門課")
        st.rerun()


# ---------- 新增事件 ----------
@st.dialog("➕ 新增事件")
def add_dialog(cur, events):
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
        if st.form_submit_button("新增", use_container_width=True, type="primary"):
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


# ---------- 匯入 / 匯出 ----------
@st.dialog("⇅ 匯入 / 匯出")
def io_dialog(events):
    st.download_button("匯出 CSV", export_csv(events), "events.csv", "text/csv",
                       use_container_width=True)
    up_csv = st.file_uploader("匯入 CSV（新增，不覆蓋）", type="csv")
    if up_csv and st.button("匯入 CSV", use_container_width=True, type="primary"):
        added, errors = parse_csv(up_csv.getvalue(), events)
        try:
            append_events(added)
        except Exception as ex:  # 資料庫寫入失敗
            st.error(f"寫入失敗：{ex}")
            return
        if not errors:
            st.toast(f"成功匯入 {len(added)} 筆")
            st.rerun()
        st.success(f"成功匯入 {len(added)} 筆（關閉視窗後重新整理即可看到）")
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
from mobile_fix import inject_mobile_css
inject_mobile_css()
sel = st.session_state.get("selected")
if not sel:
    st.title("📅 行事曆")

# 工具列：原本側邊欄的功能都收進這裡（新增 / 匯入 / 放假 / 清除 / 匯入匯出 / 登出）
with st.container(key="toolbar"):
    tb = st.columns(6)
    if tb[0].button("➕ 新增", use_container_width=True):
        add_dialog(cur, events)
    if tb[1].button("📥 課表", use_container_width=True):
        import_dialog()
    if tb[2].button("🏖 放假", use_container_width=True):
        holiday_dialog(events, cur)
    on = st.session_state.get("delete_mode", False)
    if tb[3].button("✅ 結束清除" if on else "🗑 清除", use_container_width=True,
                    type="primary" if on else "secondary"):
        st.session_state.delete_mode = not on
        st.rerun()
    if tb[4].button("⇅ 匯入匯出", use_container_width=True):
        io_dialog(events)
    if tb[5].button("👤 登出", use_container_width=True, help=f"目前帳號：{st.session_state.user}"):
        for k in ("user", "cur", "selected", "pending", "delete_mode"):
            st.session_state.pop(k, None)
        st.rerun()

pend = st.session_state.pop("pending", None)  # 取出即清除，關掉視窗不會再跳
if pend:
    confirm_dialog(pend, conflict_text(find_conflicts(pend, events)))

if sel:
    if st.button("← 返回"):
        st.session_state.selected = None
        st.rerun()
    day_view(events, sel)
    st.stop()

if st.session_state.get("delete_mode"):
    st.warning("🗑 清除模式：點選日期，進入當日後選擇要清除的事件")
head = st.container()  # 年月標題（在「檢視」那一排的上方）
with st.container(key="viewrow"):  # 檢視選項在左，上一個 / 今天 / 下一個在同一排的右側
    vc = st.columns([5, 1, 1, 1])
    view = vc[0].radio("檢視", ["月", "週", "清單", "共同空閒"], horizontal=True,
                       label_visibility="collapsed")
if view == "共同空閒":
    free_time_view(events)
    st.stop()
step = {"月": None, "週": 7, "清單": None}[view]

head.subheader(f"{cur.year} 年 {cur.month} 月")
if vc[1].button("◀ 上一個", use_container_width=True):
    st.session_state.cur = (cur - timedelta(days=step)) if step else \
        (cur.replace(day=1) - timedelta(days=1)).replace(day=1)
    st.rerun()
if vc[2].button("今天", use_container_width=True):
    st.session_state.cur = date.today()
    st.rerun()
if vc[3].button("下一個 ▶", use_container_width=True):
    st.session_state.cur = (cur + timedelta(days=step)) if step else \
        (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    st.rerun()

{"月": month_view, "週": week_view, "清單": list_view}[view](events, cur)
