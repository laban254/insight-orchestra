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

/**
 * Render a 0–1 score as a percentage, or say it was never assessed.
 * An exported report outlives the session it came from, so an unscored claim must not
 * silently print as "0%" — a reader has no way to tell that apart from a real low score.
 */
const pctLabel = (value: number | null | undefined, label: string, labelFirst = false) => {
    if (value == null || Number.isNaN(value)) return `${esc(label)} not assessed`;
    const pct = Math.round(value * 100);
    return labelFirst ? `${esc(label)} ${pct}%` : `${pct}% ${esc(label)}`;
};

function buildReportHtml(
    datasetName: string,
    analysis: ProcessResponse,
    results: QueryResult[],
    { autoprint }: { autoprint: boolean }
): string {
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

    // Print mode forces a light page (see the @media print block below) —
    // the chart's own title/axis/tick text is drawn by Plotly onto a
    // canvas, not styled by that CSS, so it needs the matching dark-on-light
    // palette here or it stays the light-on-dark color and goes nearly
    // invisible against the white print background.
    const fontColor = autoprint ? "#0b1220" : "#e8eefc";
    const gridColor = autoprint ? "rgba(11,18,32,0.15)" : "rgba(232,238,252,0.08)";

    // Print/PDF mode waits on every chart's render promise before calling
    // window.print() — printing before Plotly has painted produces a PDF
    // with empty chart boxes, since print rasterizes whatever is on screen
    // at that instant.
    const plotCalls = figs
        .map((f) => {
            try {
                const parsed = JSON.parse(f.json);
                const layoutOverrides = {
                    paper_bgcolor: "transparent",
                    plot_bgcolor: "transparent",
                    font: { color: fontColor },
                    colorway: ["#22d3ee", "#e879f9", "#a78bfa", "#34d399", "#fbbf24", "#fb7185"],
                    xaxis: { ...(parsed.layout?.xaxis ?? {}), gridcolor: gridColor, tickfont: { color: fontColor }, titlefont: { color: fontColor } },
                    yaxis: { ...(parsed.layout?.yaxis ?? {}), gridcolor: gridColor, tickfont: { color: fontColor }, titlefont: { color: fontColor } },
                };
                return `Plotly.newPlot(${JSON.stringify(f.id)}, ${JSON.stringify(parsed.data ?? [])}, Object.assign(${JSON.stringify(
                    parsed.layout ?? {}
                )}, ${JSON.stringify(layoutOverrides)}), {responsive:true,displaylogo:false})`;
            } catch {
                return "";
            }
        })
        .filter(Boolean);

    const chartScript = autoprint
        ? `Promise.all([${plotCalls.join(",")}]).then(() => setTimeout(() => window.print(), 150));`
        : `${plotCalls.join(";\n")};`;

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
  .warn{border-color:rgba(251,191,36,.4);background:rgba(251,191,36,.08);color:#fbbf24}
  .top .tag{color:#22d3ee;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em}
  .muted{color:#9aa7c2;font-size:13px}
  .chart{width:100%;height:420px}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
  @media print {
    /* A dark theme wastes ink and most print/PDF pipelines render it
       inconsistently — force a light, paginated layout for print only. */
    :root{color-scheme:light}
    body{background:#fff;color:#0b1220;padding:0}
    .card{background:#fff;border:1px solid #d8dfea;break-inside:avoid;page-break-inside:avoid}
    .top{background:#eefcff;border-color:#22d3ee}
    .warn{background:#fffaeb;border-color:#f5c451;color:#92620a}
    .muted{color:#5c6b85}
    .sub,h2{color:#5c6b85}
    h2{break-after:avoid;page-break-after:avoid}
    .chart{height:340px}
  }
</style></head>
<body><div class="wrap">
  <h1>${esc(datasetName)}</h1>
  <p class="sub">Insight Orchestra report · generated ${new Date().toLocaleString()}</p>

  ${
      analysis.degraded
          ? `<div class="card warn"><strong>Statistics only — not interpreted.</strong><p class="muted" style="margin:6px 0 0">${esc(
                analysis.degraded_reason ?? "No language model was available for this run."
            )}</p></div>`
          : ""
  }

  <div class="card"><p style="margin:0">${esc(analysis.narrative)}</p></div>

  <div class="kpis">
    ${kpis.map(([l, v]) => `<div class="card kpi"><div class="l">${esc(l)}</div><div class="v">${esc(v)}</div></div>`).join("")}
  </div>

  ${
      consensus
          ? `<h2>Top insight</h2><div class="card top">
      <div class="tag">Top insight · ${pctLabel(consensus.confidence, "confidence")}</div>
      <p style="margin:8px 0 0;font-size:15px">${esc(consensus.hypothesis)}</p>
      ${consensus.statistical_argument ? `<p class="muted" style="margin-top:6px">${esc(consensus.statistical_argument)}</p>` : ""}
    </div>`
          : ""
  }

  ${figs.length ? `<h2>Charts</h2>${figs.map((f) => `<div class="card"><div class="muted" style="margin-bottom:8px">${esc(f.title)}</div><div id="${f.id}" class="chart"></div></div>`).join("")}` : ""}

  ${
      others.length
          ? `<h2>Other patterns</h2>${others
                .map((h) => `<div class="card"><p style="margin:0">${esc(h.hypothesis)}</p><p class="muted" style="margin:6px 0 0">${pctLabel(h.confidence, "Confidence", true)} · ${pctLabel(h.business_value, "Value", true)}</p></div>`)
                .join("")}`
          : ""
  }
</div>
<script>${chartScript}</script>
</body></html>`;

    return html;
}

export function exportReport(datasetName: string, analysis: ProcessResponse | null, results: QueryResult[]) {
    if (!analysis) return;
    const html = buildReportHtml(datasetName, analysis, results, { autoprint: false });

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `insight-orchestra-${datasetName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.html`;
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Open the same report in a new tab and trigger the browser's print dialog
 * once charts have rendered — the user picks "Save as PDF" as the
 * destination. No PDF-generation dependency needed: real charts, rasterized
 * by the browser's own engine, print better than most headless-renderer
 * pipelines would.
 */
export function exportReportAsPdf(datasetName: string, analysis: ProcessResponse | null, results: QueryResult[]) {
    if (!analysis) return;
    const html = buildReportHtml(datasetName, analysis, results, { autoprint: true });

    const win = window.open("", "_blank");
    if (!win) return; // popup blocked — nothing we can do without a user gesture retry
    win.document.open();
    win.document.write(html);
    win.document.close();
}
