import os


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value is not None and str(value).strip() != "":
            return str(value)
    except Exception:
        pass

    env_value = os.getenv(name)
    if env_value is not None and env_value.strip() != "":
        return env_value

    return default
