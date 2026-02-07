"""
Pytest configuration and fixtures for Insight Orchestra tests.
"""

import pytest
import pandas as pd
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'age': [25, 30, 35, 28],
        'department': ['Engineering', 'Sales', 'Engineering', 'Marketing'],
        'salary': [75000, 65000, 85000, 70000],
    })


@pytest.fixture
def sample_csv_path(tmp_path):
    """Create a temporary CSV file for testing."""
    csv_content = """name,age,department,salary
Alice,25,Engineering,75000
Bob,30,Sales,65000
Charlie,35,Engineering,85000
Diana,28,Marketing,70000
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "reasoning": "The user wants to calculate the mean age.",
        "code": "result = df['age'].mean()",
        "needs_clarification": False,
        "clarification_question": None,
    }


@pytest.fixture
def mock_safe_code():
    """Sample safe code for sandbox testing."""
    return """
# Calculate mean of age column
result = df['age'].mean()

# Create a simple calculation
total_salary = df['salary'].sum()
avg_salary = df['salary'].mean()
result = {'mean_age': mean_age, 'total_salary': total_salary}
"""


@pytest.fixture
def mock_unsafe_code():
    """Sample unsafe code for sandbox testing."""
    return """
import os
result = os.system('ls')
"""


@pytest.fixture
def mock_plotly_code():
    """Sample code that generates a Plotly chart."""
    return """
import plotly.express as px
fig = px.bar(df, x='department', y='salary', title='Salary by Department')
result = {'chart': 'bar', 'fig': fig}
"""
