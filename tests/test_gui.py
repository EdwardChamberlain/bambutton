import sys

from bambutton.gui import run_python_entrypoint


def test_run_python_entrypoint_exposes_utf8_stream_encoding():
    def entrypoint():
        sys.stdout.write(b"ok".decode(sys.stdout.encoding))
        sys.stderr.write(b"warn".decode(sys.stderr.encoding))

    result = run_python_entrypoint("tool", entrypoint, [])

    assert result.stdout == "ok"
    assert result.stderr == "warn"
