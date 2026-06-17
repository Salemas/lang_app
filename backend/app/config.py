_model = "gpt-4o-mini"


def get_model() -> str:
    return _model


def set_model(name: str) -> None:
    global _model
    _model = name
