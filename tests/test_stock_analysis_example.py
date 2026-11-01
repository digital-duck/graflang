"""cookbook/stock_analysis (lifted from SPL.py's 066_stock_analysis, then reworked): the list of tickers is walked by a BATCH, not a LOOP.
The price download is replaced by a fixed CSV, so the test needs neither the network nor a model."""
from importlib.util import find_spec
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

GRAPH = Path(__file__).parent.parent / "cookbook" / "stock_analysis" / "stock_analysis.graph.yaml"
needs_kernel = pytest.mark.skipif(find_spec("jupyter_client") is None or find_spec("ipykernel") is None, reason="the kernel extra is not installed")
CSV = "date,close\n2026-01-01,100\n2026-01-02,110\n"


class Echo:
    name, model_override = "echo", None

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return f"R{len(self.prompts)}"


def offline(graph):
    """The same graph with the price download replaced by a fixed CSV."""
    fetch = next(n for n in graph["nodes"] if n["id"] == "each_ticker")["config"]["subgraph"]["nodes"][0]
    assert fetch["id"] == "fetch"
    fetch["config"]["code"] = f"_spl_result = {CSV!r}\n"
    return graph


def test_the_graph_validates():
    result = CliRunner().invoke(main, ["validate", str(GRAPH)])
    assert result.exit_code == 0, result.output


@needs_kernel
def test_each_ticker_is_analysed_once_and_the_report_is_written_from_all_of_them():
    llm = Echo()
    out = GraphLangRuntime(offline(load_graph(GRAPH)), llm=llm, verbose=False).execute({"tickers": "AAPL, MSFT", "days": 30})
    assert out == {"report": "R3"}
    assert len(llm.prompts) == 3                                           # two tickers and the portfolio
    assert "AAPL" in llm.prompts[0] and "change_pct=10.0" in llm.prompts[0]
    assert "MSFT" in llm.prompts[1] and "AAPL" not in llm.prompts[1]       # an item does not see the other
    assert "AAPL: R1" in llm.prompts[2] and "MSFT: R2" in llm.prompts[2] and "last 30 days" in llm.prompts[2]


@needs_kernel
def test_a_blank_item_in_the_list_is_skipped():
    llm = Echo()
    GraphLangRuntime(offline(load_graph(GRAPH)), llm=llm, verbose=False).execute({"tickers": "AAPL,, ,MSFT", "days": 5})
    assert len(llm.prompts) == 3
