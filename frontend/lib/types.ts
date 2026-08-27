export interface Schema {
  [table: string]: { name: string; type: string }[];
}

export interface ConnectRequest {
  type: string;
  connection_string: string;
}

export interface ConnectResponse {
  status: string;
  connection_id: string;
  schema: Schema;
}

export interface LoadTableRequest {
  connection_id: string;
  table_name: string;
  row_limit?: number;
}

export interface LoadTableResponse {
  file_path: string;
  table_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
}

/** What the reader had to assume to parse the file, so we can tell the user. */
export interface ParseAssumptions {
  encoding: string;
  delimiter: string;
  datetime_columns: string[];
}

export interface UploadResponse {
  file_path: string;
  name: string;
  rows: number;
  columns: number;
  column_names: string[];
  dtypes: Record<string, string>;
  null_counts: Record<string, number>;
  preview: Record<string, unknown>[];
  assumptions: ParseAssumptions;
}

export interface NLQRequest {
  file_path: string;
  question: string;
  session_id?: string;
}

export interface NLQResponse {
  answer: string;
  code: string;
  reasoning: string;
  plot_json: string | null;
  needs_clarification: boolean;
  clarification_question: string | null;
  execution_success: boolean;
  error: string | null;
  session_id: string | null;
  tokens_used?: number;
  cost_usd?: number;
}

export interface AppConfig {
  provider: string;
  model: string;
  available: string[];
  ready: Record<string, boolean>;
}

export interface DemoDataset {
  id: string;
  name: string;
  description: string;
  rows: number;
  columns: number;
  use_cases: string[];
}

export interface DemoDatasetListResponse {
  datasets: Record<string, DemoDataset>;
}

export interface DemoDatasetLoadResponse {
  file_path: string;
  dataset_id: string;
  dataset_name: string;
  columns: string[];
  row_count: number;
  column_count: number;
  description: string;
  use_cases: string[];
}

export interface ScoredHypothesis {
  hypothesis: string;
  confidence: number;
  business_value: number;
  statistical_argument: string;
  business_argument: string;
}

export interface PlotInfo {
  type: string;
  title: string;
  plotly_json: string;
}

export interface ProcessResponse {
  cleaner: {
    report: {
      initial_shape: [number, number];
      final_shape: [number, number];
      duplicates_removed: number;
      total_missing: number;
      bias_flags?: string[];
      outlier_flags?: string[];
    };
  };
  hypothesis: {
    hypotheses: string[];
    summary: {
      num_hypotheses: number;
      numeric_columns: string[];
      categorical_columns: string[];
    };
  };
  debate: {
    scored_hypotheses: ScoredHypothesis[];
    summary: {
      consensus: ScoredHypothesis | null;
    };
  };
  viz: {
    chart_info: {
      success: boolean;
      plots: PlotInfo[];
    };
  };
  narrative: string;
  suggested_questions: string[];
  preview?: {
    columns: string[];
    rows: Record<string, unknown>[];
  };
}
