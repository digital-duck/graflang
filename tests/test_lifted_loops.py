"""Loops lifted from SPL by spl2graph run correctly in graflang (skipped when SPL.py is not installed)."""
import pytest

spl2graph = pytest.importorskip("spl3.spl2graph")

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

COUNTER = """
WORKFLOW counter
    INPUT: @x TEXT DEFAULT 'a'
    OUTPUT: @n INTEGER
DO
    @n := 0;
    WHILE @n < 3 DO
        @n := @n + 1;
    END;
    COMMIT @n
END
"""

TOOL_IN_CONDITION = """
CREATE TOOL_API enough(n INTEGER) RETURNS BOOL AS PYTHON $$
def enough(n: int) -> bool:
    return int(n) >= 3
$$;

WORKFLOW w
    INPUT: @x TEXT DEFAULT 'a'
    OUTPUT: @n INTEGER
DO
    @n := 0;
    WHILE NOT enough(@n) DO
        @n := @n + 1;
    END;
    COMMIT @n
END
"""


def lifted(tmp_path, source):
    graph, _ = spl2graph.spl_to_graph(source)
    path = tmp_path / "g.graph.yaml"
    path.write_text(spl2graph.graph_to_yaml(graph))
    return load_graph(path)


def test_a_counter_loop_stops_when_its_condition_does(tmp_path):
    g = lifted(tmp_path, COUNTER)
    assert check(g) == ([], [])
    rt = GraphLangRuntime(g, verbose=False)
    assert rt.execute({}) == {"n": 3} and rt.loop_iterations == {"loop_1": 3}


def test_a_tool_called_in_the_condition_is_asked_before_every_iteration(tmp_path):
    pytest.importorskip("jupyter_client")
    g = lifted(tmp_path, TOOL_IN_CONDITION)
    assert check(g) == ([], [])
    rt = GraphLangRuntime(g, verbose=False)
    assert rt.execute({}) == {"n": 3} and rt.loop_iterations == {"loop_1": 3}
