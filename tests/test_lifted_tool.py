"""A graph lifted from SPL with a Python tool (cookbook/lifted_tool) runs offline in graflang's own kernel."""
from importlib.util import find_spec
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

GRAPH = Path(__file__).parent.parent / "cookbook" / "lifted_tool" / "lifted_tool.graph.yaml"

pytestmark = pytest.mark.skipif(find_spec("jupyter_client") is None or find_spec("ipykernel") is None,
                                reason="needs `pip install 'graflang[kernel]'`")


def test_the_tool_source_travels_in_the_node_and_runs_without_spl_py():
    graph = load_graph(GRAPH)
    assert check(graph)[0] == []
    assert GraphLangRuntime(graph, verbose=False).execute({"word": "hello"}) == {"loud": "HELLO!"}
    assert GraphLangRuntime(graph, verbose=False).execute({}) == {"loud": "HI!"}          # the input default
