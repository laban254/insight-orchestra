"""
Unit tests for the demo dataset generators.

Regression coverage for a real bug: get_customer_demo() used the deprecated
pandas frequency alias "H" (hourly), which pandas removed in favor of "h" —
loading the "customers" demo dataset raised ValueError("Invalid frequency:
H...") at generation time, a 400 from GET /demo/load?dataset_id=customers.
"""

import pandas as pd
import pytest
from app.utils.demo_data import DEMO_DATASETS, get_demo_dataset


class TestDemoDatasets:
    @pytest.mark.parametrize("dataset_id", list(DEMO_DATASETS.keys()))
    def test_every_demo_dataset_loads(self, dataset_id):
        df, metadata = get_demo_dataset(dataset_id)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert metadata["dataset_id"] == dataset_id

    def test_customer_demo_signup_date_is_valid_datetime(self):
        """The specific column that broke: freq='H' vs freq='h'."""
        df, _ = get_demo_dataset("customers")
        assert pd.api.types.is_datetime64_any_dtype(df["signup_date"])
