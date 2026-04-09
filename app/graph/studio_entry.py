from app.graph.workflow import build_workflow


def get_graph():
    """
    LangGraph Studio entrypoint.
    Returns a compiled graph app for visual debugging.
    """
    return build_workflow()

