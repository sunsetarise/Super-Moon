# Prompt Studio SM36 additive overlay

This overlay adds `/api/sm36/overview` beside inherited SM34 and SM35 routes. It
copies only the new `supermoon36` runtime package and two bridge modules. The
installer is idempotent, preserves a pre-SM36 backup of `main.py`, and stops if
the expected SM35 insertion anchors are absent.

Run `python3 install_overlay.py PROMPTSTUDIO_ROOT SM36_TREE` after reconstructing
the full release. FastAPI remains an optional Prompt Studio dependency; the core
SM36 runtime uses only the Python standard library.
