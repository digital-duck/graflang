"""Graph topology analyzer."""

import networkx as nx
from typing import Dict, Any, List

class GraphAnalyzer:
    """Analyzes GraphLang workflow topology."""
    
    def __init__(self, graph_data: Dict):
        self.graph_data = graph_data
        self.G = nx.DiGraph()
        self._build_graph()
    
    def _build_graph(self):
        """Build NetworkX graph from GraphLang data."""
        for node in self.graph_data['nodes']:
            self.G.add_node(node['id'], **node)
        
        for edge in self.graph_data['edges']:
            src_node = edge['source'].split('.')[0]
            tgt_node = edge['target'].split('.')[0]
            self.G.add_edge(src_node, tgt_node, **edge)
    
    def analyze(self) -> Dict:
        """Perform topological analysis."""
        return {
            'node_count': len(self.G.nodes()),
            'edge_count': len(self.G.edges()),
            'node_types': self._count_node_types(),
            'critical_path': self._find_critical_path(),
            'parallelizable_sections': self._find_parallel_sections(),
            'composite_nodes': self._find_composite_nodes(),
            'guard_nodes': self._find_guard_nodes(),
        }
    
    def _count_node_types(self) -> Dict[str, int]:
        """Count nodes by type."""
        counts = {}
        for node in self.G.nodes(data=True):
            node_type = node[1]['type']
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts
    
    def _find_critical_path(self) -> List[str]:
        """Find the longest path through the graph."""
        # Simplified: find path from INPUT to OUTPUT
        input_nodes = [n for n in self.G.nodes() if self.G.nodes[n]['type'] == 'INPUT']
        output_nodes = [n for n in self.G.nodes() if self.G.nodes[n]['type'] == 'OUTPUT']
        
        if not input_nodes or not output_nodes:
            return []
        
        try:
            path = nx.longest_path(self.G, source=input_nodes[0], target=output_nodes[0])
            return path
        except nx.NetworkXNoPath:
            return []
    
    def _find_parallel_sections(self) -> List[List[str]]:
        """Find sections that can be executed in parallel."""
        # Nodes at the same topological level can be parallelized
        levels = {}
        for node in nx.topological_sort(self.G):
            level = max([levels.get(pred, 0) for pred in self.G.predecessors(node)] + [0]) + 1
            levels[node] = level
        
        # Group nodes by level
        parallel_groups = {}
        for node, level in levels.items():
            if level not in parallel_groups:
                parallel_groups[level] = []
            parallel_groups[level].append(node)
        
        # Return groups with more than one node
        return [group for group in parallel_groups.values() if len(group) > 1]
    
    def _find_composite_nodes(self) -> List[str]:
        """Find nodes with subgraphs (Tier 3 composition)."""
        composite = []
        for node in self.G.nodes(data=True):
            if 'config' in node[1] and 'subgraph' in node[1]['config']:
                composite.append(node[0])
        return composite
    
    def _find_guard_nodes(self) -> List[str]:
        """Find GUARD nodes."""
        return [n for n in self.G.nodes() if self.G.nodes[n]['type'] == 'GUARD']
