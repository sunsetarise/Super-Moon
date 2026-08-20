# GitHub release guide

## Repository publication

1. Choose and add a license.
2. Install Git and Git LFS.
3. Extract the source distribution parts and verify their manifest.
4. From this repository root, run:

   ```bash
   git lfs install
   git init
   git add .gitattributes
   git add .
   git status
   git commit -m "Release Super Moon 36 New Universe source"
   git branch -M main
   git remote add origin <your-repository-url>
   git push -u origin main
   ```

5. Confirm the merged `.txt.gz` appears as an LFS object, not an ordinary
   391 MB Git blob.
6. Enable Actions, CodeQL, Dependabot, and private vulnerability reporting.

## Release-asset alternative

If Git LFS is unavailable, remove the large `.txt.gz` from the Git index while
retaining its checksum and manifest, then upload it to a GitHub Release. Do not
rewrite or recompress the file; its SHA-256 must remain
`71ac376db613c70d5cad52394f03adfcb7f2412e4c643bbb2e301e1c47473c33`.

The externally delivered `.tar.gz.001`, `.002`, and subsequent files are
transport parts, not independent archives. Reassemble in numeric order and
verify the archive hash from `SUPER_MOON_36_GITHUB_SOURCE_80MB_MANIFEST.json`.

