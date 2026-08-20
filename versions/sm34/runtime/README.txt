Runtime and derived-cache directory for Super Moon 34 New Universe Prompt Studio.

SETUP_WINDOWS.bat / START_SUPERMOON.bat may create:
- setup.log
- setup-state.json
- start-check.json
- venv-rebuild-receipt.json
- knowledge_index.sqlite3
- knowledge_chunks.bin
- server-state.json
- FULL_AUDIT_REPORT.json

The bundled SM34 knowledge cache is derived from the canonical TXT.GZ under knowledge/ and is shipped for immediate use. Its source filename, byte count, index format, and decompressed SHA-256 are checked before use. It can always be rebuilt with REBUILD_KNOWLEDGE_INDEX.bat.
