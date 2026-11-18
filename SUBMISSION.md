# Builder → Intelligent Contracts

**Title**

DeltaLoom — Consensus-verified minimum-byte binary patches

**Notes / Description**

DeltaLoom is a permissionless GenLayer registry for byte-minimal patches between commit-pinned public artifacts of up to 1,024 bytes. The leader fetches both files and synthesizes COPY/LITERAL bytecode. Validators independently re-fetch both bodies, replay the patch against the full target, and check optimality with a separate shortest-path solver. Equal-cost programs can pass if they reproduce the exact bytes. Each ordered pair stores the patch, lengths, digests, and source URLs. A consumer supplies a digest-checked baseline to reconstruct the target onchain. StudioNet proofs cover both directions between real Go ignore-template revisions (38 and 26 patch bytes), a missing file, and a duplicate request. The rejected writes left state unchanged. GenVM lint, 13 direct tests, and 9 transport tests passed. Optimality is specific to the documented COPY/LITERAL format.

**Evidence links**

- [Repository](https://github.com/mohammadisina1988-jpg/delta-loom)
- [GenLayer contract source](https://github.com/mohammadisina1988-jpg/delta-loom/blob/97efbfb4a3ba65d7bdc4e3ae079a156d5c37077b/contracts/delta_loom.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/tx/0xe966e840bd1e83a389c5d421082fc37f2a03af307b7f2f88f70612ccb95188cd)
- [Scenario proofs and receipts](https://github.com/mohammadisina1988-jpg/delta-loom/blob/main/proofs/README.md)
