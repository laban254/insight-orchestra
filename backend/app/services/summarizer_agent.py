# Insight Summarizer Agent
class InsightSummarizerAgent:
    def run(self, workflow_results):
        # Extract some key points from the workflow results
        cleaner = workflow_results.get('cleaner', {})
        hypothesis = workflow_results.get('hypothesis', {})
        debate = workflow_results.get('debate', {})
        viz = workflow_results.get('viz', {})
        summary = []
        if cleaner:
            report = cleaner.get('report', {})
            summary.append(f"Data cleaning: {report.get('duplicates_removed', 0)} duplicates removed, {report.get('total_missing', 0)} missing values handled.")
        if hypothesis:
            hyps = hypothesis.get('hypotheses', [])
            summary.append(f"Generated {len(hyps)} hypotheses for analysis.")
        if debate:
            consensus = debate.get('summary', {}).get('consensus', {})
            if consensus:
                summary.append(f"Consensus hypothesis: '{consensus.get('hypothesis', '')}' with confidence {consensus.get('confidence', 0):.2f}.")
        if viz:
            chart_info = viz.get('chart_info', {})
            if chart_info.get('success'):
                summary.append(f"{len(chart_info.get('plots', []))} visualizations generated.")
        if not summary:
            summary = ["No insights available."]
        return {"summary": "\n".join(summary)}
