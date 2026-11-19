/* Conexión opcional con OAuth gestionado por Google. Nunca devuelve tokens.
 * HMAC_KEY se guarda solo en Propiedades del script y GitHub Actions Secrets.
 * No desplegar ni conceder permisos sin aprobación del propietario.
 */
const EXPECTED_CHANNEL = 'UCuMX_olnpHMCr06FQBdCzjQ';
const MAX_VIDEO_BYTES = 32 * 1024 * 1024;
const PUBLICATION_ENABLED = true;

function comprobarCanal() {
  const channel = channel_();
  console.log(JSON.stringify({channel_id: channel.id, title: channel.snippet.title,
    publication_enabled: PUBLICATION_ENABLED, status: 'channel_verified'}));
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
  return json_({service: 'fabrica-videos-gratis', publication_enabled: PUBLICATION_ENABLED});
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
  if (!['readiness', 'markers', 'inspect', 'upload'].includes(value.action)) throw new Error('BAD_ACTION');
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
  if (body.status.privacyStatus !== 'private' || value.notify !== false)
    throw new Error('PRIVATE_TEST_ONLY');
  const requested = body.status.publishAt;
  if (requested) {
    if (!PUBLICATION_ENABLED) throw new Error('PUBLICATION_PAUSED');
    const when = Date.parse(requested);
    if (typeof requested !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(requested) ||
        !Number.isFinite(when) || when < Date.now() + 120000 || when > Date.now() + 7 * 86400000)
      throw new Error('BAD_SCHEDULE');
  }
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
    status: {privacyStatus: 'private', selfDeclaredMadeForKids: false, containsSyntheticMedia: true, embeddable: true,
      ...(requested ? {publishAt: requested} : {})}}};
}

function uploadResult_(videoId, requested, key) {
  const items = YouTube.Videos.list('snippet,status', {id: videoId}).items || [];
  if (items.length !== 1) throw new Error('UNVERIFIED_UPLOAD');
  const v = items[0];
  if (v.snippet.channelId !== EXPECTED_CHANNEL || !(v.snippet.tags || []).includes('fvg-' + key))
    throw new Error('UNVERIFIED_UPLOAD');
  const isPrivate = v.status.privacyStatus === 'private';
  const scheduled = !!requested && isPrivate && !!v.status.publishAt && Date.parse(v.status.publishAt) === Date.parse(requested);
  const published = !!requested && v.status.privacyStatus === 'public' && Date.parse(requested) <= Date.now();
  const privateVerified = !requested && isPrivate && !v.status.publishAt;
  if (!privateVerified && !scheduled && !published) throw new Error(requested ? 'UNVERIFIED_SCHEDULE' : 'UNVERIFIED_PRIVACY');
  return {video_id: v.id, url: 'https://www.youtube.com/watch?v=' + v.id,
    channel_id: EXPECTED_CHANNEL, title: v.snippet.title, status: v.status,
    requested_publish_at: requested || null, private_verified: privateVerified,
    schedule_verified: scheduled || published, public_verified: published};
}

function inspectUpload_(key, props, channel) {
  if (!/^[a-f0-9]{24}$/.test(key)) throw new Error('BAD_VIDEO');
  const raw = props.getProperty('upload_' + key);
  const record = raw ? JSON.parse(raw) : null;
  const id = record && record.video_id ? record.video_id : markers_(channel)[key];
  if (!id) return {found: false, uncertain: !!record};
  return {found: true, ...uploadResult_(id, record ? record.publish_at : null, key)};
}

function pruneConfirmed_(props, now) {
  // El historial editorial permanente está en production-state. Esta caché solo
  // conserva catorce días de confirmaciones; los intentos inciertos no caducan.
  const all = props.getProperties();
  Object.keys(all).filter(k => k.startsWith('upload_')).forEach(k => {
    const record = JSON.parse(all[k]);
    if (['private_test', 'scheduled'].includes(record.status) && record.video_id && record.confirmed_at &&
        Date.parse(record.confirmed_at) < now - 14 * 86400000) props.deleteProperty(k);
  });
}

function handle_(value, props) {
  const channel = channel_();
  if (value.action === 'readiness') return {channel_id: channel.id, title: channel.snippet.title,
    private_test_only: !PUBLICATION_ENABLED, publication_enabled: PUBLICATION_ENABLED, protocol_version: 2};
  if (value.action === 'markers') return markers_(channel);
  if (value.action === 'inspect') return inspectUpload_(value.key, props, channel);
  // Validar antes de consumir cuota o crear el registro de intento.
  const validated = validateUpload_(value);
  const journalKey = 'upload_' + value.key;
  const old = props.getProperty(journalKey);
  if (old) {
    const record = JSON.parse(old);
    if (record.video_id) return uploadResult_(record.video_id, record.publish_at, value.key);
    throw new Error('UNCERTAIN_UPLOAD_DO_NOT_RETRY');
  }
  const duplicate = markers_(channel)[value.key];
  if (duplicate) return uploadResult_(duplicate, null, value.key);
  const day = Utilities.formatDate(new Date(), 'America/Los_Angeles', 'yyyy-MM-dd');
  const count = Number(props.getProperty('quota_count') || '0');
  const used = props.getProperty('quota_day') === day ? count : 0;
  if (used >= 100) throw new Error('DAILY_UPLOAD_LIMIT');
  // Diario persistente previo al efecto remoto. Los fallos inciertos nunca repiten insert.
  const requested = validated.body.status.publishAt || null;
  props.setProperties({[journalKey]: JSON.stringify({status: 'uploading', publish_at: requested, started_at: new Date().toISOString()}),
    quota_day: day, quota_count: String(used + 1)}, false);
  const blob = Utilities.newBlob(validated.bytes, 'video/mp4', value.key + '.mp4');
  const video = YouTube.Videos.insert(validated.body, 'snippet,status', blob, {notifySubscribers: false});
  if (!video.id) throw new Error('UNVERIFIED_UPLOAD');
  props.setProperty(journalKey, JSON.stringify({status: 'received', publish_at: requested, video_id: video.id}));
  const result = uploadResult_(video.id, requested, value.key);
  props.setProperty(journalKey, JSON.stringify({status: requested ? 'scheduled' : 'private_test',
    publish_at: requested, video_id: video.id, confirmed_at: new Date().toISOString()}));
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
    pruneConfirmed_(props, Date.now());
    return json_({ok: true, result: handle_(value, props)});
  } catch (error) {
    // No incluir cuerpos, vídeos, firmas, claves ni tokens en respuesta o logs.
    const safe = ['NOT_CONFIGURED', 'BAD_REQUEST', 'UNAUTHORIZED', 'BAD_ACTION', 'WRONG_CHANNEL',
      'BAD_VIDEO', 'PRIVATE_TEST_ONLY', 'BAD_METADATA', 'BAD_MEDIA', 'UNVERIFIED_UPLOAD',
      'UNVERIFIED_PRIVACY', 'UNVERIFIED_SCHEDULE', 'PUBLICATION_PAUSED', 'BAD_SCHEDULE',
      'UNCERTAIN_UPLOAD_DO_NOT_RETRY', 'DAILY_UPLOAD_LIMIT', 'BUSY_DO_NOT_RETRY_UPLOAD', 'REPLAY'];
    return json_({ok: false, error: safe.includes(error.message) ? error.message : 'GOOGLE_API_ERROR_DO_NOT_RETRY_UPLOAD'});
  } finally {
    if (lock && lock.hasLock()) lock.releaseLock();
  }
}
