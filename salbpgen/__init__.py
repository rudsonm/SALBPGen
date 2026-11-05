"""Reproduction of SALBPGen (Otto, Otto & Scholl, 2013), an instance generator
for the Simple Assembly Line Balancing Problem."""

from .generator import (
    PAPER_BLOCKS, PAPER_SIZES, PAPER_TIME_DISTS, InstanceParams, generate_dataset,
    generate_instance, permute_times,
)
from .features import FeatureParams, NRPSInstance, critical_path, generate_nrps
from .graph import PrecedenceGraph
from .instance import Instance
from .modules import connect_modules
from .precedence import (
    GenerationError, GraphParams, default_stages, generate_precedence_graph,
    max_flexibility_stages, os_max, os_min, structure_preset,
)
from .stats import bottleneck_tasks, chain_tasks, instance_stats, lower_bound
from .times import DISTRIBUTIONS, generate_task_times
from .trickiness import is_trivial, random_search, trickiness

__all__ = [
    "DISTRIBUTIONS", "FeatureParams", "GenerationError", "NRPSInstance", "GraphParams", "Instance", "InstanceParams",
    "PAPER_BLOCKS", "PAPER_SIZES", "PAPER_TIME_DISTS", "PrecedenceGraph",
    "bottleneck_tasks", "chain_tasks", "connect_modules", "critical_path", "default_stages",
    "generate_dataset", "generate_instance", "generate_nrps", "generate_precedence_graph",
    "generate_task_times", "instance_stats", "is_trivial", "lower_bound",
    "max_flexibility_stages", "os_max", "os_min", "permute_times", "random_search",
    "structure_preset", "trickiness",
]

__version__ = "0.2.0"
