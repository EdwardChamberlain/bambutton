try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    PackageNotFoundError = Exception
    version = None

try:
    __version__ = version("bambuddy-plate-clear-button") if version else "0+unknown"
except PackageNotFoundError:
    __version__ = "0+unknown"
