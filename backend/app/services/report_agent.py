import tempfile
import os

# Automated Report Generator Agent
class ReportGeneratorAgent:
    def run(self, workflow_results):
        # Simple HTML report for demo
        html = "<h1>Insight Orchestra Report</h1>"
        html += "<h2>Summary</h2>"
        summary = workflow_results.get('audit_table', '')
        html += f"<pre>{summary}</pre>"
        html += "<h2>Hypotheses</h2>"
        hyps = workflow_results.get('hypothesis', {}).get('hypotheses', [])
        html += "<ul>" + "".join(f"<li>{h}</li>" for h in hyps) + "</ul>"
        html += "<h2>Visualizations</h2>"
        viz = workflow_results.get('viz', {}).get('chart_info', {}).get('plots', [])
        for plot in viz:
            html += f"<h3>{plot.get('title', plot.get('type', 'Chart'))}</h3>"
        # Save to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', dir='/tmp') as f:
            f.write(html)
            url = f"/static/{os.path.basename(f.name)}"
        return {"report_url": url, "message": "Report generated."}
