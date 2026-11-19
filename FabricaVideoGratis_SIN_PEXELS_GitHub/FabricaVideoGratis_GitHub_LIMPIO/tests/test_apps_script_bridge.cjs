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
let overrideStatus = null;
let overrideChannel = null;
const videos = {};
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
      insert: (body, part, blob, options) => {
        uploads++; assert.equal(options.notifySubscribers, false);
        assert.equal(body.status.privacyStatus, 'private');
        assert.equal(body.status.containsSyntheticMedia, true);
        if (failInsert) throw new Error('network');
        const id = 'video' + String(uploads).padStart(6, '0');
        videos[id] = {id, snippet: {...body.snippet, channelId: expectedChannel}, status: {...body.status}};
        return {id};
      },
      list: (part, args) => ({items: videos[args.id] ? [{...videos[args.id],
        snippet: {...videos[args.id].snippet, channelId: overrideChannel || expectedChannel},
        status: overrideStatus || videos[args.id].status}] : []})
    }
  }
});
vm.runInContext(source, ctx);
const props = {getProperty: k => properties[k], setProperty: (k,v) => properties[k]=v,
  setProperties: values => Object.assign(properties, values),getProperties:()=>({...properties}),
  deleteProperty:k=>delete properties[k]};
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
assert.equal(ctx.handle_(request,props).publication_enabled,true);
assert.equal(ctx.handle_(request,props).private_test_only,false);
const videoKey = 'd'.repeat(24);
const upload = {...request, action: 'upload', key: videoKey, notify: false,
  body: {snippet: {title:'Test',description:'Test',tags:['fvg-'+videoKey],categoryId:'20'},status:{privacyStatus:'private'}},
  video_base64: Buffer.from([0,0,0,16,102,116,121,112,0,0,0,0]).toString('base64')};
assert.throws(()=>ctx.validateUpload_({...upload,notify:true}),/PRIVATE_TEST_ONLY/);
const directPublic=structuredClone(upload);directPublic.body.status.privacyStatus='public';
assert.throws(()=>ctx.validateUpload_(directPublic),/PRIVATE_TEST_ONLY/);
assert.throws(()=>ctx.validateUpload_({...upload,video_base64:Buffer.from('not mp4 contents').toString('base64')}),/BAD_MEDIA/);
const first=ctx.handle_(upload,props);
assert.equal(first.private_verified,true);assert.equal(first.schedule_verified,false);
assert.equal(uploads,1);
ctx.handle_(upload,props);assert.equal(uploads,1,'no repetir insert cuando existe video_id');
const scheduled=structuredClone(upload);scheduled.key='f'.repeat(24);scheduled.body.snippet.tags=['fvg-'+scheduled.key];
scheduled.body.status.publishAt=new Date(Date.now()+600000).toISOString();
const result=ctx.handle_(scheduled,props);
assert.equal(result.schedule_verified,true);assert.equal(result.private_verified,false);
assert.equal(result.status.publishAt,scheduled.body.status.publishAt);
ctx.handle_(scheduled,props);assert.equal(uploads,2,'no duplicar una programación');
const lookup=ctx.handle_({...request,action:'inspect',key:scheduled.key},props);
assert.equal(lookup.found,true);assert.equal(lookup.schedule_verified,true);assert.equal(uploads,2,'inspect nunca inserta');
assert.equal(ctx.handle_({...request,action:'inspect',key:'0'.repeat(24)},props).found,false);
for(const bad of [new Date(Date.now()-600000).toISOString(),new Date(Date.now()+30000).toISOString(),new Date(Date.now()+8*86400000).toISOString(),'2026-12-30']) {
  const invalid=structuredClone(scheduled);invalid.body.status.publishAt=bad;
  assert.throws(()=>ctx.validateUpload_(invalid),/BAD_SCHEDULE/);
}
overrideStatus={privacyStatus:'private',publishAt:new Date(Date.now()+900000).toISOString()};
assert.throws(()=>ctx.uploadResult_(result.video_id,scheduled.body.status.publishAt,scheduled.key),/UNVERIFIED_SCHEDULE/);
overrideStatus={privacyStatus:'public'};
assert.throws(()=>ctx.uploadResult_(result.video_id,scheduled.body.status.publishAt,scheduled.key),/UNVERIFIED_SCHEDULE/);
assert.throws(()=>ctx.uploadResult_(first.video_id,null,videoKey),/UNVERIFIED_PRIVACY/);
const released=ctx.uploadResult_(result.video_id,new Date(Date.now()-600000).toISOString(),scheduled.key);
assert.equal(released.public_verified,true);
overrideStatus=null;overrideChannel='other-channel';
assert.throws(()=>ctx.uploadResult_(first.video_id,null,videoKey),/UNVERIFIED_UPLOAD/);overrideChannel=null;
const uncertain=structuredClone(upload);uncertain.key='e'.repeat(24);uncertain.body.snippet.tags=['fvg-'+uncertain.key];failInsert=true;
assert.throws(()=>ctx.handle_(uncertain,props),/network/);
assert.throws(()=>ctx.handle_(uncertain,props),/UNCERTAIN_UPLOAD_DO_NOT_RETRY/);
assert.equal(uploads,3,'no repetir insert tras fallo incierto');failInsert=false;
assert.equal(ctx.handle_({...request,action:'inspect',key:uncertain.key},props).uncertain,true);
properties.quota_count='100';properties.quota_day='2026-11-19';
const limited=structuredClone(upload);limited.key='1'.repeat(24);limited.body.snippet.tags=['fvg-'+limited.key];
assert.throws(()=>ctx.handle_(limited,props),/DAILY_UPLOAD_LIMIT/);assert.equal(properties['upload_'+limited.key],undefined);
const paused=vm.createContext({Date,Number});vm.runInContext(source.replace('const PUBLICATION_ENABLED = true;','const PUBLICATION_ENABLED = false;'),paused);
assert.throws(()=>paused.validateUpload_(scheduled),/PUBLICATION_PAUSED/);
const old=new Date(Date.now()-15*86400000).toISOString();
properties.upload_old=JSON.stringify({status:'scheduled',video_id:'old-id',confirmed_at:old});
properties.upload_unknown=JSON.stringify({status:'uploading',started_at:old});
ctx.pruneConfirmed_(props,Date.now());
assert.equal(properties.upload_old,undefined);
assert.ok(properties.upload_unknown,'el diario incierto nunca caduca');
assert.ok(properties['upload_'+scheduled.key],'la confirmación reciente se conserva');
console.log('Apps Script: HMAC, canal, fechas, pausa, cuota, privacidad, programación y recuperación sin duplicados verificados');
