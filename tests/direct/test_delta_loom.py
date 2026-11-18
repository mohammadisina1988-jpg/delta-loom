from hashlib import sha256
from pathlib import Path
import re

import pytest


BASE = 'https://raw.githubusercontent.com/github/gitignore/74cf7151d96a6eaacd4f66fd59b01a140036d857/Go.gitignore'
TARGET = 'https://raw.githubusercontent.com/github/gitignore/c2043973f0fcbdb3da5d68c46f446fe41350480c/Go.gitignore'
ORIGINAL = Path('fixtures/base.bin').read_bytes()
UPDATED = Path('fixtures/target.bin').read_bytes()


def deploy(direct_deploy):
    return direct_deploy('contracts/delta_loom.py', sdk_version='v0.2.16')


def mock(vm, base=ORIGINAL, target=UPDATED, target_status=200):
    vm.clear_mocks()
    vm.mock_web(re.escape(BASE), {'status': 200, 'body': base})
    vm.mock_web(re.escape(TARGET), {'status': target_status, 'body': target})


def oracle(base, target):
    costs = [0]
    for end in range(1, len(target) + 1):
        cost = min(costs[start] + 3 + end - start for start in range(end))
        for start in range(end):
            if target[start:end] in base:
                cost = min(cost, costs[start] + 5)
        costs.append(cost)
    return costs[-1]


def test_actual_public_artifacts_and_correct_application(direct_vm, direct_deploy, direct_bob):
    contract = deploy(direct_deploy)
    assert contract.get_delta(BASE, TARGET) == {}
    direct_vm.sender = direct_bob
    mock(direct_vm)
    contract.synthesize(BASE, TARGET)
    delta = contract.get_delta(BASE, TARGET)
    assert delta['base_sha256'] == sha256(ORIGINAL).hexdigest()
    assert delta['target_sha256'] == sha256(UPDATED).hexdigest()
    assert delta['patch_bytes'] == oracle(ORIGINAL, UPDATED)
    assert contract.apply_delta(BASE, TARGET, ORIGINAL.hex()) == UPDATED.hex()
    assert direct_vm.run_validator() is True
    with direct_vm.expect_revert('Baseline does not match digest'):
        contract.apply_delta(BASE, TARGET, (b'X' + ORIGINAL[1:]).hex())
    with direct_vm.expect_revert('Delta already published'):
        contract.synthesize(BASE, TARGET)
    assert contract.get_delta(BASE, TARGET) == delta


@pytest.mark.parametrize(('base', 'target'), [
    (b'', b'abc'),
    (b'abc', b''),
    (b'hello', b'hello'),
    (b'ABCDE', b'xABCDEy'),
    (b'0123456789', b'6789012345'),
    (b'aabbccaabbcc', b'bbaabbcccaaabb'),
])
def test_edge_cases_match_exhaustive_oracle(direct_vm, direct_deploy, base, target):
    contract = deploy(direct_deploy)
    mock(direct_vm, base, target)
    contract.synthesize(BASE, TARGET)
    assert contract.get_delta(BASE, TARGET)['patch_bytes'] == oracle(base, target)
    assert contract.apply_delta(BASE, TARGET, base.hex()) == target.hex()
    assert direct_vm.run_validator() is True


def test_validator_rejects_a_correct_but_longer_patch_and_wrong_bytes(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    mock(direct_vm)
    contract.synthesize(BASE, TARGET)
    initial = contract.get_delta(BASE, TARGET)
    metadata = {key: value for key, value in initial.items() if key not in ('id','base_url','target_url')}
    literal = b'\x01' + len(UPDATED).to_bytes(2, 'big') + UPDATED
    assert direct_vm.run_validator(leader_result={**metadata, 'patch_hex': literal.hex(),
                                                'patch_bytes': len(literal)}) is False
    malformed = {**metadata, 'patch_hex': 'ff' + metadata['patch_hex'][2:]}
    assert direct_vm.run_validator(leader_result=malformed) is False
    mock(direct_vm, ORIGINAL, b'Z' + UPDATED[1:])
    assert direct_vm.run_validator() is False
    assert contract.get_delta(BASE, TARGET) == initial


@pytest.mark.parametrize(('data', 'status', 'message'), [
    (b'missing', 404, 'Artifact unavailable'),
    (b'X' * 1025, 200, 'Artifact exceeds byte limit'),
])
def test_unavailable_or_oversized_artifact_can_be_retried(direct_vm, direct_deploy, data, status, message):
    contract = deploy(direct_deploy)
    mock(direct_vm, target=data, target_status=status)
    with direct_vm.expect_revert(message):
        contract.synthesize(BASE, TARGET)
    assert contract.get_delta(BASE, TARGET) == {}
    mock(direct_vm)
    contract.synthesize(BASE, TARGET)
    assert contract.apply_delta(BASE, TARGET, ORIGINAL.hex()) == UPDATED.hex()


@pytest.mark.parametrize('target', [
    'https://raw.githubusercontent.com/github/gitignore/main/Go.gitignore',
    'https://raw.githubusercontent.com/github/gitignore/c2043973f0fcbdb3da5d68c46f446fe41350480c/../Go.gitignore',
    'https://example.com/Go.gitignore',
])
def test_moving_or_untrusted_url_cannot_publish(direct_vm, direct_deploy, target):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert('Expected a commit-pinned raw GitHub file'):
        contract.synthesize(BASE, target)
