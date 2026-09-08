from signallab.pipeline import _deployment_gate


def _run():
    return {
        'mode': 'walk_forward',
        'metrics': {'total_return': 0.25, 'sharpe': 1.1},
        'robustness': {'fdr_q': 0.04, 'sharpe_ci_low': 0.2},
        'parameter_stability': {'stability_score': 0.75},
        'cost_stress': [{'fee_bps': 25.0, 'total_return': 0.08, 'sharpe': 0.5}],
        'selection_bias': {'reality_check_p': 0.04},
        'cross_asset': {'replication_pass': True, 'holdout': {'available': True, 'positive': True}},
        'yearly_performance': [
            {'year': 2023, 'return': 0.1},
            {'year': 2024, 'return': -0.02},
            {'year': 2025, 'return': 0.15},
        ],
    }


def test_gate_passes_when_all_checks_clear():
    gate = _deployment_gate(_run())
    assert gate['status'] == 'pass'
    assert gate['passed'] == gate['total'] == 9


def test_gate_fails_when_oos_result_is_negative():
    run = _run()
    run['metrics']['total_return'] = -0.05
    run['metrics']['sharpe'] = -0.2
    gate = _deployment_gate(run)
    assert gate['status'] == 'fail'
