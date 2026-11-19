/* Conexión opcional con OAuth gestionado por Google. Nunca devuelve tokens.
 * HMAC_KEY se guarda solo en Propiedades del script y GitHub Actions Secrets.
 * No desplegar ni conceder permisos sin aprobación del propietario.
 */
const EXPECTED_CHANNEL = 'UCuMX_olnpHMCr06FQBdCzjQ';
const MAX_VIDEO_BYTES = 32 * 1024 * 1024;

function comprobarCanal() {
  const channel = channel_();
  console.log(JSON.stringify({channel_id: channel.id, title: channel.snippet.title,
    publication_enabled: false, status: 'channel_verified'}));
  return channel.id;
}

function channel_() {
  const items = YouTube.Channels.list('id,snippet,contentDetails', {mine: true}).items || [];
  const selected = items.filter(c => c.id === EXPECTED_CHANNEL);
  if (selected.length !== 1) throw new Error('WRONG_CHANNEL');
  return selected[0];
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return json_({service: 'fabrica-videos-gratis', publication_enabled: false});
}

function authenticate_(envelope, now, key) {
  if (!key || key.length < 43) throw new Error('NOT_CONFIGURED');
  if (!envelope || typeof envelope.payload !== 'string' || envelope.payload.length > 46 * 1024 * 1024)
    throw new Error('BAD_REQUEST');
  const expected = Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature(envelope.payload, key)).replace(/=+$/, '');
  const supplied = envelope.signature;
  let difference = typeof supplied === 'string' && supplied.length === expected.length ? 0 : 1;
  for (let i = 0; i < expected.length; i++) difference |= expected.charCodeAt(i) ^ String(supplied).charCodeAt(i);
  if (difference) throw new Error('UNAUTHORIZED');
  const value = JSON.parse(envelope.payload);
  if (!Number.isInteger(value.timestamp) || Math.abs(now - value.timestamp) > 300 ||
      !/^[a-f0-9]{32}$/.test(value.nonce) || value.channel_id !== EXPECTED_CHANNEL)
    throw new Error('UNAUTHORIZED');
  if (!['readiness', 'markers', 'upload'].includes(value.action)) throw new Error('BAD_ACTION');
  return value;
}

function markers_(channel) {
  const playlist = channel.contentDetails.relatedPlaylists.uploads;
  const items = YouTube.PlaylistItems.list('contentDetails', {playlistId: playlist, maxResults: 50}).items || [];
  if (!items.length) return {};
  const videos = YouTube.Videos.list('snippet', {id: items.map(i => i.contentDetails.videoId).join(',')}).items || [];
  const result = {};
  videos.forEach(v => (v.snippet.tags || []).forEach(tag => {
    if (/^fvg-[a-f0-9]{24}$/.test(tag)) result[tag.slice(4)] = v.id;
  }));
  return result;
}

function validateUpload_(value) {
  const body = value.body;
  if (!/^[a-f0-9]{24}$/.test(value.key) || !body || !body.snippet || !body.status)
    throw new Error('BAD_VIDEO');
  if (body.status.privacyStatus !== 'private' || body.status.publishAt || value.notify !== false)
    throw new Error('PRIVATE_TEST_ONLY');
  const snippet = body.snippet;
  if (typeof snippet.title !== 'string' || !snippet.title.trim() || snippet.title.length > 100 ||
      typeof snippet.description !== 'string' || snippet.description.length > 5000 ||
      !Array.isArray(snippet.tags) || snippet.tags.length > 15 ||
      !snippet.tags.every(t => typeof t === 'string' && t.length <= 65) ||
      !snippet.tags.includes('fvg-' + value.key) || snippet.categoryId !== '20') throw new Error('BAD_METADATA');
  if (typeof value.video_base64 !== 'string' || value.video_base64.length > Math.ceil(MAX_VIDEO_BYTES / 3) * 4 ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(value.video_base64)) throw new Error('BAD_MEDIA');
  const bytes = Utilities.base64Decode(value.video_base64);
  if (bytes.length < 12 || bytes.length > MAX_VIDEO_BYTES ||
      String.fromCharCode.apply(null, bytes.slice(4, 8)) !== 'ftyp') throw new Error('BAD_MEDIA');
  return {bytes: bytes, body: {snippet: {title: snippet.title, description: snippet.description,
    tags: snippet.tags, categoryId: '20', defaultLanguage: 'es', defaultAudioLanguage: 'es'},
    status: {privacyStatus: 'private', selfDeclaredMadeForKids: false, containsSyntheticMedia: true, embeddable: true}}};
}

function privateResult_(videoId) {
  const items = YouTube.Videos.list('snippet,status', {id: videoId}).items || [];
  if (items.length !== 1) throw new Error('UNVERIFIED_UPLOAD');
  const v = items[0];
  const verified = v.status.privacyStatus === 'private' && !v.status.publishAt;
  if (!verified) throw new Error('UNVERIFIED_PRIVACY');
  return {video_id: v.id, url: 'https://www.youtube.com/watch?v=' + v.id,
    title: v.snippet.title, status: v.status, private_verified: true, schedule_verified: false};
}

function handle_(value, props) {
  const channel = channel_();
  if (value.action === 'readiness') return {channel_id: channel.id, title: channel.snippet.title, private_test_only: true};
  if (value.action === 'markers') return markers_(channel);
  // Validar antes de consumir cuota o crear el registro de intento.
  const validated = validateUpload_(value);
  const journalKey = 'upload_' + value.key;
  const old = props.getProperty(journalKey);
  if (old) {
    const record = JSON.parse(old);
    if (record.video_id) return privateResult_(record.video_id);
    throw new Error('UNCERTAIN_UPLOAD_DO_NOT_RETRY');
  }
  const duplicate = markers_(channel)[value.key];
  if (duplicate) return privateResult_(duplicate);
  const day = Utilities.formatDate(new Date(), 'America/Los_Angeles', 'yyyy-MM-dd');
  const count = Number(props.getProperty('quota_count') || '0');
  const used = props.getProperty('quota_day') === day ? count : 0;
  if (used >= 100) throw new Error('DAILY_UPLOAD_LIMIT');
  // Diario persistente previo al efecto remoto. Los fallos inciertos nunca repiten insert.
  props.setProperties({[journalKey]: JSON.stringify({status: 'uploading', started_at: new Date().toISOString()}),
    quota_day: day, quota_count: String(used + 1)}, false);
  const blob = Utilities.newBlob(validated.bytes, 'video/mp4', value.key + '.mp4');
  const video = YouTube.Videos.insert(validated.body, 'snippet,status', blob, {notifySubscribers: false});
  if (!video.id) throw new Error('UNVERIFIED_UPLOAD');
  props.setProperty(journalKey, JSON.stringify({status: 'received', video_id: video.id}));
  const result = privateResult_(video.id);
  props.setProperty(journalKey, JSON.stringify({status: 'private_test', video_id: video.id}));
  return result;
}

function doPost(e) {
  let lock;
  try {
    if (!e || !e.postData || e.postData.contents.length > 46 * 1024 * 1024) throw new Error('BAD_REQUEST');
    const props = PropertiesService.getScriptProperties();
    const value = authenticate_(JSON.parse(e.postData.contents), Math.floor(Date.now() / 1000), props.getProperty('HMAC_KEY'));
    lock = LockService.getScriptLock();
    if (!lock.tryLock(1000)) throw new Error('BUSY_DO_NOT_RETRY_UPLOAD');
    const nonceKey = 'nonce_' + value.nonce;
    const now = Math.floor(Date.now() / 1000);
    const all = props.getProperties();
    if (all[nonceKey]) throw new Error('REPLAY');
    Object.keys(all).filter(k => k.startsWith('nonce_') && Number(all[k]) < now - 600)
      .forEach(k => props.deleteProperty(k));
    props.setProperty(nonceKey, String(now));
    return json_({ok: true, result: handle_(value, props)});
  } catch (error) {
    // No incluir cuerpos, vídeos, firmas, claves ni tokens en respuesta o logs.
    const safe = ['NOT_CONFIGURED', 'BAD_REQUEST', 'UNAUTHORIZED', 'BAD_ACTION', 'WRONG_CHANNEL',
      'BAD_VIDEO', 'PRIVATE_TEST_ONLY', 'BAD_METADATA', 'BAD_MEDIA', 'UNVERIFIED_UPLOAD',
      'UNVERIFIED_PRIVACY', 'UNCERTAIN_UPLOAD_DO_NOT_RETRY', 'DAILY_UPLOAD_LIMIT', 'BUSY_DO_NOT_RETRY_UPLOAD', 'REPLAY'];
    return json_({ok: false, error: safe.includes(error.message) ? error.message : 'GOOGLE_API_ERROR_DO_NOT_RETRY_UPLOAD'});
  } finally {
    if (lock && lock.hasLock()) lock.releaseLock();
  }
}
