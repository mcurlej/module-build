from enum import Enum
from typing import List, TypedDict


class MockBuildState(Enum):
    INIT = 1
    BUILDING = 2
    FAILED = 3
    FINISHED = 4


class MockBuildStatusContext(TypedDict):
    state: MockBuildState
    current_build_batch: int
    num_finished_comps: List[int]


class MockBuildStatusBatch(TypedDict):
    state: MockBuildState
    state_component: MockBuildState
    current_component: int
    finished_components: List[int]
