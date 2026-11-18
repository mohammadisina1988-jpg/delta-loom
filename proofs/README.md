# StudioNet proofs

Contract 0xAD8e2a969628C4b6350b6E5207634f3dec610f9B on GenLayer StudioNet. [Tested contract source](https://github.com/mohammadisina1988-jpg/delta-loom/blob/97efbfb4a3ba65d7bdc4e3ae079a156d5c37077b/contracts/delta_loom.py) · [Passing proof workflow](https://github.com/mohammadisina1988-jpg/delta-loom/actions/runs/44278049073).

Source SHA-256 822b8e59697385da57ea1785d4d0eed52ce941138ce54b7115eb1a7ffe046886. The deployment receipt and a fresh RPC read both match the tested source bytes.

| Scenario | Explorer | Execution | Consensus | Agree / disagree / idle | Receipt |
| --- | --- | --- | --- | --- | --- |
| Deploy DeltaLoom | [0xe966e840bd…](https://explorer-studio.genlayer.com/tx/0xe966e840bd1e83a389c5d421082fc37f2a03af307b7f2f88f70612ccb95188cd) | SUCCESS | MAJORITY_AGREE | 3 / 0 / 2 | [deploy receipt](deploy-receipt.json) |
| Publish forward patch | [0x811d3c35df…](https://explorer-studio.genlayer.com/tx/0x811d3c35dfa7785bcf8f84b891874a4e7e2e86f572fc05ae81e04d9838e1118d) | SUCCESS | MAJORITY_AGREE | 3 / 0 / 2 | [forward receipt](forward-receipt.json) |
| Publish reverse patch | [0x8849ee0058…](https://explorer-studio.genlayer.com/tx/0x8849ee005858070a800e01ef1b785370b8ed937ace0ad136d50ea9db12beeefe) | SUCCESS | MAJORITY_AGREE | 3 / 0 / 2 | [reverse receipt](reverse-receipt.json) |
| Reject a missing upstream file | [0xd297e6f59c…](https://explorer-studio.genlayer.com/tx/0xd297e6f59c4ff5e87206068736622395a6728c0d746b81c5fd7872978163b26f) | ERROR | MAJORITY_AGREE | 3 / 0 / 2 | [missing receipt](missing-receipt.json) |
| Reject a duplicate pair | [0x288c1f4efa…](https://explorer-studio.genlayer.com/tx/0x288c1f4efa04095874a3b3828b22d4d14b4ec402399692c030ea1df0474bfdb4) | ERROR | MAJORITY_AGREE | 3 / 0 / 2 | [duplicate receipt](duplicate-receipt.json) |

All five receipts are finalized. The proof verifies signed calldata and reads the contract state after every transaction. The missing and duplicate calls return the expected errors and leave all checked pairs unchanged.

| Direction | Baseline bytes | Target bytes | Minimum patch bytes |
| --- | ---: | ---: | ---: |
| forward | 572 | 588 | 38 |
| reverse | 588 | 572 | 26 |

The two files are commit-pinned upstream revisions of Go.gitignore. The CLI replay reproduced the exact target bytes in each direction. An independent decoder and exhaustive substring solver checked byte equality and optimality.

GenVM lint passed alongside 13 direct tests and 9 transport tests. The proof tooling retries long read requests in StudioNet’s legacy calldata format when the standard RLP envelope triggers the decoder error. [Upstream decoder fix](https://github.com/genlayerlabs/genlayer-studio/pull/1746).

[Verification report](verified.json) · [Transaction journal](transactions.json).
