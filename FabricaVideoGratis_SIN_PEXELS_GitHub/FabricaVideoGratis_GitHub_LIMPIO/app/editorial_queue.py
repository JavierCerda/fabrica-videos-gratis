"""Cola editorial: fechas reales, fuentes verificadas y prevención de repeticiones."""
import datetime as dt
import hashlib
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from .neural_voice import spoken_tokens
from .quality import SWEARS

UTC=dt.timezone.utc
RESEARCH_HOSTS={'www.rockstargames.com','support.rockstargames.com','media.rockstargames.com',
    'media-rockstargames-com.akamaized.net','store.steampowered.com',
    'news.xbox.com','blog.playstation.com','www.playstation.com','www.nintendo.com',
    'ir.take2games.com','www.take2games.com','www.reuters.com','apnews.com',
    'www.guinnessworldrecords.com','www.thegameawards.com','thegameawards.com'}


def timestamp(value):
    result=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Fecha sin zona horaria')
    return result.astimezone(UTC)


def normalized(text):
    return ' '.join(spoken_tokens(text))


def signature(topic):
    return hashlib.sha256(normalized(' '.join(topic['editorial']['facts'])).encode()).hexdigest()[:24]


def similar(a,b):
    stop={'de','la','el','los','las','en','un','una','y','que','del','con','por','para','gta','grand','theft','auto'}
    x=set(normalized(a).split())-stop;y=set(normalized(b).split())-stop
    return bool(x and y and len(x&y)/max(1,min(len(x),len(y)))>=.8)


def validate_editorial_style(topic):
    """Límites legibles y decisiones visuales explícitas para el perfil nuevo."""
    from .smooth_media import visual_identity
    text=' '.join(b['narration'] for b in topic['beats'])
    sentences=[s for s in re.split(r'[.!?¡¿]+',text) if spoken_tokens(s)]
    if any(len(spoken_tokens(s))>22 for s in sentences):
        raise ValueError('Simplificar: frase con más de 22 palabras')
    if len(spoken_tokens(text))/max(1,len(sentences))>14:
        raise ValueError('Simplificar: frases demasiado largas en conjunto')
    if not topic.get('media_review',{}).get('subject'):
        raise ValueError('Falta revisión del tema visual')
    identities=set()
    for beat in topic['beats']:
        for visual in beat['visuals']:
            if not visual.get('subject') or not visual.get('relevance'):
                raise ValueError('Explicar qué muestra cada medio y su relación con este bloque')
            if visual.get('kind')=='video' and visual.get('max_seconds',0)<3.3:
                raise ValueError('Clip demasiado corto para un plano fluido, sin bucles')
            identities.add(visual_identity(visual))
    if len(identities)<3:raise ValueError('Se necesitan al menos tres medios o fragmentos distintos relacionados')


def validate_topic(topic,now,config):
    from .gta_sources import GAMES
    from .studio import validate_visual
    if not re.fullmatch('[a-z0-9-]{8,90}',topic['id']):raise ValueError('ID editorial inválido')
    if topic.get('format')!='comedia_es' or topic.get('editorial_status')!='approved_fact':raise ValueError('Guion no aprobado')
    if len(topic['allowed_games'])!=1 or topic['allowed_games'][0] not in {*GAMES,'gta6'}:raise ValueError('Juego sin catálogo visual revisado')
    if not 1<=len(topic['display_title'])<=65 or len(topic['title'])>90:raise ValueError('Título fuera del formato')
    if len(topic['beats'])!=5:raise ValueError('El Short debe tener cinco bloques')
    if topic.get('editorial_version',0)>=2:validate_editorial_style(topic)
    text=' '.join(b['narration'] for b in topic['beats']);words=spoken_tokens(text)
    if not 95<=len(words)<=125:raise ValueError(f'Longitud inesperada: {len(words)} palabras')
    if sum(w in SWEARS for w in words)<8:raise ValueError('Falta el tono de comedia adulta solicitado')
    for beat in topic['beats']:
        if not beat.get('visuals'):raise ValueError('Bloque sin medios')
        for visual in beat['visuals']:validate_visual(topic,visual)
    research=topic['research'];reviewed=timestamp(research['verified_at'])
    if not now-dt.timedelta(hours=config['research_max_age_hours'])<=reviewed<=now+dt.timedelta(minutes=5):
        raise ValueError('La investigación ya no es reciente')
    if not topic['editorial']['facts'] or not topic['editorial'].get('jokes'):raise ValueError('Faltan hechos o chistes separados')
    sources=research['sources']
    if not sources or {s['url'] for s in sources}!=set(topic['sources']):raise ValueError('Fuentes sin correspondencia')
    for source in sources:
        parsed=urlparse(source['url'])
        if parsed.scheme!='https' or parsed.hostname not in RESEARCH_HOSTS:raise ValueError('Fuente no admitida')
        if not source.get('supported_facts'):raise ValueError('La fuente no respalda ningún hecho')
        if any(f not in topic['editorial']['facts'] for f in source['supported_facts']):raise ValueError('Hecho sin correspondencia')
    if set(topic['editorial']['facts'])!={f for s in sources for f in s['supported_facts']}:raise ValueError('Hay hechos sin fuente')
    if topic['content_type']=='news':
        published=timestamp(topic['published_at'])
        if published>now+dt.timedelta(minutes=5):raise ValueError('Noticia del futuro')
        if published.astimezone(ZoneInfo(config['timezone'])).date()!=now.astimezone(ZoneInfo(config['timezone'])).date():
            raise ValueError('Una noticia de otro día no se presenta como novedad de hoy')
        if not any(s.get('published_at')==topic['published_at'] for s in sources):raise ValueError('Fecha de noticia sin fuente')
    elif topic['content_type']!='evergreen':raise ValueError('Tipo editorial inválido')
    if re.search(r'\b(hoy|mañana|ayer|esta noche|esta semana)\b',text,re.I):
        raise ValueError('Usar fechas explícitas para que la narración no caduque en la cola')
    return topic


def ingest(state,packet,now,config):
    if packet.get('schema_version')!=1:raise ValueError('Formato de bandeja desconocido')
    topics=packet['topics']
    if len(topics)>config['batch_size']:raise ValueError('Demasiados guiones en el lote')
    pending=state.setdefault('pending',[]);seen=state.setdefault('history',[]);report=[]
    for topic in topics:
        try:validate_topic(topic,now,config)
        except (ValueError,KeyError,TypeError) as exc:
            report.append({'id':topic.get('id'),'status':'rejected','reason':str(exc)});continue
        facts=' '.join(topic['editorial']['facts']);key=signature(topic)
        previous=next((t for t in pending if signature(t)==key),None)
        if previous and topic.get('editorial_version',0)>previous.get('editorial_version',0) and not any(r.get('key')==key for r in seen):
            # Revisar un borrador pendiente conserva su posición y nunca repite una subida.
            pending[pending.index(previous)]={**topic,'queue_key':key,'queued_at':previous['queued_at']}
            report.append({'id':topic['id'],'status':'revised'});continue
        records=seen+[{'key':signature(t),'facts':' '.join(t['editorial']['facts']),'source_urls':t['sources'],'kind':t['content_type']} for t in pending]
        duplicate=any(r.get('key')==key or similar(facts,r.get('facts','')) or
            (topic['content_type']=='news' and r.get('kind')=='news' and set(topic['sources'])&set(r.get('source_urls',[]))) for r in records)
        if duplicate:report.append({'id':topic['id'],'status':'duplicate'});continue
        if len(pending)>=config['queue_limit']:report.append({'id':topic['id'],'status':'queue_full'});continue
        topic={**topic,'queue_key':key,'queued_at':now.isoformat()};pending.append(topic)
        report.append({'id':topic['id'],'status':'queued'})
    return report


def select_pending(state,now,config):
    alive=[]
    for t in state.get('pending',[]):
        if t['content_type']=='news' and now-timestamp(t['published_at'])>dt.timedelta(hours=config['news_expiry_hours']):
            state.setdefault('expired',[]).append({'id':t['id'],'reason':'news_expired'});continue
        alive.append(t)
    state['pending']=alive
    eligible=[t for t in alive if t.get('editorial_version',0)>=config.get('editorial_version',0)]
    return sorted(eligible,key=lambda t:(t['content_type']!='news',-timestamp(t.get('published_at',t['queued_at'])).timestamp()))[:config['batch_size']]
