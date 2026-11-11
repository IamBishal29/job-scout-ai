import jobpilot
from jobpilot.__main__ import main


def test_version_is_set():
    assert jobpilot.__version__ == "0.1.0"


def test_main_prints_version(capsys):
    main()
    assert "JobPilot 0.1.0" in capsys.readouterr().out
