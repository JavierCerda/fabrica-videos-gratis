const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const key = 'a'.repeat(64);
const expectedChannel = 'UCuMX_olnpHMCr06FQBdCzjQ';
const properties = {};
let uploads = 0;
let channels = [{id: expectedChannel, snippet: {title: 'Test'}, contentDetails: {relatedPlaylists: {uploads: 'playlist'}}}];
let failInsert = false;
let status = {privacyStatus: 'private'};
const ctx = vm.createContext({console, Buffer, Date,
  Utilities: {
    computeHmacSha256Signature: (text, secret) => crypto.createHmac('sha256', secret).update(text).digest(),
    base64EncodeWebSafe: value => Buffer.from(value).toString('base64url'),
    base64Decode: value => [...Buffer.from(value, 'base64')],
    newBlob: (bytes, type, name) => ({bytes, type, name}),
    formatDate: () => '2026-11-19'
  },
  YouTube: {
    Channels: {list: () => ({items: channels})},
    PlaylistItems: {list: () => ({items: []})},
    Videos: {
      insert: (body, part, blob, options) => {uploads++; assert.equal(options.notifySubscribers, false);
        assert.equal(body.status.privacyStatus, 'private'); assert.equal(body.status.containsSyntheticMedia, true);
        if (failInsert) throw new Error('network'); return {id: 'test-video'};},
      list: () => ({items: [{id: 'test-video', snippet: {title: 'Test'}, status}]})
    }
  }
});
vm.runInContext(source, ctx);
const props = {getProperty: k => properties[k], setProperty: (k,v) => properties[k]=v,
  setProperties: values => Object.assign(properties, values)};
function signed(value) {const payload = JSON.stringify(value); return {payload,
  signature: crypto.createHmac('sha256', key).update(payload).digest('base64url')};}
const request = {timestamp: 1000, nonce: 'b'.repeat(32), channel_id: expectedChannel, action: 'readiness'};
assert.equal(ctx.authenticate_(signed(request),1000,key).action,'readiness');
assert.throws(()=>ctx.authenticate_(signed(request),1301,key),/UNAUTHORIZED/);
assert.throws(()=>ctx.authenticate_(signed(request),1000,''),/NOT_CONFIGURED/);
assert.throws(()=>ctx.authenticate_({...signed(request),signature:'c'.repeat(43)},1000,key),/UNAUTHORIZED/);
assert.throws(()=>ctx.authenticate_(signed({...request,channel_id:'other'}),1000,key),/UNAUTHORIZED/);
assert.throws(()=>ctx.authenticate_(signed({...request,action:'delete'}),1000,key),/BAD_ACTION/);
channels=[]; assert.throws(()=>ctx.channel_(),/WRONG_CHANNEL/);
channels=[{id:expectedChannel,snippet:{title:'Test'},contentDetails:{relatedPlaylists:{uploads:'playlist'}}}];
const videoKey = 'd'.repeat(24);
const upload = {...request, action: 'upload', key: videoKey, notify: false,
  body: {snippet: {title:'Test',description:'Test',tags:['fvg-'+videoKey],categoryId:'20'},status:{privacyStatus:'private'}},
  video_base64: Buffer.from([0,0,0,16,102,116,121,112,0,0,0,0]).toString('base64')};
assert.throws(()=>ctx.validateUpload_({...upload,notify:true}),/PRIVATE_TEST_ONLY/);
const publicBody = structuredClone(upload); publicBody.body.status.publishAt='2026-11-20T12:00:00Z';
assert.throws(()=>ctx.validateUpload_(publicBody),/PRIVATE_TEST_ONLY/);
assert.throws(()=>ctx.validateUpload_({...upload,video_base64:Buffer.from('not mp4 contents').toString('base64')}),/BAD_MEDIA/);
assert.equal(ctx.handle_(upload,props).private_verified,true);
assert.equal(uploads,1);
ctx.handle_(upload,props); assert.equal(uploads,1,'no repetir insert cuando existe video_id');
const uncertain={...upload,key:'e'.repeat(24),body:structuredClone(upload.body)};
uncertain.body.snippet.tags=['fvg-'+uncertain.key]; failInsert=true;
assert.throws(()=>ctx.handle_(uncertain,props),/network/);
assert.throws(()=>ctx.handle_(uncertain,props),/UNCERTAIN_UPLOAD_DO_NOT_RETRY/);
assert.equal(uploads,2,'no repetir insert tras fallo incierto'); failInsert=false;
status={privacyStatus:'public'};
assert.throws(()=>ctx.privateResult_('test-video'),/UNVERIFIED_PRIVACY/);
console.log('Apps Script: autenticación, canal, medios, privacidad y deduplicación verificados');
