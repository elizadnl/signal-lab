export type Point = { date: string; value: number }
export type Trade = { date: string; return: number; direction: string; outcome: string }
export type RegimeRow = { regime: string; return: number; sharpe: number | null; hit_rate: number; observations: number }
export type EdgeDecayRow = { horizon: number; mean_edge_bps: number | null; hit_rate: number | null; observations: number }
export type CostStressRow = { fee_bps: number; total_return: number; sharpe: number }
export type DelayStressRow = { delay_days: number; total_return: number; sharpe: number }
export type ParameterSensitivityRow = { lookback: number; total_return: number; sharpe: number }
export type ParameterSensitivity = { rows: ParameterSensitivityRow[]; positive_parameter_share: number; plateau_score: number }
export type ReturnConcentration = { active_sessions: number; top_profit_share: number | null; top_loss_share: number | null; return_without_best_sessions: number; removed_sessions: number }
export type SelectionBias = { reality_check_p: number | null; best_specification: string | null; best_mean_return: number | null; trials: number; block_size?: number; bootstrap_samples?: number; scope?: string }
export type CrossAssetRow = { symbol: string; total_return: number; sharpe: number; fdr_q: number | null; positive: boolean }
export type HoldoutTransfer = { available: boolean; reason?: string; target?: string; donors?: string[]; chosen_lookback?: number; donor_mean_train_sharpe?: number; train_start?: string; train_end?: string; test_start?: string; test_end?: string; observations?: number; total_return?: number; sharpe?: number; max_drawdown?: number; positive?: boolean; scope?: string }
export type CrossAssetValidation = { asset_rows: CrossAssetRow[]; positive_share: number; median_sharpe: number | null; replication_pass: boolean; holdout: HoldoutTransfer }
export type YearRow = { year: number; return: number; sharpe: number; max_drawdown: number; hit_rate: number; active_sessions: number }
export type GateCriterion = { name: string; label: string; pass: boolean }
export type DeploymentGate = { status: string; passed: number; total: number; positive_year_share?: number; criteria: GateCriterion[] }
export type Metrics = {
  total_return: number
  annualized_return: number
  annualized_volatility: number
  sharpe: number
  sortino: number | null
  calmar: number | null
  max_drawdown: number
  win_rate: number
  profit_factor: number | null
  exposure: number
  trades: number
  turnover: number
  longest_win_streak: number
  longest_loss_streak: number
}
export type Robustness = {
  evaluation_start: string
  hac_t_stat: number | null
  p_value: number | null
  fdr_q: number | null
  sharpe_ci_low: number | null
  sharpe_ci_high: number | null
  benchmark_return: number
  excess_vs_benchmark: number
  evidence_grade: string
}
export type ParameterStability = {
  dominant_lookback: number | null
  unique_lookbacks: number
  switches: number
  stability_score: number | null
}
export type SignalState = { label: string; score: number | null; change_30d: number | null }
export type Fold = {
  train_start: string
  train_end: string
  test_start: string
  test_end: string
  lookback: number
  train_sharpe: number
}
export type Run = {
  symbol: string
  signal: string
  mode: string
  fee_bps: number
  holding_period: number
  selected_lookback: number | null
  start_date: string
  end_date: string
  metrics: Metrics
  robustness: Robustness
  parameter_stability: ParameterStability
  signal_state: SignalState
  break_even_fee_bps: number | null
  yearly_performance: YearRow[]
  deployment_gate: DeploymentGate
  equity: Point[]
  drawdown: Point[]
  rolling_reliability: Point[]
  regime_performance: RegimeRow[]
  edge_decay: EdgeDecayRow[]
  cost_stress: CostStressRow[]
  execution_delay_stress: DelayStressRow[]
  parameter_sensitivity: ParameterSensitivity
  return_concentration: ReturnConcentration
  selection_bias: SelectionBias
  cross_asset: CrossAssetValidation
  trades: Trade[]
  folds: Fold[]
}
export type DataSource = {
  kind: string
  label: string
  claim_status: string
  source?: string
  interval?: string
  retrieved_at_utc?: string
  requested_end_month?: string
}
export type DataAudit = {
  clean: boolean
  rows: number
  start_date?: string | null
  end_date?: string | null
  duplicate_dates?: number
  missing_values?: number
  invalid_ohlc_rows?: number
  nonpositive_price_rows?: number
  negative_volume_rows?: number
  zero_volume_rows?: number
  missing_calendar_days?: number
  max_gap_days?: number
  sha256?: string
  file?: string
}
export type Payload = {
  generated_for: string
  version?: string
  methodology: string
  data_source: DataSource
  data_audit?: Record<string, DataAudit>
  runs: Run[]
}
