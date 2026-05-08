"""Backward-compat shim. Real code lives in src/tools/."""
from src.tools import all_tools  # noqa: F401
from src.tools.native import { #noqa: F401
    web_search, wikipedia_lookup, calculator, python_repl, 
    list_files, read_file, write_file, run_shell, doc_search
}
