# Release assets

`SUPER_MOON_36_NEW_UNIVERSE_QUALIFICATION_CANDIDATE_FULL_MERGED.txt.gz` is the
complete byte-preserved merged release. It is 391,292,410 bytes and must remain
unchanged. Use `python ../tools/verify_assets.py` from this directory or
`python tools/verify_assets.py` from the repository root.

Because the file exceeds 100 MB, `.gitattributes` assigns it to Git LFS. An
alternative is to keep it as a GitHub Release asset and retain this directory's
manifest and checksums in normal Git.

