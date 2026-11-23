"""Publicación OAuth vinculada a un canal, SEO y recuperación sin duplicar subidas."""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo
from .editorial_queue import timestamp
from .gta_sources import game_label

UTC=dt.timezone.utc
SCOPES=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']


def readiness():
    from .youtube_bridge import bridge_selected,bridge_readiness
    if bridge_selected():return bridge_readiness()
    names=('YT_CLIENT_ID','YT_CLIENT_SECRET','YT_REFRESH_TOKEN','YT_CHANNEL_ID')
    return {'ready':all(os.getenv(n) for n in names),'missing':[n for n in names if not os.getenv(n)]}


def quota_day(now):return now.astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat()


def remaining_uploads(state,now,limit):
    if state.get('quota_block_until') and timestamp(state['quota_block_until'])>now:return 0
    # The channel limit can span midnight. Count attempts by actual upload time,
    # including private tests and uncertain results, rather than publication time.
    cutoff = now - dt.timedelta(hours=24)
    recent_attempts = sum(
        bool(record.get('started_at')) and cutoff < timestamp(record['started_at']) <= now
        for record in state.get('history', [])
    )
    daily_attempts = state.get('attempts', {}).get(quota_day(now), 0)
    return max(0, limit - max(recent_attempts, daily_attempts))


def classify_upload_error(exc,now):
    from .youtube_bridge import BridgeError

    if isinstance(exc, BridgeError):
        reasons_by_code = {
            'YOUTUBE_UPLOAD_LIMIT_EXCEEDED': 'uploadLimitExceeded',
            'YOUTUBE_API_QUOTA_EXCEEDED': 'quotaExceeded',
            'DAILY_UPLOAD_LIMIT': 'dailyLimitExceeded',
        }
        reasons = {reasons_by_code.get(exc.code)}
    else:
        try:
            error=json.loads(exc.content).get('error',{})
            reasons={item.get('reason') for item in error.get('errors',[])}
        except (AttributeError,TypeError,ValueError):return None
    if reasons&{'quotaExceeded','dailyLimitExceeded'}:
        local=now.astimezone(ZoneInfo('America/Los_Angeles'))
        tomorrow=dt.datetime.combine(local.date()+dt.timedelta(days=1),dt.time(),tzinfo=local.tzinfo)
        return tomorrow.astimezone(UTC).isoformat()
    if 'uploadLimitExceeded' in reasons:return (now+dt.timedelta(hours=24)).isoformat()
    return None


def next_slot(state,now,minutes):
    earliest=(now+dt.timedelta(minutes=4)).replace(microsecond=0)
    value=max(earliest,timestamp(state['next_publish_at'])) if state.get('next_publish_at') else earliest
    value=value.replace(microsecond=0)
    state['next_publish_at']=(value+dt.timedelta(minutes=minutes)).isoformat()
    return value.isoformat().replace('+00:00','Z')


def seo(topic,key,publish_at,config):
    label=game_label(topic['allowed_games'][0]);title=topic['title'].strip()
    if len(title)>90:raise ValueError('Título SEO demasiado largo')
    if 'gta' not in title.casefold() and 'grand theft auto' not in title.casefold():title=f'{label}: {title}'
    if len(title)>100:raise ValueError('Título SEO supera el límite de YouTube')
    tag='#GTA6' if topic['allowed_games'][0]=='gta6' else '#GTA'
    description=topic['summary'].strip()+'\n\n'
    if topic['content_type']=='news':description+='Noticia publicada el '+topic['published_at'][:10]+'.\n'
    description+=('Información verificada en español.' if topic.get('editorial_version',0)>=3 else 'Comentario y humor originales en español.')+' Narración sintética.\n\nFuentes:\n'+'\n'.join(topic['sources'])
    description+='\n\n'+tag+' #CuriosidadesGTA #Shorts'
    tags=list(dict.fromkeys([label,'GTA','Grand Theft Auto','curiosidades GTA','GTA español','Shorts','fvg-'+key]+topic.get('seo_tags',[])))
    tags=[t for t in tags if len(t)<=65][:15]
    status={'privacyStatus':'private','selfDeclaredMadeForKids':False,'containsSyntheticMedia':True,'embeddable':True}
    if publish_at:status['publishAt']=publish_at
    return {'snippet':{'title':title,'description':description[:4900],'tags':tags,'categoryId':'20',
        'defaultLanguage':'es','defaultAudioLanguage':'es'},
        'status':status}


class YouTubePublisher:
    private_test_only=False

    def __new__(cls,client=None):
        if client is None:
            from .youtube_bridge import bridge_selected,AppsScriptPublisher
            if bridge_selected():return AppsScriptPublisher()
        return super().__new__(cls)

    def __init__(self,client=None):
        if client is None:
            check=readiness()
            if not check['ready']:raise RuntimeError('Conexión de YouTube pendiente: '+', '.join(check['missing']))
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            creds=Credentials(None,refresh_token=os.environ['YT_REFRESH_TOKEN'],token_uri='https://oauth2.googleapis.com/token',
                client_id=os.environ['YT_CLIENT_ID'],client_secret=os.environ['YT_CLIENT_SECRET'],scopes=SCOPES)
            try:creds.refresh(Request())
            except Exception:raise RuntimeError('YouTube necesita reconectar la autorización OAuth') from None
            client=build('youtube','v3',credentials=creds,cache_discovery=False)
        self.client=client
        channels=self.client.channels().list(part='id,snippet,contentDetails',mine=True).execute().get('items',[])
        expected=os.getenv('YT_CHANNEL_ID','')
        matched=[c for c in channels if c['id']==expected]
        if len(matched)!=1:raise RuntimeError('El canal autorizado no coincide con el canal de destino configurado')
        self.channel=matched[0]

    def recent_markers(self):
        playlist=self.channel['contentDetails']['relatedPlaylists']['uploads']
        items=self.client.playlistItems().list(part='contentDetails',playlistId=playlist,maxResults=50).execute().get('items',[])
        if not items:return {}
        ids=','.join(i['contentDetails']['videoId'] for i in items)
        videos=self.client.videos().list(part='snippet,status',id=ids).execute().get('items',[])
        return {tag[4:]:v['id'] for v in videos for tag in v['snippet'].get('tags',[]) if tag.startswith('fvg-')}

    def inspect_upload(self,key,publish_at=None):
        video_id=self.recent_markers().get(key)
        if not video_id:return {'found':False}
        items=self.client.videos().list(part='snippet,status',id=video_id).execute().get('items',[])
        if len(items)!=1 or items[0]['snippet'].get('channelId')!=self.channel['id']:
            raise RuntimeError('No se pudo verificar el vídeo del canal autorizado')
        v=items[0];actual=v['status'];public=actual.get('privacyStatus')=='public'
        scheduled=bool(publish_at) and actual.get('privacyStatus')=='private' and bool(actual.get('publishAt')) and timestamp(actual['publishAt'])==timestamp(publish_at)
        released=bool(publish_at) and public and timestamp(publish_at)<=dt.datetime.now(UTC)
        return {'found':True,'video_id':video_id,'url':'https://www.youtube.com/watch?v='+video_id,
            'title':v['snippet']['title'],'status':actual,'channel_id':self.channel['id'],
            'private_verified':not publish_at and actual.get('privacyStatus')=='private' and not actual.get('publishAt'),
            'schedule_verified':scheduled or released,'public_verified':released}

    def upload(self,video,body,notify=False):
        from googleapiclient.http import MediaFileUpload
        request=self.client.videos().insert(part='snippet,status',body=body,notifySubscribers=notify,
            media_body=MediaFileUpload(str(video),mimetype='video/mp4',resumable=True,chunksize=8*1024*1024))
        result=None
        while result is None:_,result=request.next_chunk(num_retries=2)
        if not result.get('id'):raise RuntimeError('YouTube no devolvió un ID de vídeo')
        check=self.client.videos().list(part='status,snippet',id=result['id']).execute().get('items',[])
        if len(check)!=1:raise RuntimeError('Subida recibida, pero no se pudo verificar su estado')
        requested=body['status'].get('publishAt');actual=check[0]['status']
        return {'video_id':result['id'],'url':'https://www.youtube.com/watch?v='+result['id'],
            'status':check[0]['status'],'title':check[0]['snippet']['title'],
            'private_verified':not requested and actual.get('privacyStatus')=='private' and not actual.get('publishAt'),
            'schedule_verified':bool(requested) and check[0]['status'].get('privacyStatus')=='private' and
                bool(check[0]['status'].get('publishAt')) and
                timestamp(check[0]['status']['publishAt'])==timestamp(requested)}
