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
    names=('YT_CLIENT_ID','YT_CLIENT_SECRET','YT_REFRESH_TOKEN','YT_CHANNEL_ID')
    return {'ready':all(os.getenv(n) for n in names),'missing':[n for n in names if not os.getenv(n)]}


def quota_day(now):return now.astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat()


def remaining_uploads(state,now,limit):
    if state.get('quota_block_until') and timestamp(state['quota_block_until'])>now:return 0
    return max(0,limit-state.get('attempts',{}).get(quota_day(now),0))


def classify_upload_error(exc,now):
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
    earliest=now+dt.timedelta(minutes=4)
    value=max(earliest,timestamp(state['next_publish_at'])) if state.get('next_publish_at') else earliest
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
    status={'privacyStatus':'private','selfDeclaredMadeForKids':False,'containsSyntheticMedia':False,'embeddable':True}
    if publish_at:status['publishAt']=publish_at
    return {'snippet':{'title':title,'description':description[:4900],'tags':tags,'categoryId':'20',
        'defaultLanguage':'es','defaultAudioLanguage':'es'},
        'status':status}


class YouTubePublisher:
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
