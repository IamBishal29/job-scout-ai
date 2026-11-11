"""Entry point for `python -m jobpilot`."""

from jobpilot import __version__


def main() -> None:
    print(f"JobPilot {__version__}")


if __name__ == "__main__":
    main()
