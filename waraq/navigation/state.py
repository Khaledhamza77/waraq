from typing import Literal, TypedDict

Status = Literal["", "navigating", "found", "not_found", "rejected", "greeting"]


class NavigationState(TypedDict, total=False):
    original_query: str
    query: str
    language: str
    intent: str
    navigation_path: list[str]
    leaf_content: str
    leaf_metadata: list[dict]
    status: Status
