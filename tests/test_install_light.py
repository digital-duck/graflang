"""`graf` starts without the optional jinja2 (only the Rust code generator needs it, and it says so)."""
import subprocess
import sys
import textwrap

CODE = textwrap.dedent("""
    import sys
    sys.modules["jinja2"] = None               # as if jinja2 were not installed
    from click.testing import CliRunner
    from graphlang.cli import main
    assert CliRunner().invoke(main, ["--help"]).exit_code == 0
    r = CliRunner().invoke(main, ["vis", "--list-engines"]); assert r.exit_code == 0, r.output
    from graphlang.grafc.compiler import GraphLangCompiler
    c = GraphLangCompiler.__new__(GraphLangCompiler)
    try:
        c.generate_rust()
    except ValueError as e:
        print("graflang[grafc]" in str(e))
""")


def test_graf_starts_without_jinja2_and_the_code_generator_explains():
    r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[-1] == "True", r.stdout
