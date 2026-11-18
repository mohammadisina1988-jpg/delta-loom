const fs = require('node:fs');
const {assert, equal, sourceHash, digest, invoke, read, rpc, receipt, receiptSummary, save, record, delay} = require('./transport.cjs');
const {decodeReceipt} = require('./receipt-calldata.cjs');

const baseUrl = 'https://raw.githubusercontent.com/github/gitignore/74cf7151d96a6eaacd4f66fd59b01a140036d857/Go.gitignore';
const targetUrl = 'https://raw.githubusercontent.com/github/gitignore/c2043973f0fcbdb3da5d68c46f446fe41350480c/Go.gitignore';
const missingUrl = targetUrl.replace(/Go\.gitignore$/, 'NoSuchDeltaLoomProofArtifact.bin');
const cases = [
  {label: 'forward', urls: [baseUrl, targetUrl]},
  {label: 'reverse', urls: [targetUrl, baseUrl]},
  {label: 'missing', urls: [baseUrl, missingUrl]}
];

async function getBytes(url, expectedStatus) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const response = await fetch(url, {signal: AbortSignal.timeout(18000)});
      assert(response.status === expectedStatus, 'Unexpected artifact HTTP ' + response.status);
      return Buffer.from(await response.arrayBuffer());
    } catch (error) {
      if (attempt === 2) throw error;
      await delay(3000);
    }
  }
}

function exhaustiveCost(base, target) {
  const costs = [0];
  for (let end = 1; end <= target.length; end++) {
    let best = Infinity;
    for (let start = end - 1; start >= 0; start--) {
      best = Math.min(best, costs[start] + 3 + end - start);
      if (base.includes(target.subarray(start, end))) best = Math.min(best, costs[start] + 5);
    }
    costs.push(best);
  }
  return costs.at(-1);
}

function decode(base, program) {
  const chunks = [];
  let at = 0;
  while (at < program.length) {
    const op = program[at++];
    if (op === 0) {
      const offset = program.readUInt16BE(at);
      const count = program.readUInt16BE(at + 2);
      assert(count > 0 && offset + count <= base.length, 'Copy outside source');
      chunks.push(base.subarray(offset, offset + count));
      at += 4;
    } else {
      assert(op === 1, 'Unknown opcode');
      const count = program.readUInt16BE(at);
      at += 2;
      assert(count > 0 && at + count <= program.length, 'Truncated literal');
      chunks.push(program.subarray(at, at + count));
      at += count;
    }
  }
  return Buffer.concat(chunks);
}

async function main() {
  const wallets = JSON.parse(process.env.DELTA_ACCOUNTS || '[]');
  assert(wallets.length === 2 && wallets[0].address !== wallets[1].address, 'Two wallets required');
  const [base, target] = await Promise.all([getBytes(baseUrl, 200), getBytes(targetUrl, 200), getBytes(missingUrl, 404)]);
  assert(base.equals(fs.readFileSync('fixtures/base.bin')) && target.equals(fs.readFileSync('fixtures/target.bin')),
    'Upstream bytes differ from pinned fixtures');
  const ref = new Map([[baseUrl, base], [targetUrl, target]]);
  assert(await rpc('eth_chainId', []) === '0xf22f', 'StudioNet only');
  const code = fs.readFileSync('contracts/delta_loom.py');
  process.env.DELTA_ACCOUNT = wallets[0].name;
  const resumed = process.env.DELTA_DEPLOYMENT;
  if (resumed) assert(/^0x[0-9a-f]{64}$/i.test(resumed), 'Invalid existing deployment hash');
  const deployment = resumed || await invoke('deploy', ['deploy', '--contract', 'contracts/delta_loom.py']);
  const deployed = await receipt('deploy', deployment, true);
  if (resumed) record('deploy', deployment);
  const contract = deployed.to_address || deployed.recipient;
  assert(/^0x[0-9a-f]{40}$/i.test(contract) && code.equals(Buffer.from(deployed.data.contract_code, 'base64')),
    'Deployed source mismatch');
  const report = {contract, deployment, resumed: Boolean(resumed), revision: process.env.GITHUB_SHA, source_sha256: sourceHash,
    fixtures: {base: digest(base), target: digest(target)}, deltas: {}, trace: []};

  async function verify(label, raw, actor, args, error) {
    const signer = (raw.from_address || raw.sender).toLowerCase();
    assert((actor === null || signer === wallets[actor].address)
      && (raw.to_address || raw.recipient).toLowerCase() === contract.toLowerCase(), 'Wrong receipt addresses');
    assert(equal(await decodeReceipt(raw), args), 'Wrong signed calldata');
    if (error) {
      const payload = Buffer.from(raw.consensus_data.leader_receipt[0].result, 'base64');
      assert(payload[0] === 1 && payload.subarray(1).toString() === error, 'Unexpected revert');
    }
    const state = {};
    for (const item of cases) {
      state[item.label] = await read(label + '-state-' + item.label,
        ['call', contract, 'get_delta', '--args', ...item.urls]);
      assert(equal(state[item.label], report.deltas[item.label] || {}), 'Unexpected persisted delta');
    }
    report.trace.push({label, ...receiptSummary(raw), signer, args, error: error || null, state});
    save('progress', report);
  }

  async function publish(label, item, actor, error) {
    process.env.DELTA_ACCOUNT = wallets[actor].name;
    const tx = await invoke(label, ['write', contract, 'synthesize', '--args', ...item.urls]);
    const raw = await receipt(label, tx, !error);
    if (!error) {
      const delta = await read(label + '-new', ['call', contract, 'get_delta', '--args', ...item.urls]);
      const [first, second] = item.urls;
      const left = ref.get(first);
      const right = ref.get(second);
      const patch = Buffer.from(delta.patch_hex, 'hex');
      assert(equal(delta, {id: digest(first + '\0' + second), base_url: first, target_url: second,
        base_sha256: digest(left), base_size: left.length, target_sha256: digest(right), target_size: right.length,
        patch_hex: patch.toString('hex'), patch_bytes: exhaustiveCost(left, right)}), 'Patch cost or metadata differs');
      assert(patch.length === delta.patch_bytes && decode(left, patch).equals(right), 'Independent patch replay differs');
      const restored = await read(label + '-apply',
        ['call', contract, 'apply_delta', '--args', ...item.urls, left.toString('hex')], output => output);
      assert(restored === right.toString('hex'), 'Onchain replay differs from upstream bytes');
      report.deltas[label] = delta;
    }
    await verify(label, raw, actor, {method: 'synthesize', args: item.urls}, error);
  }

  await verify('deploy', deployed, resumed ? null : 0, {args: []});
  await publish('forward', cases[0], 1);
  await publish('reverse', cases[1], 0);
  await publish('missing', cases[2], 1, 'Artifact unavailable');
  await publish('duplicate', cases[0], 0, 'Delta already published');
  assert(code.equals(Buffer.from(await rpc('gen_getContractCode', [contract]), 'base64')), 'Fresh code differs');
  save('verified', report);
  console.log(JSON.stringify({contract, deployment, receipts: report.trace.length,
    sizes: Object.fromEntries(Object.entries(report.deltas).map(([label, delta]) => [label, delta.patch_bytes]))}));
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
module.exports = {exhaustiveCost, decode};
