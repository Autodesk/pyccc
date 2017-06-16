import pytest

def pytest_addoption(parser):
    parser.addoption("--testccc", action="store_true")