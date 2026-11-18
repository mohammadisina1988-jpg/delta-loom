# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from hashlib import sha256
import json
import re


LIMIT = 1024
RAW_COMMIT_URL = (
    r'https://raw\.githubusercontent\.com/[A-Za-z0-9-]{1,39}/'
    r'[A-Za-z0-9_.-]{1,100}/[0-9a-f]{40}/[A-Za-z0-9_./-]+'
)


def fail(reason):
    raise gl.vm.UserError(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def identifier(base_url, target_url):
    for url in (base_url, target_url):
        if (len(url) > 240 or re.fullmatch(RAW_COMMIT_URL, url) is None
                or any(part in ('', '.', '..') for part in url[8:].split('/'))):
            fail('Expected a commit-pinned raw GitHub file')
    return sha256((base_url + '\0' + target_url).encode()).hexdigest()


def download(url):
    response = gl.nondet.web.get(url)
    if response.status != 200:
        fail('Artifact unavailable')
    if len(response.body) > LIMIT:
        fail('Artifact exceeds byte limit')
    return response.body


def u16(value):
    return value.to_bytes(2, 'big')


def optimize(base, target):
    """Backward costs with one rolling row of longest common prefixes."""
    n, m = len(target), len(base)
    costs = [0] * (n + 1)
    choices = [(0, 0, 0)] * n
    following = [0] * (m + 1)
    literal_end = n
    for index in range(n - 1, -1, -1):
        current = [0] * (m + 1)
        longest = 0
        for offset, value in enumerate(base):
            if target[index] == value:
                current[offset] = following[offset + 1] + 1
                longest = max(longest, current[offset])
        length = literal_end - index
        best = (3 + length + costs[literal_end], 1, -length, 0)
        if longest:
            stop = min(range(index + 1, index + longest + 1), key=lambda end: (costs[end], -end))
            width = stop - index
            origin = next(offset for offset, match in enumerate(current) if match >= width)
            best = min(best, (5 + costs[stop], 0, -width, origin))
        cost, op, negative_width, origin = best
        costs[index] = cost
        choices[index] = (op, -negative_width, origin)
        if costs[index] + index < costs[literal_end] + literal_end:
            literal_end = index
        following = current

    program = bytearray()
    cursor = 0
    while cursor < n:
        op, length, offset = choices[cursor]
        if op == 0:
            program.extend(b'\x00' + u16(offset) + u16(length))
        else:
            program.extend(b'\x01' + u16(length) + target[cursor:cursor + length])
        cursor += length
    return bytes(program)


def minimum_size(base, target):
    """Forward shortest path, using native substring search for copy bounds."""
    n = len(target)
    distances = [0] + [n + 3] * n
    literal_floor = 0
    for start in range(n + 1):
        if start:
            distances[start] = min(distances[start], literal_floor + 3 + start)
        literal_floor = min(literal_floor, distances[start] - start)
        low, high = 0, min(len(base), n - start) + 1
        while low + 1 < high:
            length = (low + high) // 2
            if base.find(target[start:start + length]) == -1:
                high = length
            else:
                low = length
        cost = distances[start] + 5
        for end in range(start + 1, start + low + 1):
            if cost < distances[end]:
                distances[end] = cost
    return distances[n]


def replay(base, program, size):
    cursor = 0
    result = bytearray()
    while cursor < len(program):
        tag = program[cursor]
        if tag == 0 and cursor + 5 <= len(program):
            offset = int.from_bytes(program[cursor + 1:cursor + 3], 'big')
            length = int.from_bytes(program[cursor + 3:cursor + 5], 'big')
            if offset + length > len(base):
                fail('Copy exceeds baseline')
            piece = base[offset:offset + length]
            cursor += 5
        elif tag == 1 and cursor + 3 <= len(program):
            length = int.from_bytes(program[cursor + 1:cursor + 3], 'big')
            end = cursor + 3 + length
            if end > len(program):
                fail('Truncated literal')
            piece = program[cursor + 3:end]
            cursor = end
        else:
            fail('Invalid patch opcode')
        if length == 0 or len(result) + length > size:
            fail('Invalid reconstructed size')
        result.extend(piece)
    if len(result) != size:
        fail('Invalid reconstructed size')
    return bytes(result)


def summary(base, target):
    return {'base_sha256': sha256(base).hexdigest(), 'base_size': len(base),
            'target_sha256': sha256(target).hexdigest(), 'target_size': len(target)}


def matches_patch(proposal, base, target):
    if not isinstance(proposal, dict):
        return False
    patch = proposal.get('patch_hex')
    actual = summary(base, target)
    if (not isinstance(patch, str) or len(patch) > 2 * (LIMIT + 3)
            or re.fullmatch(r'(?:[0-9a-f]{2})*', patch) is None
            or encode(proposal) != encode({**actual, 'patch_hex': patch, 'patch_bytes': len(patch) // 2})):
        return False
    program = bytes.fromhex(patch)
    return replay(base, program, len(target)) == target and len(program) == minimum_size(base, target)


def synthesize_delta(base_url, target_url):
    def acquire():
        return download(base_url), download(target_url)

    def lead():
        base, target = acquire()
        patch = optimize(base, target)
        return {**summary(base, target), 'patch_hex': patch.hex(), 'patch_bytes': len(patch)}

    def verify(proposal):
        try:
            base, target = acquire()
        except gl.vm.UserError as error:
            return not isinstance(proposal, gl.vm.Return) and getattr(proposal, 'message', None) == error.message
        except Exception:
            return False
        if not isinstance(proposal, gl.vm.Return):
            return False
        try:
            return matches_patch(proposal.calldata, base, target)
        except Exception:
            return False

    return gl.vm.run_nondet_unsafe(lead, verify)


class DeltaLoom(gl.Contract):
    deltas: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def synthesize(self, base_url: str, target_url: str) -> None:
        key = identifier(base_url, target_url)
        if key in self.deltas:
            fail('Delta already published')
        result = synthesize_delta(base_url, target_url)
        self.deltas[key] = encode({'id': key, 'base_url': base_url, 'target_url': target_url, **result})

    @gl.public.view
    def get_delta(self, base_url: str, target_url: str) -> dict:
        key = identifier(base_url, target_url)
        return json.loads(self.deltas[key]) if key in self.deltas else {}

    @gl.public.view
    def apply_delta(self, base_url: str, target_url: str, base_hex: str) -> str:
        record = self.get_delta(base_url, target_url)
        if not record:
            fail('Delta has not been published')
        if (len(base_hex) > 2 * LIMIT or not re.fullmatch(r'(?:[0-9a-f]{2})*', base_hex)
                or len(base_hex) != 2 * record['base_size']):
            fail('Invalid baseline encoding')
        base = bytes.fromhex(base_hex)
        if sha256(base).hexdigest() != record['base_sha256']:
            fail('Baseline does not match digest')
        restored = replay(base, bytes.fromhex(record['patch_hex']), record['target_size'])
        if sha256(restored).hexdigest() != record['target_sha256']:
            fail('Reconstructed target digest mismatch')
        return restored.hex()
