"""
Demo datasets for testing Insight Orchestra.
Multiple pre-configured datasets with different characteristics.
"""
import pandas as pd
import numpy as np


def get_sales_demo() -> pd.DataFrame:
    """Sales dataset - time series with regions and products."""
    np.random.seed(42)
    n = 1000
    
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n, freq="D"),
        "region": np.random.choice(["North", "South", "East", "West"], n),
        "product": np.random.choice(["Widget A", "Widget B", "Gadget X", "Gadget Y"], n),
        "sales_rep": np.random.choice([f"Rep_{i}" for i in range(1, 21)], n),
        "quantity": np.random.randint(1, 50, n),
        "unit_price": np.random.uniform(10, 500, n).round(2),
        "customer_satisfaction": np.random.choice([1, 2, 3, 4, 5], n, p=[0.05, 0.10, 0.20, 0.40, 0.25]),
    })
    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["cost"] = (df["revenue"] * np.random.uniform(0.4, 0.7, n)).round(2)
    return df


def get_employee_demo() -> pd.DataFrame:
    """Employee dataset - HR analytics with departments and performance."""
    np.random.seed(42)
    n = 500
    
    return pd.DataFrame({
        "employee_id": range(1, n + 1),
        "name": [f"Employee_{i}" for i in range(1, n + 1)],
        "department": np.random.choice(["Engineering", "Sales", "Marketing", "HR", "Finance"], n),
        "salary": np.random.randint(40000, 150000, n),
        "hire_date": pd.date_range("2015-01-01", periods=n, freq="D"),
        "performance_score": np.random.uniform(1, 5, n).round(2),
        "years_tenure": np.random.randint(0, 10, n),
        "promotion_eligible": np.random.choice([True, False], n, p=[0.3, 0.7]),
        "remote_friendly": np.random.choice([True, False], n, p=[0.6, 0.4]),
    })


def get_customer_demo() -> pd.DataFrame:
    """Customer dataset - e-commerce with purchases and churn."""
    np.random.seed(42)
    n = 800
    
    return pd.DataFrame({
        "customer_id": range(1, n + 1),
        "signup_date": pd.date_range("2021-01-01", periods=n, freq="H"),
        "country": np.random.choice(["USA", "UK", "Canada", "Australia", "Germany"], n),
        "lifetime_value": np.random.exponential(500, n).round(2),
        "total_purchases": np.random.randint(1, 50, n),
        "avg_order_value": np.random.uniform(20, 500, n).round(2),
        "last_purchase_days_ago": np.random.randint(0, 365, n),
        "customer_segment": np.random.choice(["Premium", "Standard", "Budget"], n, p=[0.2, 0.5, 0.3]),
        "churn_risk": np.random.choice([True, False], n, p=[0.15, 0.85]),
    })


def get_weather_demo() -> pd.DataFrame:
    """Weather dataset - time series with multiple metrics."""
    np.random.seed(42)
    n = 365
    
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "city": np.random.choice(["New York", "London", "Tokyo", "Sydney"], n),
        "temperature_celsius": np.random.uniform(-10, 35, n).round(1),
        "humidity_percent": np.random.uniform(30, 90, n).round(1),
        "precipitation_mm": np.random.exponential(5, n).round(1),
        "wind_speed_kmh": np.random.uniform(0, 40, n).round(1),
        "pressure_hpa": np.random.uniform(1000, 1030, n).round(1),
        "cloud_cover_percent": np.random.randint(0, 100, n),
    })


def get_movie_demo() -> pd.DataFrame:
    """Movie dataset - entertainment with ratings and reviews."""
    np.random.seed(42)
    n = 600
    
    return pd.DataFrame({
        "movie_id": range(1, n + 1),
        "title": [f"Movie_{i}" for i in range(1, n + 1)],
        "release_year": np.random.randint(1995, 2024, n),
        "genre": np.random.choice(["Action", "Drama", "Comedy", "Thriller", "Sci-Fi", "Animation"], n),
        "runtime_minutes": np.random.randint(80, 180, n),
        "imdb_rating": np.random.uniform(1, 9, n).round(1),
        "imdb_votes": np.random.randint(100, 500000, n),
        "budget_million": np.random.exponential(50, n).round(1),
        "box_office_million": np.random.exponential(100, n).round(1),
        "director": [f"Director_{i}" for i in range(1, n + 1)],
    })


DEMO_DATASETS = {
    "sales": {
        "name": "📊 Sales Analytics",
        "description": "1000 rows of daily sales data with regions and products",
        "rows": 1000,
        "columns": 8,
        "use_cases": ["Time series", "Regional analysis", "Product performance"],
        "loader": get_sales_demo,
    },
    "employees": {
        "name": "👥 Employee HR Data",
        "description": "500 employees with departments, salaries, and performance",
        "rows": 500,
        "columns": 9,
        "use_cases": ["HR analytics", "Salary analysis", "Promotion eligibility"],
        "loader": get_employee_demo,
    },
    "customers": {
        "name": "🛍️ Customer E-Commerce",
        "description": "800 customers with purchase history and churn prediction",
        "rows": 800,
        "columns": 9,
        "use_cases": ["Customer segmentation", "Churn prediction", "LTV analysis"],
        "loader": get_customer_demo,
    },
    "weather": {
        "name": "🌤️ Weather Time Series",
        "description": "365 days of weather data across 4 cities",
        "rows": 365,
        "columns": 8,
        "use_cases": ["Time series analysis", "Seasonal patterns", "Clustering"],
        "loader": get_weather_demo,
    },
    "movies": {
        "name": "🎬 Movie Database",
        "description": "600 movies with ratings, budgets, and box office",
        "rows": 600,
        "columns": 10,
        "use_cases": ["Regression analysis", "Genre comparison", "ROI analysis"],
        "loader": get_movie_demo,
    },
}


def get_demo_dataset(dataset_name: str = "sales") -> tuple:
    """
    Get a demo dataset by name.
    
    Args:
        dataset_name: Key from DEMO_DATASETS ("sales", "employees", "customers", "weather", "movies")
        
    Returns:
        (DataFrame, metadata dict)
    """
    if dataset_name not in DEMO_DATASETS:
        dataset_name = "sales"
    
    config = DEMO_DATASETS[dataset_name]
    df = config["loader"]()
    
    metadata = {
        "name": config["name"],
        "description": config["description"],
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "use_cases": config["use_cases"],
        "dataset_id": dataset_name,
    }
    
    return df, metadata
