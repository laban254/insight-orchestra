/**
 * Build a self-contained HTML report (interactive charts via the Plotly CDN)
 * from the current analysis + query results, and trigger a download.
 */

import type { ProcessResponse } from "./types";
import type { QueryResult } from "@/components/workspace/CanvasPane";

const esc = (s: unknown) =>
    String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

export function exportReport(datasetName: string, analysis: ProcessResponse | null, results: QueryResult[]) {
    if (!analysis) return;

    const report = analysis.cleaner.report;
    const consensus = analysis.debate.summary.consensus;
    const others = analysis.debate.scored_hypotheses
        .filter((h) => h.hypothesis !== consensus?.hypothesis)
        .slice(0, 6);

    type Fig = { id: string; title: string; json: string };
    const figs: Fig[] = [];
    analysis.viz.chart_info.plots.forEach((p, i) => figs.push({ id: `fig-a-${i}`, title: p.title || `Chart ${i + 1}`, json: p.plotly_json }));
    results.forEach((r, i) => figs.push({ id: `fig-r-${i}`, title: r.question, json: r.plotJson }));

    const kpis = [
        ["Rows", report.final_shape[0].toLocaleString()],
        ["Columns", String(report.final_shape[1])],
        ["Duplicates removed", report.duplicates_removed.toLocaleString()],
        ["Missing fixed", report.total_missing.toLocaleString()],
    ];

    const chartScript = figs
        .map((f) => {
            try {
                const parsed = JSON.parse(f.json);
                return `Plotly.newPlot(${JSON.stringify(f.id)}, ${JSON.stringify(parsed.data ?? [])}, Object.assign(${JSON.stringify(
                    parsed.layout ?? {}
                )}, {paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e8eefc'},colorway:['#22d3ee','#e879f9','#a78bfa','#34d399','#fbbf24','#fb7185']}), {responsive:true,displaylogo:false});`;
            } catch {
                return "";
            }
        })
        .join("\n");

    const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Insight Orchestra — ${esc(datasetName)}</title>
<script src="https://cdn.plot.ly/plotly-2.29.1.min.js"></script>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:#070b14;color:#e8eefc;font:14px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:40px}
  .wrap{max-width:960px;margin:0 auto}
  h1{font-size:24px;margin:0 0 4px} .sub{color:#9aa7c2;margin:0 0 28px;font-size:13px}
  h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#5e6c89;margin:32px 0 12px}
  .card{background:#0f1626;border:1px solid #25314c;border-radius:14px;padding:18px;margin-bottom:14px}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  .kpi .v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
  .kpi .l{font-size:11px;color:#9aa7c2;text-transform:uppercase;letter-spacing:.05em}
  .top{border-color:rgba(34,211,238,.3);background:rgba(34,211,238,.06)}
  .top .tag{color:#22d3ee;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em}
  .muted{color:#9aa7c2;font-size:13px}
  .chart{width:100%;height:420px}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
</style></head>
<body><div class="wrap">
  <h1>${esc(datasetName)}</h1>
  <p class="sub">Insight Orchestra report · generated ${new Date().toLocaleString()}</p>

  <div class="card"><p style="margin:0">${esc(analysis.narrative)}</p></div>

  <div class="kpis">
    ${kpis.map(([l, v]) => `<div class="card kpi"><div class="l">${esc(l)}</div><div class="v">${esc(v)}</div></div>`).join("")}
  </div>

  ${
      consensus
          ? `<h2>Top insight</h2><div class="card top">
      <div class="tag">Top insight · ${Math.round(consensus.confidence * 100)}% confidence</div>
      <p style="margin:8px 0 0;font-size:15px">${esc(consensus.hypothesis)}</p>
      ${consensus.statistical_argument ? `<p class="muted" style="margin-top:6px">${esc(consensus.statistical_argument)}</p>` : ""}
    </div>`
          : ""
  }

  ${figs.length ? `<h2>Charts</h2>${figs.map((f) => `<div class="card"><div class="muted" style="margin-bottom:8px">${esc(f.title)}</div><div id="${f.id}" class="chart"></div></div>`).join("")}` : ""}

  ${
      others.length
          ? `<h2>Other patterns</h2>${others
                .map((h) => `<div class="card"><p style="margin:0">${esc(h.hypothesis)}</p><p class="muted" style="margin:6px 0 0">Confidence ${Math.round(h.confidence * 100)}% · Value ${Math.round(h.business_value * 100)}%</p></div>`)
                .join("")}`
          : ""
  }
</div>
<script>${chartScript}</script>
</body></html>`;

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `insight-orchestra-${datasetName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.html`;
    a.click();
    URL.revokeObjectURL(url);
}
