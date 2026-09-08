cmake_minimum_required(VERSION 3.15)
project(signallab_fast)
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(_fast fast_backtest.cpp)
