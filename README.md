# DeltaLoom

DeltaLoom synthesizes byte-minimal patches between two small public artifacts. A consumer can apply the published patch with a verified baseline to recover the target bytes onchain.

Deploy without arguments. Anyone can call `synthesize(base_url, target_url)` for an ordered pair of raw GitHub paths pinned by full commit hashes. Each response may hold up to 1,024 bytes. The contract fetches both bodies inside its GenLayer nondeterministic flow. It stores the patch, source URLs, lengths, and SHA-256 digests. A published pair is immutable.

The leader computes one globally minimal patch using backward dynamic programming and a rolling longest-common-prefix table. Each validator independently fetches the files, applies the proposed bytecode, compares the restored target byte for byte, and computes the minimum cost using a separate forward shortest-path calculation. Validators can accept multiple equally short bytecodes because each must produce the exact same target and have the same minimum length.

| Opcode | Encoding |
| --- | --- |
| COPY | Byte `00`, unsigned 16-bit baseline offset, unsigned 16-bit length |
| LITERAL | Byte `01`, unsigned 16-bit length, literal bytes |

Integers are big-endian. Lengths must be positive. Empty target data uses empty bytecode. The optimum applies to this bytecode format, including operation overhead. Raw response bytes determine the result, including line endings and binary content.

`get_delta(base_url, target_url)` exposes a published program. `apply_delta(base_url, target_url, base_hex)` verifies the baseline digest, applies the stored bytecode, verifies the output digest, and returns the target in lowercase hex. Failed downloads and rejected programs leave the pair open for retry.

## Verification

```sh
pip install -r requirements-dev.txt
genvm-lint download --version v0.2.16
genvm-lint check contracts/delta_loom.py
python -m pytest tests/direct -q
npm ci
node --test tests/rpc-preflight.test.cjs
```

The proof checks both directions between two upstream revisions of the Go ignore template, including exact onchain byte reconstruction. It verifies byte optimality by enumerating every substring edge, checks signed calldata and deployed code bytes, and verifies that missing and duplicate requests leave state unchanged. The test fixtures originate in the CC0-licensed upstream collection. Generic CLI receipt transport is reused under MIT.

[GitHub gitignore collection](https://github.com/github/gitignore) · [GenLayer equivalence principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
