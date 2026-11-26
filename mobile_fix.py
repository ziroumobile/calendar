"""手機版排版修正：讓月曆的 7 欄在窄螢幕也維持橫向，不要被 Streamlit 自動改成直排。
用法（app.py 內，放在 st.markdown(CSS, ...) 那行的後面）：
    from mobile_fix import inject_mobile_css
    inject_mobile_css()
"""
import streamlit as st

_ROWS = ('[data-testid="stHorizontalBlock"]:has(.wd), '
         '[data-testid="stHorizontalBlock"]:has([class*="st-key-cell"]), '
         '[data-testid="stHorizontalBlock"]:has(button):has(h3)')  # 星期列、日期列、上一個/今天/下一個列
_COLS = ('[data-testid="stHorizontalBlock"]:has(.wd) > [data-testid="stColumn"], '
         '[data-testid="stHorizontalBlock"]:has([class*="st-key-cell"]) > [data-testid="stColumn"], '
         '[data-testid="stHorizontalBlock"]:has(button):has(h3) > [data-testid="stColumn"]')

_NAV = '[data-testid="stHorizontalBlock"]:has(button):has(h3)'
_NAV_TITLE = _NAV + ' > [data-testid="stColumn"]:last-child'

MOBILE_CSS = f"""
<style>
@media (max-width: 640px) {{
  {_ROWS} {{flex-direction:row !important;flex-wrap:nowrap !important;gap:2px !important}}
  {_COLS} {{min-width:0 !important;width:0 !important;flex:1 1 0 !important}}
  {_NAV_TITLE} {{flex:2.6 1 0 !important}}
  {_NAV} button {{padding:0 4px !important;min-height:2rem !important}}
  {_NAV} button p {{font-size:12px !important;white-space:nowrap}}
  {_NAV} h3 {{font-size:1.05rem !important;white-space:nowrap;padding:0 !important;text-align:right}}
  .block-container {{padding-left:.5rem !important;padding-right:.5rem !important}}
  .wd {{font-size:11px;padding:4px 0;border-radius:6px}}
  [class*="st-key-cell"] {{padding:2px !important;min-height:64px !important;border-radius:6px !important;gap:0 !important}}
  [class*="st-key-celltoday-"] {{border-width:1px !important}}
  [class*="st-key-cell"] button {{padding:0 2px !important;min-height:1.3rem !important}}
  [class*="st-key-cell"] button p {{font-size:12px !important}}
  .chip {{font-size:9px;padding:1px 2px;margin:1px 0;border-radius:3px}}
  .more {{font-size:9px}}
  .cal td {{height:auto;padding:2px;font-size:10px}}
}}
</style>
"""


def inject_mobile_css():
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
