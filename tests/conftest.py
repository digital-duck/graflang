"""Test selection: `--mode` is the only switch. The default runs the offline tests, `--mode llm` only the ones that call a real model."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--mode", choices=("no-llm", "llm", "all"), default="no-llm",
                     help="no-llm (default): offline tests only; llm: only the tests marked `llm` (real claude_cli calls, billed); all: both")


def pytest_configure(config):
    if config.option.markexpr:                                   # pytest's own -m: SPL uses -m for --model, so there is one switch here
        raise pytest.UsageError("-m is not used in this repo; choose tests with --mode no-llm|llm|all")


def pytest_report_header(config):
    return f"graflang test mode: {config.getoption('--mode')} (--mode llm runs the real-model tests, --mode all both)"


def pytest_collection_modifyitems(config, items):
    mode = config.getoption("--mode")
    if mode == "all":
        return
    keep, dropped = [], []
    for item in items:
        (keep if (item.get_closest_marker("llm") is not None) == (mode == "llm") else dropped).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = keep
