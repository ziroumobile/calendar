"""手機版排版修正：讓月曆的 7 欄在窄螢幕也維持橫向，不要被 Streamlit 自動改成直排。
用法（app.py 內，放在 st.markdown(CSS, ...) 那行的後面）：
    from mobile_fix import inject_mobile_css
    inject_mobile_css()
"""
import streamlit as st

_ROWS = ('[data-testid="stHorizontalBlock"]:has(.wd), '
         '[data-testid="stHorizontalBlock"]:has([class*="st-key-cell"])')  # 星期列、日期列
_COLS = ('[data-testid="stHorizontalBlock"]:has(.wd) > [data-testid="stColumn"], '
         '[data-testid="stHorizontalBlock"]:has([class*="st-key-cell"]) > [data-testid="stColumn"]')
_TB = '.st-key-toolbar [data-testid="stHorizontalBlock"]'
_VR = '.st-key-viewrow [data-testid="stHorizontalBlock"]'

MOBILE_CSS = f"""
<style>
@media (max-width: 640px) {{
  {_ROWS} {{flex-direction:row !important;flex-wrap:nowrap !important;gap:2px !important}}
  {_COLS} {{min-width:0 !important;width:0 !important;flex:1 1 0 !important}}
  .st-key-topbar [data-testid="stHorizontalBlock"] {{flex-direction:row !important;flex-wrap:nowrap !important;gap:4px !important}}
  .st-key-topbar [data-testid="stColumn"] {{min-width:0 !important;width:auto !important;flex:1 1 auto !important}}
  .st-key-topbar [data-testid="stColumn"]:last-child {{flex:0 0 56px !important}}
  .st-key-toolbar [data-testid="stColumn"]:first-child {{display:none !important}}
  .st-key-topbar h1 {{font-size:1.6rem !important}}
  {_TB} {{flex-direction:row !important;flex-wrap:wrap !important;gap:4px !important}}
  {_TB} > [data-testid="stColumn"] {{min-width:0 !important;width:auto !important;flex:1 1 30% !important}}
  {_VR} {{flex-direction:row !important;flex-wrap:wrap !important;gap:4px !important}}
  {_VR} > [data-testid="stColumn"] {{min-width:0 !important;width:auto !important;flex:1 1 0 !important}}
  {_VR} > [data-testid="stColumn"]:first-child {{flex:1 1 100% !important}}
  .st-key-toolbar button, .st-key-viewrow button {{padding:0 4px !important;min-height:2.2rem !important}}
  .st-key-topbar button {{min-height:2.6rem !important}}
  .st-key-topbar button p {{font-size:26px !important}}
  .st-key-toolbar button p, .st-key-viewrow button p {{font-size:13px !important;white-space:nowrap}}
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
