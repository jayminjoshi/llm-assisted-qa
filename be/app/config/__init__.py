import pathlib
from loguru import logger

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

path = pathlib.Path(__file__).parent / "config.toml"
try:
    with path.open(mode="rb") as fp:
        config = tomllib.load(fp)
except FileNotFoundError:
    logger.exception("Config file not found. Please create a config.toml file in the config directory.")
    exit()
