.PHONY: test verify compile manifest

test:
	python tools/run_all_tests.py

verify:
	python tools/verify_assets.py

compile:
	python -m compileall -q versions/sm34/supermoon_runtime/src versions/sm34/supermoon_studio versions/sm35/src versions/sm36/src

manifest:
	python tools/build_source_manifest.py . manifests/GITHUB_SOURCE_MANIFEST.json

