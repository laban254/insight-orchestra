import pandas as pd

# Natural Language Query Agent
class NaturalLanguageQueryAgent:
    def run(self, df, question):
        # Simple demo: answer some common questions
        q = question.lower()
        if "missing" in q or "null" in q:
            missing = df.isnull().sum().sum()
            return {"answer": f"There are {missing} missing values in your data."}
        if "row" in q and ("count" in q or "many" in q or "number" in q):
            return {"answer": f"Your data has {len(df)} rows."}
        if "column" in q and ("count" in q or "many" in q or "number" in q):
            return {"answer": f"Your data has {len(df.columns)} columns."}
        if "unique" in q:
            col = None
            for c in df.columns:
                if c.lower() in q:
                    col = c
                    break
            if col:
                uniq = df[col].nunique()
                return {"answer": f"Column '{col}' has {uniq} unique values."}
        # Fallback
        return {"answer": f"(Demo) I received your question: '{question}'. This would be answered by an LLM or rules."}
