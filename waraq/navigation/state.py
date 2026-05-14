from typing import TypedDict


class NavigationState(TypedDict, total=False):
    original_query: str
    query: str
    language: str
    intent: str
    navigation_path: list[str]
    leaf_content: str
    leaf_metadata: dict
    status: str
