from jinja2 import BaseLoader, Environment

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }} — Insight Orchestra Report</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 960px;
           margin: 0 auto; padding: 40px 20px; color: #1a1a1a; }
    h1   { color: #0f3460; border-bottom: 2px solid #e0e0e0; padding-bottom: 12px; }
    h2   { color: #16213e; margin-top: 32px; }
    pre  { background: #1e1e1e; color: #d4d4d4; padding: 16px;
           border-radius: 8px; overflow-x: auto; font-size: 13px; }
    .agent-block { background: #f8f9fa; border-left: 4px solid #0f3460;
                   padding: 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }
    .timestamp   { color: #888; font-size: 12px; }
    .chart       { margin: 24px 0; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p class="timestamp">Generated {{ timestamp }} · Insight Orchestra</p>

  <h2>Agent Analysis</h2>
  {% for agent in agents %}
  <div class="agent-block">
    <strong>{{ agent.emoji }} {{ agent.name }}</strong>
    <p>{{ agent.output }}</p>
  </div>
  {% endfor %}

  <h2>Conversation</h2>
  {% for msg in messages %}
    {% if msg.role == "user" %}
      <p><strong>Q:</strong> {{ msg.content }}</p>
    {% else %}
      <p>{{ msg.content }}</p>
      {% if msg.code %}
      <pre>{{ msg.code }}</pre>
      {% endif %}
    {% endif %}
  {% endfor %}

  <h2>Visualisations</h2>
  {% for chart in charts %}
  <div class="chart" id="chart-{{ loop.index }}"></div>
  <script>
    Plotly.newPlot('chart-{{ loop.index }}',
      {{ chart.data | tojson }},
      {{ chart.layout | tojson }}
    );
  </script>
  {% endfor %}

</body>
</html>
"""


class ExportService:
    def to_html(self, session_data: dict) -> str:
        """Generate self-contained HTML report"""
        env = Environment(loader=BaseLoader())
        template = env.from_string(HTML_TEMPLATE)
        return str(template.render(**session_data))

    def to_markdown(self, session_data: dict) -> str:
        """Generate markdown report for Git storage"""
        lines = [f"# {session_data.get('title', 'Analysis Report')}\n"]
        lines.append(f"*Generated {session_data.get('timestamp', 'Now')} · Insight Orchestra*\n")

        if "agents" in session_data and session_data["agents"]:
            lines.append("## Agent Analysis\n")
            for agent in session_data["agents"]:
                lines.append(
                    f"### {agent.get('emoji', '')} {agent.get('name', 'Agent')}\n{agent.get('output', '')}\n"
                )

        lines.append("## Conversation\n")
        # Ensure we have at least an empty list if this isn't in test data.
        for msg in session_data.get("messages", []):
            if msg.get("role") == "user":
                lines.append(f"**Q:** {msg.get('content', '')}\n")
            else:
                lines.append(f"{msg.get('content', '')}\n")
                if msg.get("code"):
                    lines.append(f"```python\n{msg.get('code', '')}\n```\n")

        return "\n".join(lines)
