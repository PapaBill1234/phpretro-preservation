# Fresh-start Stage 4: where the rewrite should live

Status: location selected; repository creation is still deferred. No branch or repository was created.

## Options

| Option | Advantages | Costs and risks |
| --- | --- | --- |
| New branch in `hotel-drogon-scope-guard` | Keeps one remote, issue tracker, and familiar checkout; can reuse history and existing CI configuration. | Carries the current repository history, including the implementation being replaced and its mixed-quality decisions. A branch isolates changes but does not remove that history or prevent accidental cherry-picks and merges. Existing C++/React workflow and documentation continue to imply the old architecture unless deliberately replaced. |
| New repository | Gives the clean rewrite an independent history, issue/CI configuration, and clear boundary from the existing application. The old repository can remain available as a read-only behavior and evidence reference. | Requires new repository setup, access controls, CI, and a deliberate transfer of approved evidence. History and evidence do not move automatically; copying current implementation risks carrying forward the problems this restart is meant to address. |

## Recommendation

Use a new repository for the fresh rewrite, while retaining the current repository as a read-only historical implementation and evidence source. Start the new repository from approved planning and evidence artifacts, not by copying the existing backend or frontend. Carry over only reviewed behavior captures, schema/ownership evidence, and asset provenance records that are needed for the selected first-release slice.

This recommendation fits the stated clean-rewrite purpose and avoids blending old implementation history with the new design. It does not select a backend language or authorize repository creation. Before creation, decide the repository name/visibility, who needs access, and which evidence artifacts may be copied. Keep credentials and disposable database contents out of any transfer.

## Decision recorded

The selected location is a **new repository**. This records the location choice only; it does not create the repository or authorize transferring files yet.

## Still open

- Repository name and owner.
- Visibility and access controls.
- Approved evidence to transfer, with disposable data and credentials excluded.
- Backend and frontend implementation choices remain for the rewrite plan; this proposal makes no language selection.
