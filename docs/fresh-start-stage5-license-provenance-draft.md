# Fresh-start Stage 5: README and asset provenance wording

Status: draft for review only. This wording has not been applied to `README.md`, a license file, or an asset directory.

## Proposed README wording

> This is a non-commercial preservation and hobby project. The project's original code is distributed under the GNU General Public License, version 3 (GPL-3.0); see `LICENSE`.
>
> The application is an independent clean reimplementation based on observed behavior and golden captures. Original PHPRetro PHP source code is not copied into this codebase. Third-party artwork, themes, fonts, and other assets may have separate authors and terms; their recorded provenance does not imply that they are relicensed under GPL-3.0. This project is not affiliated with, endorsed by, or sponsored by Sulake Corporation. Habbo and related marks remain the property of their respective owners.

The README should credit original creators for retained assets where known, using the asset provenance record as the source of attribution. Unknown attribution should remain explicitly unknown rather than be invented.

## Proposed provenance file

Create one `ASSET-PROVENANCE.md` in the clearly named asset folder when assets are brought into the repository. Keep one row per file:

| Repository path | Source URL or archive | Creator / rights holder | Retrieved (UTC date) | SHA-256 | License / terms known | Notes / attribution |
| --- | --- | --- | --- | --- | --- | --- |
| `path/to/asset` | `https://...` | `name or UNKNOWN` | `YYYY-MM-DD` | `64-character digest` | `license or UNKNOWN` | `required credit or context` |

Record source, retrieval date, and hash for every asset. Record creator, license, and attribution information when available; mark unresolved items `UNKNOWN` and flag them for later review. The provenance file is evidence, not a claim that all assets share the code license.

## Still open

- Review the wording before it is applied.
- Confirm the final code license file and exact GPL-3.0 license text when the new repository is approved.
- Select the asset-folder name and provenance path with the repository layout.
- Populate actual per-file records only when assets are selected for inclusion; do not fabricate sources, dates, hashes, or rights information.
