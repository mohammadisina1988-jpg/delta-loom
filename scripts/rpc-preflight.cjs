// Retry only this read-only RPC. Never replay a signed send or an entire CLI command.
function retryPreflight(fetchImpl,{pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),attempts=3,warn=console.warn}={}){
 return async function(input,options){
  let request;
  try{request=JSON.parse(options?.body);}catch{}
  const allowed=String(input)==='https://studio.genlayer.com/api'&&options?.method==='POST'&&request?.method==='eth_gasPrice'&&!Array.isArray(request);
  if(!allowed)return fetchImpl(input,options);
  for(let attempt=1;attempt<=attempts;attempt++){
   try{
    const response=await fetchImpl(input,options);
    if(!response.ok)throw Error('Gas-price preflight HTTP '+response.status);
    await response.clone().json();
    return response;
   }catch(error){
    if(attempt===attempts)throw error;
    warn('Retry read-only eth_gasPrice preflight '+attempt+'/'+attempts);
    await pause(7000*attempt);
   }
  }
 };
}
function retryLongStudioRead(fetchImpl) {
  return async (input, options) => {
    const response = await fetchImpl(input, options);
    if (String(input) !== 'https://studio.genlayer.com/api' || options?.method !== 'POST') return response;
    let request;
    try { request = JSON.parse(options.body); } catch { return response; }
    const call = request?.params?.[0];
    if (request?.method !== 'gen_call' || call?.type !== 'read'
      || !/^0xf9[0-9a-f]{4}b9(?:[0-9a-f]{2})+00$/i.test(call.data)) return response;
    let failure;
    try { failure = (await response.clone().json()).error; } catch { return response; }
    if (failure?.code !== -32603 || !/^RLP string ends with \d+ superfluous bytes$/.test(failure.message)) {
      return response;
    }
    const bytes = Buffer.from(call.data.slice(2), 'hex');
    const size = bytes.readUInt16BE(4);
    if (bytes.readUInt16BE(1) !== bytes.length - 3 || size !== bytes.length - 7
      || bytes[bytes.length - 2] <= 1) return response;
    // StudioNet's legacy decoder also accepts bare calldata ending in a non-flag byte.
    call.data = '0x' + bytes.subarray(6, -1).toString('hex');
    return fetchImpl(input, {...options, body: JSON.stringify(request)});
  };
}
module.exports={retryPreflight, retryLongStudioRead};
