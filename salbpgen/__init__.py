"""Reproduction of SALBPGen (Otto, Otto & Scholl, 2013), an instance generator
for the Simple Assembly Line Balancing Problem."""

from .generator import InstanceParams, generate_dataset, generate_instance
from .graph import PrecedenceGraph
from .instance import Instance
from .precedence import GraphParams, generate_precedence_graph
from .stats import instance_stats
from .times import DISTRIBUTIONS, generate_task_times

__all__ = [
    "DISTRIBUTIONS",
    "GraphParams",
    "Instance",
    "InstanceParams",
    "PrecedenceGraph",
    "generate_dataset",
    "generate_instance",
    "generate_precedence_graph",
    "generate_task_times",
    "instance_stats",
]

__version__ = "0.1.0"
