# Explainability Agent
class ExplainabilityAgent:
    def run(self, plot):
        title = plot.get('title', 'Untitled')
        ptype = plot.get('type', 'chart').capitalize()
        x = plot.get('x', None)
        y = plot.get('y', None)
        if ptype == 'Scatter' and x and y:
            explanation = f"This scatter plot shows the relationship between '{x}' and '{y}'. Look for patterns, clusters, or outliers."
        elif ptype == 'Histogram' and x:
            explanation = f"This histogram shows the distribution of '{x}'. Peaks indicate common values, while tails show rare values."
        elif ptype == 'Box' and x and y:
            explanation = f"This box plot compares the distribution of '{y}' across categories of '{x}'. It highlights medians, quartiles, and outliers."
        elif ptype == 'Bar' and x:
            explanation = f"This bar plot shows the frequency or value of '{x}' across categories."
        else:
            explanation = f"This {ptype.lower()} plot titled '{title}' visualizes your data."
        return {"explanation": explanation}
