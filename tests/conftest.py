import logging


def pytest_configure(config):
    for name in ("httpx", "httpcore", "openai", "langgraph", "langchain_core", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
