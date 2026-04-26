#!/usr/bin/env python3
"""
Notion → hukuoka_wCH.html 자동 생성기
Usage: NOTION_TOKEN=<token> python3 generate_fukuoka.py
"""
import os, requests, html as htmllib
from collections import defaultdict
from datetime import datetime, date

TOKEN = os.environ["NOTION_TOKEN"]
H = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

SCHEDULE_DB = "40129c84f79b462da09d6e2700fec886"
BOOKING_DB  = "f2a0571e9ca9495c96b31930a224886b"
PACKING_DB  = "9704d6e72ec1462cb932a5b03717b105"

# ── Notion API ────────────────────────────────────────────────────────────────

def nget(url, **params):
    r = requests.get(url, headers=H, params=params)
    r.raise_for_status()
    return r.json()

def npost(url, body=None):
    r = requests.post(url, headers=H, json=body or {})
    r.raise_for_status()
    return r.json()

def query_db(db_id, sorts=None):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    body, out = ({"sorts": sorts} if sorts else {}), []
    while True:
        d = npost(url, body)
        out += d["results"]
        if not d.get("has_more"):
            break
        body["start_cursor"] = d["next_cursor"]
    return out

def get_blocks(block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    out, params = [], {"page_size": 100}
    while True:
        d = nget(url, **params)
        out += d["results"]
        if not d.get("has_more"):
            break
        params["start_cursor"] = d["next_cursor"]
    return out

def rt(lst):
    return "".join(t.get("plain_text", "") for t in lst)

def get_prop(page, name):
    p = page["properties"].get(name, {})
    t = p.get("type", "")
    if t == "title":     return rt(p.get("title", []))
    if t == "rich_text": return rt(p.get("rich_text", []))
    if t == "date":
        d = p.get("date")
        return (d["start"], d.get("end") or "") if d else ("", "")
    if t == "select":    s = p.get("select");  return s["name"] if s else ""
    if t == "status":    s = p.get("status");  return s["name"] if s else ""
    if t == "number":    return p.get("number")
    if t == "checkbox":  return p.get("checkbox", False)
    return ""

def get_table_rows(page_id):
    rows = []
    for block in get_blocks(page_id):
        if block["type"] != "table":
            continue
        skip = True
        for rb in get_blocks(block["id"]):
            if rb["type"] != "table_row":
                continue
            cells = [rt(c) for c in rb["table_row"]["cells"]]
            if skip:
                skip = False
                continue
            if any(c.strip() for c in cells):
                rows.append(cells)
    return rows

# ── HTML 헬퍼 ─────────────────────────────────────────────────────────────────

def e(s):
    return htmllib.escape(str(s))

def tl_item(time, title, sub="", tags=None, minor=False):
    cls = "tl-item" + (" minor" if minor else "")
    tags_html = ""
    if tags:
        tags_html = '<div class="tl-tags">' + "".join(
            f'<span class="tag {tc}">{e(t)}</span>' for tc, t in tags if t
        ) + "</div>"
    sub_html = f'<div class="tl-sub">{e(sub).replace(chr(10), "<br>")}</div>' if sub.strip() else ""
    time_html = f'<div class="tl-time">{e(time)}</div>' if time.strip() else ""
    return f"""
      <div class="{cls}">
        <div class="tl-dot"></div>
        {time_html}
        <div class="tl-title">{e(title)}</div>
        {sub_html}
        {tags_html}
      </div>"""

def status_badge(status):
    cls = {
        "예약완료": "status-done", "결제완료": "status-paid",
        "해야함": "status-todo", "예약예정": "status-plan", "진행중": "status-plan",
    }.get(status, "status-plan")
    return f'<span class="status {cls}">{e(status)}</span>'

# ── 데이터 가져오기 ────────────────────────────────────────────────────────────

print("📅 일정 DB 가져오는 중...")
schedule_pages = query_db(SCHEDULE_DB, sorts=[{"property": "시작", "direction": "ascending"}])

print("📋 예약 DB 가져오는 중...")
booking_pages = query_db(BOOKING_DB, sorts=[{"property": "날짜/시간", "direction": "ascending"}])

print("🎒 준비물 DB 가져오는 중...")
packing_pages = query_db(PACKING_DB, sorts=[
    {"property": "사람", "direction": "ascending"},
    {"property": "준비물", "direction": "ascending"},
])

# 날짜별 일정 그룹핑
by_date = defaultdict(list)
for page in schedule_pages:
    date_val = get_prop(page, "시작")
    if isinstance(date_val, tuple):
        date_val = date_val[0]
    if date_val:
        by_date[date_val[:10]].append(page)

# 사람별 준비물 그룹핑
by_person = defaultdict(list)
for page in packing_pages:
    person = get_prop(page, "사람") or "공통"
    by_person[person].append(page)

# ── 패널 생성 ─────────────────────────────────────────────────────────────────

DAYS = [
    ("2026-06-20", "6월 20일 (토)", "도착의 날 🛬",          "d620"),
    ("2026-06-21", "6월 21일 (일)", "시모노세키 당일치기 🚢", "d621"),
    ("2026-06-22", "6월 22일 (월)", "",                       "d622"),
    ("2026-06-23", "6월 23일 (화)", "유후인 + 하카타 관광 🌸","d623"),
    ("2026-06-24", "6월 24일 (수)", "",                       "d624"),
    ("2026-06-25", "6월 25일 (목)", "귀국의 날 ✈️",          "d625"),
]

DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]

def build_day_panel(date_str, title_kr, subtitle):
    entries = by_date.get(date_str, [])
    header = (
        f'<div class="day-header"><h2>{e(title_kr)}</h2>'
        + (f'<p>{e(subtitle)}</p>' if subtitle else "")
        + '</div>'
    )

    if not entries:
        return header + '<div class="empty-day">📝 아직 일정이 없어요.</div>'

    tl_html = ""
    for entry in entries:
        entry_title = get_prop(entry, "일정")
        region      = get_prop(entry, "지역")
        memo        = get_prop(entry, "메모")

        print(f"  → 블록 가져오는 중: {entry_title}")
        rows = get_table_rows(entry["id"])

        if not rows:
            tags = [("tag-loc", region)] if region else []
            tl_html += tl_item("", entry_title, memo, tags)
            continue

        if memo.strip():
            tl_html += f'<div class="memo-box"><strong>메모</strong> {e(memo)}</div>'

        for row in rows:
            time = row[0].strip() if len(row) > 0 else ""
            title_parts = [c.strip() for c in row[1:3] if c.strip()]
            item_title  = " — ".join(title_parts) if title_parts else entry_title
            if not item_title.strip():
                continue

            sub_parts = [
                c.strip() for c in row[3:]
                if c.strip() and not c.strip().startswith("http")
            ]
            sub = "\n".join(sub_parts)

            tags = []
            if region:
                tags.append(("tag-loc", region))
            for c in row:
                if "엔" in c and any(ch.isdigit() for ch in c):
                    tags.append(("tag-cost", c.strip()))
                    break

            tl_html += tl_item(time, item_title, sub, tags)

    return header + f'<div class="timeline">{tl_html}</div>'


def build_booking_panel():
    rows_html = ""
    for page in booking_pages:
        item     = get_prop(page, "항목")
        status   = get_prop(page, "상태")
        name     = get_prop(page, "예약명/편명")
        date_val = get_prop(page, "날짜/시간")
        memo     = get_prop(page, "메모")
        cost     = get_prop(page, "비용")

        date_str = ""
        if isinstance(date_val, tuple):
            start, end = date_val
            date_str = start
            if end:
                date_str += f" ~ {end}"

        cost_str = f"₩{int(cost):,}" if cost else ""

        rows_html += f"""
          <tr>
            <td>{e(item)}</td>
            <td>{e(name)}</td>
            <td>{e(date_str)}</td>
            <td>{e(memo)}</td>
            <td>{cost_str}</td>
            <td>{status_badge(status)}</td>
          </tr>"""

    return f"""
    <div class="day-header"><h2>📋 예약 / 기본정보</h2></div>
    <div class="card">
      <h3>📋 예약 목록</h3>
      <table class="res-table">
        <thead><tr><th>항목</th><th>예약명</th><th>날짜</th><th>메모</th><th>비용</th><th>상태</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    <div class="card">
      <h3>💡 기본 정보</h3>
      <table class="res-table">
        <thead><tr><th>항목</th><th>내용</th></tr></thead>
        <tbody>
          <tr><td>여행 기간</td><td>2026년 6월 20일 (토) — 6월 25일 (목) · 5박 6일</td></tr>
          <tr><td>멤버</td><td>효진, 창현</td></tr>
          <tr><td>주 교통</td><td>지하철 · 버스 · 신칸센 (시모노세키 이동 시)</td></tr>
          <tr><td>환전</td><td>엔화 현금 필수 (가라토 이치바, 관문 페리 등)</td></tr>
        </tbody>
      </table>
    </div>"""


def build_packing_panel():
    html = '<div class="day-header"><h2>🎒 준비물 체크리스트</h2></div>'
    icons = {"효진": "👤", "창현": "👤", "공통": "🤝"}

    for person, items in by_person.items():
        icon = icons.get(person, "👤")
        items_html = ""
        for i, page in enumerate(items):
            item_name = get_prop(page, "준비물")
            checked   = get_prop(page, "체크")
            uid = f"pack_{person}_{i}"
            checked_attr = "checked" if checked else ""
            li_cls = "checked" if checked else ""
            items_html += (
                f'<li class="{li_cls}">'
                f'<input type="checkbox" id="{uid}" {checked_attr} onchange="saveCheck(this)">'
                f'<label for="{uid}">{e(item_name)}</label></li>'
            )
        html += f'<div class="card"><h3>{icon} {e(person)}</h3><ul class="pack-list">{items_html}</ul></div>'
    return html


# ── 패널 및 탭 조립 ───────────────────────────────────────────────────────────

tabs_html    = ""
panels_html  = ""

for i, (date_str, title_kr, subtitle, panel_id) in enumerate(DAYS):
    y, m, d = map(int, date_str.split("-"))
    dow = DOW_KR[date(y, m, d).weekday()]
    active = " active" if i == 0 else ""

    tabs_html   += f'<div class="tab{active}" onclick="switchTab(\'{panel_id}\')">{m}/{d} {dow}</div>\n'
    panel_body   = build_day_panel(date_str, title_kr, subtitle)
    panels_html += f'<div class="panel{active}" id="{panel_id}">{panel_body}</div>\n'

tabs_html   += '<div class="tab" onclick="switchTab(\'booking\')">📋 예약정보</div>\n'
tabs_html   += '<div class="tab" onclick="switchTab(\'packing\')">🎒 준비물</div>\n'
panels_html += f'<div class="panel" id="booking">{build_booking_panel()}</div>\n'
panels_html += f'<div class="panel" id="packing">{build_packing_panel()}</div>\n'

updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# ── HTML 출력 ─────────────────────────────────────────────────────────────────

HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🧳 후쿠오카 여행 (6/20–6/25)</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', sans-serif; background: #fdf6f0; color: #1a1a1a; min-height: 100vh; }}
    .hero {{ background: linear-gradient(135deg, #e8603c 0%, #c0392b 60%, #922b21 100%); color: #fff; padding: 2.5rem 2rem 2rem; text-align: center; }}
    .hero h1 {{ font-size: 2rem; font-weight: 700; }}
    .hero p {{ margin-top: 0.4rem; font-size: 0.95rem; opacity: 0.85; }}
    .hero-meta {{ display: flex; justify-content: center; gap: 2rem; margin-top: 1.2rem; flex-wrap: wrap; }}
    .hero-meta span {{ font-size: 0.85rem; background: rgba(255,255,255,0.18); padding: 4px 14px; border-radius: 20px; }}
    .updated {{ font-size: 0.75rem; opacity: 0.6; margin-top: 0.5rem; }}
    .tabs {{ display: flex; overflow-x: auto; background: #fff; border-bottom: 2px solid #f0ebe4; padding: 0 1rem; gap: 2px; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .tab {{ flex-shrink: 0; padding: 0.85rem 1.2rem; font-size: 0.85rem; font-weight: 600; cursor: pointer; color: #888; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.2s; white-space: nowrap; }}
    .tab:hover {{ color: #e8603c; }}
    .tab.active {{ color: #e8603c; border-bottom-color: #e8603c; }}
    .content {{ max-width: 860px; margin: 0 auto; padding: 1.8rem 1rem 4rem; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .day-header {{ margin-bottom: 1.4rem; }}
    .day-header h2 {{ font-size: 1.3rem; font-weight: 700; }}
    .day-header p {{ font-size: 0.85rem; color: #888; margin-top: 3px; }}
    .timeline {{ position: relative; padding-left: 28px; }}
    .timeline::before {{ content: ''; position: absolute; left: 9px; top: 6px; bottom: 0; width: 2px; background: #f0ebe4; }}
    .tl-item {{ position: relative; margin-bottom: 1.4rem; }}
    .tl-dot {{ position: absolute; left: -24px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: #e8603c; border: 2px solid #fff; box-shadow: 0 0 0 2px #e8603c; }}
    .tl-item.minor .tl-dot {{ background: #ddd; box-shadow: 0 0 0 2px #ddd; }}
    .tl-time {{ font-size: 0.78rem; font-weight: 700; color: #e8603c; letter-spacing: 0.5px; margin-bottom: 3px; }}
    .tl-item.minor .tl-time {{ color: #aaa; }}
    .tl-title {{ font-size: 1rem; font-weight: 600; }}
    .tl-sub {{ font-size: 0.85rem; color: #666; margin-top: 4px; line-height: 1.6; }}
    .tl-tags {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }}
    .tag {{ font-size: 0.75rem; padding: 2px 9px; border-radius: 12px; font-weight: 500; }}
    .tag-loc {{ background: #fff3e0; color: #e65100; }}
    .tag-food {{ background: #fce4ec; color: #c62828; }}
    .tag-tip {{ background: #e8f5e9; color: #2e7d32; }}
    .tag-cost {{ background: #e3f2fd; color: #1565c0; }}
    .tag-transport {{ background: #f3e5f5; color: #6a1b9a; }}
    .card {{ background: #fff; border: 1px solid #ede8e0; border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; }}
    .card h3 {{ font-size: 1rem; font-weight: 700; margin-bottom: 0.8rem; }}
    .res-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .res-table th {{ background: #fdf0e8; color: #c0392b; font-weight: 600; padding: 8px 12px; text-align: left; border-bottom: 1px solid #ede8e0; }}
    .res-table td {{ padding: 9px 12px; border-bottom: 1px solid #f5f0ea; vertical-align: middle; }}
    .res-table tr:last-child td {{ border-bottom: none; }}
    .status {{ display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; font-weight: 600; }}
    .status-done {{ background: #d4edda; color: #155724; }}
    .status-paid {{ background: #cce5ff; color: #004085; }}
    .status-todo {{ background: #f8d7da; color: #721c24; }}
    .status-plan {{ background: #fff3cd; color: #856404; }}
    .pack-list {{ list-style: none; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
    .pack-list li {{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: #444; }}
    .pack-list li input[type="checkbox"] {{ accent-color: #e8603c; width: 15px; height: 15px; cursor: pointer; flex-shrink: 0; }}
    .pack-list li.checked label {{ text-decoration: line-through; color: #bbb; }}
    .memo-box {{ background: #fffbf5; border-left: 3px solid #e8603c; border-radius: 0 8px 8px 0; padding: 0.8rem 1rem; font-size: 0.85rem; color: #555; line-height: 1.7; margin-bottom: 1rem; }}
    .memo-box strong {{ color: #e8603c; }}
    .empty-day {{ text-align: center; padding: 3rem 0; color: #ccc; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="hero">
    <h1>🧳 후쿠오카 여행</h1>
    <p>2026년 6월 20일 (토) — 6월 25일 (목) · 5박 6일</p>
    <div class="hero-meta">
      <span>✈️ 인천 → 후쿠오카</span>
      <span>👥 효진 · 창현</span>
      <span>🏨 프레지던트 호텔 + 원스호텔</span>
    </div>
    <p class="updated">마지막 업데이트: {updated_at}</p>
  </div>

  <div class="tabs">
    {tabs_html}
  </div>

  <div class="content">
    {panels_html}
  </div>

  <script>
    function switchTab(id) {{
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      event.currentTarget.classList.add('active');
    }}
    function saveCheck(el) {{
      const state = {{}};
      document.querySelectorAll('input[type="checkbox"]').forEach(cb => {{ state[cb.id] = cb.checked; }});
      localStorage.setItem('fukuoka_pack', JSON.stringify(state));
    }}
    (function loadChecks() {{
      const data = localStorage.getItem('fukuoka_pack');
      if (!data) return;
      const state = JSON.parse(data);
      Object.entries(state).forEach(([id, checked]) => {{
        const el = document.getElementById(id);
        if (el) el.checked = checked;
      }});
    }})();
  </script>
</body>
</html>"""

out_path = os.path.join(os.path.dirname(__file__), "hukuoka_wCH.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"✅ 완료! → {out_path}")
print(f"   마지막 업데이트: {updated_at}")
