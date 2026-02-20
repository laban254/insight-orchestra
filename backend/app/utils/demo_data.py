import pandas as pd
import numpy as np

def get_demo_dataset() -> pd.DataFrame:
    """
    Sales dataset — realistic enough to produce
    interesting analysis without being boring.
    ~1000 rows, covers all common analysis patterns.
    """
    np.random.seed(42)
    n = 1000

    return pd.DataFrame({
        "date":       pd.date_range("2023-01-01", periods=n, freq="D"),
        "region":     np.random.choice(["North", "South", "East", "West"], n),
        "product":    np.random.choice(["Widget A", "Widget B", "Gadget X", "Gadget Y"], n),
        "sales_rep":  np.random.choice([f"Rep_{i}" for i in range(1, 21)], n),
        "quantity":   np.random.randint(1, 50, n),
        "unit_price": np.random.uniform(10, 500, n).round(2),
        "revenue":    lambda df: (df["quantity"] * df["unit_price"]).round(2),
        "cost":       lambda df: (df["revenue"] * np.random.uniform(0.4, 0.7, n)).round(2),
        "customer_satisfaction": np.random.choice([1, 2, 3, 4, 5], n,
                                  p=[0.05, 0.10, 0.20, 0.40, 0.25]),
    })
