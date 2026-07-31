from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
INPUT = MODULE_DIR / "data" / "analyzed" / "2026-07" / "articles_analyzed.json"
OUTPUT = MODULE_DIR / "reports" / "2026-07" / "southeast_asia_medtech_monthly_report_offline.html"


def main() -> int:
    articles = json.loads(INPUT.read_text(encoding="utf-8"))
    included = [item for item in articles if item.get("include_in_monthly_report") is True]
    included.sort(
        key=lambda item: (
            item.get("relevance_score", 0),
            item.get("packaging_relevance_score", 0),
            item.get("published_date", ""),
        ),
        reverse=True,
    )
    country_counts = Counter(
        country
        for item in included
        for country in (item.get("report_countries") or ["Regional / Global"])
    )
    payload = json.dumps(included, ensure_ascii=False).replace("</", "<\\/")
    document = TEMPLATE.replace("__ARTICLE_DATA__", payload)
    document = document.replace("__TOTAL__", str(len(included)))
    document = document.replace(
        "__COUNTRY_COUNTS__",
        " · ".join(f"{html.escape(country)} {count}" for country, count in country_counts.items()),
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")
    print(OUTPUT)
    print(f"articles={len(included)} bytes={OUTPUT.stat().st_size}")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>东南亚医疗器械月报｜2026年7月</title>
<style>
:root{--ink:#17231f;--muted:#68726d;--paper:#f6f3ec;--cream:#ece6d9;--line:#d4cec1;--forest:#153c32;--teal:#14746a;--coral:#e36b4f;--white:#fffdf8}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif;line-height:1.6}
a{color:inherit}.wrap{max-width:1180px;margin:auto;padding:68px 30px}.hero{background:linear-gradient(125deg,#102e27,#17483c 65%,#0c2d27);color:var(--white);padding:24px max(30px,calc((100vw - 1120px)/2)) 82px}
nav{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ffffff26;padding-bottom:22px}.brand{font-weight:700}.brand b{display:inline-block;background:var(--coral);padding:6px 10px;margin-right:10px;font-size:12px}.edition{font-size:12px;color:#ffffffa8}
.hero-grid{display:grid;grid-template-columns:1fr 260px;gap:70px;align-items:end;padding-top:75px}.eyebrow,.kicker{font:700 11px ui-monospace,monospace;letter-spacing:.15em;text-transform:uppercase;color:#8dd3c5}.hero h1{font-size:clamp(44px,6vw,76px);line-height:1;letter-spacing:-.05em;margin:18px 0 26px}.hero p{max-width:720px;color:#ffffffb5;font-size:17px}.issue{border-top:4px solid var(--coral);padding-top:20px;display:grid;gap:8px;color:#ffffffa8;font-size:12px}.issue strong{font-size:20px;color:white}
h2{font-size:34px;letter-spacing:-.035em;margin:8px 0}.heading{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:28px}.heading>p{font-size:12px;color:var(--muted);text-align:right}.kicker{color:var(--teal);margin:0}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);background:var(--white)}.metric{padding:24px;border-right:1px solid var(--line)}.metric:last-child{border:0}.metric strong{display:block;font-size:39px;color:var(--forest)}.metric span{font-size:12px;color:var(--muted)}
.summary{display:grid;grid-template-columns:1.4fr .8fr;gap:22px;margin-top:22px}.note{background:var(--cream);padding:38px}.note h2{font-size:30px}.note p{color:#59625e}.coverage{background:var(--white);border:1px solid var(--line);padding:28px}.coverage h3{margin-top:0}.coverage p{font-size:13px;color:var(--muted)}
.signals{background:var(--forest);color:white}.signals .wrap{padding-top:66px}.signals .heading>p{color:#ffffff8f}.signals .kicker{color:#8dd3c5}.signal-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#ffffff2c;border:1px solid #ffffff2c}.signal{background:#174439;padding:25px;min-height:310px;text-decoration:none;display:flex;flex-direction:column}.signal:hover{background:#1b5043}.signal .scores{font:10px ui-monospace,monospace;color:#8dd3c5}.signal h3{font-size:18px;line-height:1.4}.signal p{color:#ffffffa5;font-size:13px}.signal small{margin-top:auto;color:#ffffff77}
.filters{display:grid;grid-template-columns:1fr 1fr 1.3fr;background:white;border:1px solid var(--line);margin:25px 0}.filters label{padding:12px 17px;border-right:1px solid var(--line)}.filters label:last-child{border:0}.filters span{display:block;font-size:9px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase}.filters select,.filters input{width:100%;border:0;outline:0;background:transparent;padding-top:5px}
.article{display:grid;grid-template-columns:70px 1fr;gap:22px;border-top:1px solid var(--line);padding:25px 4px}.date{border-right:1px solid var(--line)}.date strong{font-size:29px;display:block;line-height:1}.date span{font:10px ui-monospace,monospace;color:var(--coral)}.meta{display:flex;gap:6px;flex-wrap:wrap}.meta span{background:#e7e1d6;padding:3px 7px;font-size:10px}.meta .pack{background:#d6ebe5;color:#17685d}.article h3{font-size:18px;line-height:1.4;margin:9px 0}.article p{color:var(--muted);margin:0}.foot{display:flex;justify-content:space-between;gap:20px;margin-top:13px;font-size:11px;color:#8a918d}.foot a{color:var(--teal);text-decoration:none;font-weight:700}.empty{text-align:center;padding:50px;color:var(--muted)}
footer{background:#0e2923;color:#ffffff8a;padding:34px max(30px,calc((100vw - 1120px)/2));font-size:12px}.offline{background:#fff4db;border:1px solid #e0c98f;padding:12px 16px;margin:0 0 25px;font-size:12px;color:#725421}
@media(max-width:800px){.hero-grid,.summary{grid-template-columns:1fr}.signal-grid{grid-template-columns:1fr 1fr}.metrics{grid-template-columns:1fr 1fr}.filters{grid-template-columns:1fr}.filters label{border-right:0;border-bottom:1px solid var(--line)}}@media(max-width:520px){.wrap{padding:50px 17px}.hero{padding-left:17px;padding-right:17px}.signal-grid{grid-template-columns:1fr}.article{grid-template-columns:50px 1fr}.foot{flex-direction:column}}
@media print{.filters,.offline{display:none}.hero{padding-bottom:45px}.article,.signal{break-inside:avoid}}
</style>
</head>
<body>
<header class="hero">
<nav><div class="brand"><b>SEA</b>MedTech Intelligence</div><div class="edition">OFFLINE EDITION · JULY 2026</div></nav>
<div class="hero-grid"><div><div class="eyebrow">WEBSITE MONITORING · JULY 01–24</div><h1>Southeast Asia<br>Medical Device<br>Monthly Report</h1><p>面向医疗包装业务的东南亚医疗器械情报，覆盖监管审批、政府采购、产能扩张、商业合作及无菌包装信号。</p></div><div class="issue"><span>CURRENT EDITION</span><strong>2026年7月</strong><span>DeepSeek analyzed</span><span>63 source-linked reports</span></div></div>
</header>
<main>
<section class="wrap"><div class="offline">✓ 这是可离线打开的单文件报告。筛选、搜索和正文无需联网；只有点击“官方原文”时需要网络连接。</div>
<div class="heading"><div><p class="kicker">REPORT AT A GLANCE</p><h2>本月情报概览</h2></div><p>July-to-date · 数据截至2026-07-24</p></div>
<div class="metrics"><div class="metric"><strong>501</strong><span>成功抓取文章</span></div><div class="metric"><strong>449</strong><span>DeepSeek分析完成</span></div><div class="metric"><strong>__TOTAL__</strong><span>纳入本期报告</span></div><div class="metric"><strong id="packCount">—</strong><span>包装相关性3–5分</span></div></div>
<div class="summary"><article class="note"><p class="kicker">EXECUTIVE VIEW</p><h2>采购信息显著增加，机会价值需要分层判断。</h2><p>本期数据以菲律宾政府医疗采购为主。分析严格区分招标邀请与正式中标，普通设备采购不会因为来自官方平台就自动成为高价值事件。包装侧重点关注无菌耗材、灭菌兼容性、无菌屏障与ISO 11607等可验证信号。</p></article><aside class="coverage"><h3>国家覆盖</h3><p>__COUNTRY_COUNTS__</p><p>没有抓取到内容不等于该市场没有事件；部分政府平台仍存在访问限制。</p></aside></div>
</section>
<section class="signals"><div class="wrap"><div class="heading"><div><p class="kicker">PRIORITY SIGNALS</p><h2>医疗器械包装机会</h2></div><p>按包装相关性与行业重要性排序</p></div><div class="signal-grid" id="signals"></div></div></section>
<section class="wrap"><div class="heading"><div><p class="kicker">NEWS BY COUNTRY</p><h2>按国家浏览新闻</h2></div><p><span id="shown">0</span> articles shown</p></div>
<div class="filters"><label><span>国家/地区</span><select id="country"></select></label><label><span>类别</span><select id="category"></select></label><label><span>搜索</span><input id="search" placeholder="公司、产品、关键词…"></label></div><div id="articles"></div></section>
</main>
<footer><strong>SEA MedTech Intelligence</strong> · Website-source monitoring · AI-assisted analysis · 请以所链接官方原文作为商业决策依据</footer>
<script>
const DATA=__ARTICLE_DATA__;
const countryCN={Singapore:"新加坡",Malaysia:"马来西亚",Thailand:"泰国",Indonesia:"印度尼西亚",Vietnam:"越南",Philippines:"菲律宾","Regional / Global":"区域/全球"};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const countries=["全部国家",...new Set(DATA.flatMap(a=>a.report_countries.length?a.report_countries:["Regional / Global"]))];
const categories=["全部类别",...new Set(DATA.map(a=>a.primary_category))];
country.innerHTML=countries.map(x=>`<option value="${esc(x)}">${esc(countryCN[x]||x)}</option>`).join("");
category.innerHTML=categories.map(x=>`<option>${esc(x)}</option>`).join("");
packCount.textContent=DATA.filter(a=>a.packaging_relevance_score>=3).length;
const sorted=[...DATA].sort((a,b)=>b.packaging_relevance_score-a.packaging_relevance_score||b.relevance_score-a.relevance_score);
signals.innerHTML=sorted.slice(0,6).map(a=>`<a class="signal" href="${esc(a.url)}" target="_blank"><div class="scores">PACKAGING ${a.packaging_relevance_score}/5 · RELEVANCE ${a.relevance_score}/20</div><h3>${esc(a.title)}</h3><p>${esc(a.packaging_relevance_reason||a.one_sentence_takeaway)}</p><small>${esc(a.source_name)} · ${esc(a.published_date)}</small></a>`).join("");
function render(){const q=search.value.trim().toLowerCase(),c=country.value,k=category.value;const rows=DATA.filter(a=>c==="全部国家"||(a.report_countries.length?a.report_countries:["Regional / Global"]).includes(c)).filter(a=>k==="全部类别"||a.primary_category===k).filter(a=>!q||`${a.title} ${a.summary_cn} ${a.source_name}`.toLowerCase().includes(q)).sort((a,b)=>b.relevance_score-a.relevance_score||b.packaging_relevance_score-a.packaging_relevance_score||b.published_date.localeCompare(a.published_date));shown.textContent=rows.length;articles.innerHTML=rows.length?rows.map(a=>`<article class="article"><div class="date"><strong>${esc(a.published_date.slice(8,10))}</strong><span>JUL</span></div><div><div class="meta"><span>${esc((a.report_countries.length?a.report_countries:["Regional / Global"]).map(x=>countryCN[x]||x).join(" / "))}</span><span>${esc(a.primary_category)}</span><span>R ${a.relevance_score}/20</span>${a.packaging_relevance_score?`<span class="pack">P ${a.packaging_relevance_score}/5</span>`:""}</div><h3>${esc(a.title)}</h3><p>${esc(a.one_sentence_takeaway||a.summary_cn)}</p><div class="foot"><span>${esc(a.organization||a.source_name)}</span><a href="${esc(a.url)}" target="_blank">查看官方原文 ↗</a></div></div></article>`).join(""):'<div class="empty">当前筛选条件下没有重要更新。</div>'}
country.onchange=category.onchange=render;search.oninput=render;render();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
