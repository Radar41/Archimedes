"""Auth stub — single-operator, no external auth required for MVP."""

OPERATOR_ID = "radar41"


def get_current_user() -> str:
    return OPERATOR_ID
