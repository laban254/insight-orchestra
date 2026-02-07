"""
Unit tests for ADK Agents.
"""

import pytest
import pandas as pd
from app.services.adk_agents import (
    DataJanitorAgent,
    HypothesisBotAgent,
    DebateManagerAgent,
    VizWhizAgent,
    InsightOrchestraWorkflow,
)


class TestDataJanitorAgent:
    """Test cases for DataJanitorAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a DataJanitorAgent instance."""
        return DataJanitorAgent(name="DataJanitorAgent")
    
    @pytest.fixture
    def dirty_data(self):
        """Create a DataFrame with various issues."""
        return pd.DataFrame({
            'name': ['Alice', 'Bob', 'Alice', None, 'Eve'],
            'age': [25, 30, 25, 28, None],
            'department': ['Sales', 'Sales', 'Sales', 'Sales', 'Engineering'],
            'constant': ['x', 'x', 'x', 'x', 'x'],  # Constant column
        })
    
    def test_detect_duplicates(self, agent, dirty_data):
        """Test duplicate detection."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        assert 'duplicates_found' in result['report']
        assert result['report']['duplicates_found'] == 1  # One duplicate row
    
    def test_remove_duplicates(self, agent, dirty_data):
        """Test duplicate removal."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        assert result['report']['duplicates_removed'] == 1
    
    def test_detect_missing_values(self, agent, dirty_data):
        """Test missing value detection."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        missing = result['report']['missing_values']
        assert 'name' in missing
        assert 'age' in missing
        assert missing['name'] == 1  # One null name
        assert missing['age'] == 1   # One null age
    
    def test_impute_numeric_missing(self, agent, dirty_data):
        """Test numeric missing value imputation."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        # Age should be imputed with mean (28)
        cleaned_df = pd.DataFrame(result['cleaned_data'])
        assert cleaned_df['age'].isnull().sum() == 0
    
    def test_impute_categorical_missing(self, agent, dirty_data):
        """Test categorical missing value imputation."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        # Name should be imputed with mode (Alice)
        cleaned_df = pd.DataFrame(result['cleaned_data'])
        assert cleaned_df['name'].isnull().sum() == 0
    
    def test_detect_constant_columns(self, agent, dirty_data):
        """Test constant column detection."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        assert 'constant' in result['report']['constant_columns']
    
    def test_bias_flags(self, agent):
        """Test bias flag generation for high missing rates."""
        data = pd.DataFrame({
            'id': list(range(100)),
            'mostly_missing': [None] * 40 + list(range(60)),
        })
        
        result = agent.run(data.to_dict(orient='records'))
        
        assert 'bias_flags' in result['report']
        assert any('mostly_missing' in flag for flag in result['report']['bias_flags'])
    
    def test_final_shape_report(self, agent, dirty_data):
        """Test that final shape is reported."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        assert 'final_shape' in result['report']
        assert len(result['report']['final_shape']) == 2
    
    def test_improved_missing_values_imputed_flag(self, agent, dirty_data):
        """Test that missing_values_imputed flag is set."""
        result = agent.run(dirty_data.to_dict(orient='records'))
        
        assert result['report']['missing_values_imputed'] is True


class TestHypothesisBotAgent:
    """Test cases for HypothesisBotAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a HypothesisBotAgent instance."""
        return HypothesisBotAgent(name="HypothesisBotAgent")
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data with numeric and categorical columns."""
        return pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'salary': [50000, 60000, 70000, 80000, 90000],
            'department': ['Sales', 'Engineering', 'Sales', 'Engineering', 'HR'],
            'city': ['NYC', 'LA', 'NYC', 'LA', 'Chicago'],
        })
    
    def test_generate_hypotheses(self, agent, sample_data):
        """Test hypothesis generation."""
        result = agent.run(sample_data.to_dict(orient='records'))
        
        assert 'hypotheses' in result
        assert len(result['hypotheses']) > 0
        assert 'summary' in result
    
    def test_skip_index_columns(self, agent):
        """Test that index-like columns are skipped."""
        data = pd.DataFrame({
            'PassengerId': [1, 2, 3],
            'Index': [1, 2, 3],
            'ID': [1, 2, 3],
            'id': [1, 2, 3],
            'age': [25, 30, 35],
        })
        
        result = agent.run(data.to_dict(orient='records'))
        hypotheses_text = ' '.join(result['hypotheses'])
        
        # Should not contain PassengerId, Index, ID, id in hypotheses
        assert 'PassengerId' not in hypotheses_text
        assert 'Index' not in hypotheses_text
        assert 'ID' not in hypotheses_text
    
    def test_numeric_correlation_hypotheses(self, agent, sample_data):
        """Test generation of correlation hypotheses."""
        result = agent.run(sample_data.to_dict(orient='records'))
        hypotheses_text = ' '.join(result['hypotheses'])
        
        # Should generate hypotheses about age and salary
        assert 'age' in hypotheses_text.lower()
        assert 'salary' in hypotheses_text.lower()
    
    def test_categorical_group_hypotheses(self, agent, sample_data):
        """Test generation of group-by hypotheses."""
        result = agent.run(sample_data.to_dict(orient='records'))
        hypotheses_text = ' '.join(result['hypotheses'])
        
        # Should generate hypotheses about department groups
        assert 'department' in hypotheses_text.lower()
    
    def test_summary_contains_column_info(self, agent, sample_data):
        """Test that summary contains column information."""
        result = agent.run(sample_data.to_dict(orient='records'))
        
        summary = result['summary']
        assert 'numeric_columns' in summary
        assert 'categorical_columns' in summary
        assert 'age' in summary['numeric_columns']
        assert 'salary' in summary['numeric_columns']
        assert 'department' in summary['categorical_columns']
    
    def test_max_hypotheses_limit(self, agent):
        """Test that hypotheses are limited to 10."""
        data = pd.DataFrame({
            f'col_{i}': list(range(10)) for i in range(10)
        })
        
        result = agent.run(data.to_dict(orient='records'))
        
        assert len(result['hypotheses']) <= 10
    
    def test_duplicate_hypotheses_removed(self, agent):
        """Test that duplicate hypotheses are removed."""
        data = pd.DataFrame({
            'age': [25, 30, 35],
            'salary': [50000, 60000, 70000],
            'dept': ['Sales', 'Engineering', 'HR'],
        })
        
        result = agent.run(data.to_dict(orient='records'))
        hypotheses = result['hypotheses']
        
        # Check for unique hypotheses
        assert len(hypotheses) == len(set(hypotheses))


class TestDebateManagerAgent:
    """Test cases for DebateManagerAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a DebateManagerAgent instance."""
        return DebateManagerAgent(name="DebateManagerAgent")
    
    def test_score_hypotheses(self, agent):
        """Test hypothesis scoring."""
        hypotheses = [
            "Does age correlate with salary?",
            "Is there a difference between departments?",
        ]
        
        result = agent.run(hypotheses)
        
        assert 'scored_hypotheses' in result
        assert 'summary' in result
        assert len(result['scored_hypotheses']) == len(hypotheses)
    
    def test_confidence_and_business_value(self, agent):
        """Test that confidence and business value are assigned."""
        hypotheses = ["Test hypothesis"]
        
        result = agent.run(hypotheses)
        
        scored = result['scored_hypotheses'][0]
        assert 'confidence' in scored
        assert 'business_value' in scored
        assert 0 <= scored['confidence'] <= 1
        assert 0 <= scored['business_value'] <= 1
    
    def test_sorted_by_combined_score(self, agent):
        """Test that hypotheses are sorted by combined score."""
        hypotheses = ["H1", "H2", "H3"]
        
        result = agent.run(hypotheses)
        scored = result['scored_hypotheses']
        
        # Should be sorted descending by confidence * business_value
        scores = [s['confidence'] * s['business_value'] for s in scored]
        assert scores == sorted(scores, reverse=True)
    
    def test_consensus_identified(self, agent):
        """Test that consensus hypothesis is identified."""
        hypotheses = ["Test hypothesis"]
        
        result = agent.run(hypotheses)
        
        assert result['summary']['consensus'] is not None
        assert result['summary']['consensus']['hypothesis'] == "Test hypothesis"
    
    def test_arguments_generated(self, agent):
        """Test that statistical and business arguments are generated."""
        hypotheses = ["Test hypothesis"]
        
        result = agent.run(hypotheses)
        
        assert 'arguments' in result['summary']
        assert len(result['summary']['arguments']) == 1
        
        arg = result['summary']['arguments'][0]
        assert 'hypothesis' in arg
        assert 'statistical' in arg
        assert 'business' in arg
    
    def test_empty_hypotheses(self, agent):
        """Test handling of empty hypotheses list."""
        result = agent.run([])
        
        assert result['scored_hypotheses'] == []
        assert result['summary']['consensus'] is None


class TestVizWhizAgent:
    """Test cases for VizWhizAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a VizWhizAgent instance."""
        return VizWhizAgent(name="VizWhizAgent")
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for visualization."""
        return pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'salary': [50000, 60000, 70000, 80000, 90000],
            'department': ['Sales', 'Engineering', 'Sales', 'Engineering', 'HR'],
        })
    
    def test_generate_visualizations(self, agent, sample_data):
        """Test visualization generation."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Age vs Salary'},
        )
        
        assert 'chart_info' in result
        assert 'success' in result['chart_info']
        assert 'plots' in result['chart_info']
    
    def test_scatter_plot_for_numeric_correlation(self, agent, sample_data):
        """Test scatter plot generation for correlated numeric columns."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Age vs Salary'},
        )
        
        plots = result['chart_info']['plots']
        if plots:
            plot_types = [p['type'] for p in plots]
            assert 'scatter' in plot_types or 'density_heatmap' in plot_types
    
    def test_box_plot_for_categorical_grouping(self, agent, sample_data):
        """Test box plot generation for categorical-numeric comparison."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Salary by Department'},
        )
        
        plots = result['chart_info']['plots']
        if plots:
            plot_types = [p['type'] for p in plots]
            assert 'box' in plot_types or 'violin' in plot_types
    
    def test_histogram_for_single_numeric(self, agent, sample_data):
        """Test histogram generation for single numeric column."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Age distribution'},
        )
        
        plots = result['chart_info']['plots']
        if plots:
            plot_types = [p['type'] for p in plots]
            assert 'histogram' in plot_types
    
    def test_plotly_json_serialization(self, agent, sample_data):
        """Test that plots are serialized to JSON."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Age vs Salary'},
        )
        
        plots = result['chart_info']['plots']
        for plot in plots:
            assert 'plotly_json' in plot
            assert isinstance(plot['plotly_json'], str)
    
    def test_invalid_columns_handled(self, agent):
        """Test handling of columns that don't exist."""
        data = pd.DataFrame({'age': [25, 30, 35]})
        
        result = agent.run(
            data.to_dict(orient='records'),
            consensus={'hypothesis': 'Salary vs Department'},
        )
        
        # Should still succeed with fallback plots
        assert result['chart_info']['success'] is True or result['chart_info']['plots'] != []
    
    def test_fallback_to_all_columns(self, agent, sample_data):
        """Test fallback to all columns when consensus fails."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Unknown pattern'},
            hypotheses=['Age vs Salary', 'Department breakdown'],
        )
        
        # Should generate plots using all columns
        assert result['chart_info']['success'] is True or len(result['chart_info']['plots']) > 0
    
    def test_unique_plot_types(self, agent, sample_data):
        """Test that duplicate plot types are removed."""
        result = agent.run(
            sample_data.to_dict(orient='records'),
            consensus={'hypothesis': 'Age vs Salary'},
        )
        
        plots = result['chart_info']['plots']
        seen_titles = set()
        for plot in plots:
            key = (plot['type'], plot['title'])
            assert key not in seen_titles
            seen_titles.add(key)


class TestInsightOrchestraWorkflow:
    """Test cases for InsightOrchestraWorkflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create an InsightOrchestraWorkflow instance."""
        return InsightOrchestraWorkflow()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for workflow testing."""
        return pd.DataFrame({
            'age': [25, 30, 35, 40, 45],
            'salary': [50000, 60000, 70000, 80000, 90000],
            'department': ['Sales', 'Engineering', 'Sales', 'Engineering', 'HR'],
        })
    
    def test_full_workflow_execution(self, workflow, sample_data):
        """Test running the full workflow."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'cleaner' in result
        assert 'hypothesis' in result
        assert 'debate' in result
        assert 'viz' in result
        assert 'audit_table' in result
    
    def test_cleaner_output_structure(self, workflow, sample_data):
        """Test cleaner output structure."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'cleaned_data' in result['cleaner']
        assert 'report' in result['cleaner']
    
    def test_hypothesis_output_structure(self, workflow, sample_data):
        """Test hypothesis output structure."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'hypotheses' in result['hypothesis']
        assert 'summary' in result['hypothesis']
    
    def test_debate_output_structure(self, workflow, sample_data):
        """Test debate output structure."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'scored_hypotheses' in result['debate']
        assert 'summary' in result['debate']
    
    def test_viz_output_structure(self, workflow, sample_data):
        """Test visualization output structure."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'chart_info' in result['viz']
        assert 'plots' in result['viz']['chart_info']
    
    def test_audit_table_generated(self, workflow, sample_data):
        """Test that audit table is generated."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert 'audit_table' in result
        assert '|' in result['audit_table']  # Markdown table format
        assert 'Feature' in result['audit_table']
    
    def test_self_refinement_hypotheses(self, workflow, sample_data):
        """Test that self-refinement modifies hypotheses."""
        result = workflow.run(sample_data.to_dict(orient='records'))
        
        assert result['hypothesis'].get('revised') is True
        assert 'revised_hypotheses' in result['hypothesis']
    
    def test_empty_data_handled(self, workflow):
        """Test handling of empty DataFrame."""
        data = pd.DataFrame({'col': []}).to_dict(orient='records')
        
        result = workflow.run(data)
        
        # Should not crash, but may have limited output
        assert 'cleaner' in result
        assert 'hypothesis' in result
