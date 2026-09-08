#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <cmath>
#include <vector>

namespace py = pybind11;

// Mirrors the Python convention exactly:
// signal position[t] is executed for return[t+1], and the turnover generated
// by that signal change is charged on the same execution bar.
std::vector<double> equity_curve(
    const std::vector<double>& returns,
    const std::vector<double>& positions,
    double fee_bps
) {
    const std::size_t n = std::min(returns.size(), positions.size());
    std::vector<double> equity(n, 1.0);
    double value = 1.0;
    const double fee = fee_bps / 10000.0;

    for (std::size_t i = 0; i < n; ++i) {
        const double held_pos = (i == 0 ? 0.0 : positions[i - 1]);
        const double previous_held = (i <= 1 ? 0.0 : positions[i - 2]);
        const double turnover = (i == 0 ? 0.0 : std::abs(held_pos - previous_held));
        const double pnl = held_pos * returns[i] - turnover * fee;
        value *= (1.0 + pnl);
        equity[i] = value;
    }
    return equity;
}

PYBIND11_MODULE(_fast, m) {
    m.doc() = "Optional C++ acceleration for SignalLab";
    m.def("equity_curve", &equity_curve, py::arg("returns"), py::arg("positions"), py::arg("fee_bps") = 10.0);
}
