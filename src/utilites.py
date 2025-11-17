import os


def load_env():
    """Load environment variables from .env file."""
    env_vars = {}
    env_path = ".env"

    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Environment file not found: {env_path}")

    try:
        with open(env_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" not in line:
                        continue  # Skip malformed lines
                    key, value = line.split("=", 1)
                    env_vars[key.strip().lower()] = value.strip()
    except Exception as e:
        raise RuntimeError(f"Error loading .env file: {e}")

    return env_vars
