"""Test selection: `--mode no-llm` (the default) runs the offline tests, `--mode llm` only the ones that call a real model."""


def pytest_addoption(parser):
    parser.addoption("--mode", choices=("no-llm", "llm", "all"), default="no-llm",
                     help="no-llm (default): offline tests only; llm: only the tests marked `llm` (real claude_cli calls, billed); all: both")


def pytest_report_header(config):
    if config.option.markexpr:
        return None                                              # an explicit -m decides
    return f"graflang test mode: {config.getoption('--mode')} (--mode llm runs the real-model tests, --mode all both)"


def pytest_collection_modifyitems(config, items):
    mode = config.getoption("--mode")
    if config.option.markexpr or mode == "all":                  # an explicit -m expression wins over --mode
        return
    keep, dropped = [], []
    for item in items:
        (keep if (item.get_closest_marker("llm") is not None) == (mode == "llm") else dropped).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = keep
