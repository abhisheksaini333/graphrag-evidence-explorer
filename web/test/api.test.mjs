import assert from 'node:assert/strict';
import test from 'node:test';
import {build} from 'esbuild';
const compiled=await build({entryPoints:['src/api.ts'],bundle:true,write:false,format:'esm'});
const {api}=await import('data:text/javascript;base64,'+Buffer.from(compiled.outputFiles[0].text).toString('base64'));

test('an empty overload response produces a usable status message',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>({ok:false,status:503,json:async()=>{throw new SyntaxError('empty body');}});
    await assert.rejects(api('/query',{}),/503/);
  }finally{globalThis.fetch=original;}
});
test('a malformed successful response is never treated as valid evidence',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>({ok:true,status:200,json:async()=>{throw new SyntaxError('bad body');}});
    await assert.rejects(api('/graph'),/unreadable/);
  }finally{globalThis.fetch=original;}
});
test('revision conflicts retain the server recovery instruction',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>({ok:false,status:409,json:async()=>({message:'Graph changed; reload before correcting'})});
    await assert.rejects(api('/corrections',{}),/reload before correcting/);
  }finally{globalThis.fetch=original;}
});
