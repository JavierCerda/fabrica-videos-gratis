"""Fuentes del editor y búsqueda de ideas de GTA; sin claves ni scraping de vídeos ajenos."""
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image
from bs4 import BeautifulSoup
from .pipeline import ROOT, UA, log

GAMES = {
    'gta3': (1546970,'Grand Theft Auto III'),
    'vicecity': (1546990,'Grand Theft Auto: Vice City'),
    'sanandreas': (1547000,'Grand Theft Auto: San Andreas'),
    'gta4': (12210,'Grand Theft Auto IV'),
    'episodes': (12220,'Grand Theft Auto: Episodes from Liberty City'),
    'gta5': (271590,'Grand Theft Auto V'),
}
IMAGE_HOSTS = {'shared.akamai.steamstatic.com','shared.fastly.steamstatic.com',
               'shared.cloudflare.steamstatic.com','cdn.akamai.steamstatic.com','cdn.cloudflare.steamstatic.com'}
GTA6_GALLERY='https://www.rockstargames.com/VI/media/screenshots'


@lru_cache(maxsize=1)
def gta6_gallery():
    response=requests.get(GTA6_GALLERY,headers={'User-Agent':UA},timeout=(15,40));response.raise_for_status()
    paths=sorted(set(re.findall(r'/VI/_next/static/media/[^"<>\\ ?]+\.jpg',response.text)))
    prefixes=['Vice_City_01.','Leonida_Keys_01.','Grassrivers_01.','Port_Gellhorn_01.','Ambrosia_01.','Mount_Kalaga_National_Park_01.',
              'Jason_Duval_01.','Jason_Duval_02.','Jason_Duval_03.','Lucia_Caminos_01.','Lucia_Caminos_02.',
              'Lucia_Caminos_03.','Jason_and_Lucia_01.','Jason_and_Lucia_02.']
    selected=[]
    for prefix in prefixes:
        matches=[p for p in paths if ('/media/'+prefix) in p]
        if len(matches)!=1:raise ValueError('Galería de GTA VI cambiada; revisar la selección')
        selected.append('https://www.rockstargames.com'+matches[0])
    return selected


@lru_cache(maxsize=8)
def game_data(game):
    appid, expected = GAMES[game]
    r=requests.get('https://store.steampowered.com/api/appdetails',params={'appids':appid,'l':'english'},headers={'User-Agent':UA},timeout=(15,40))
    r.raise_for_status();entry=r.json()[str(appid)]
    if not entry.get('success'):raise RuntimeError(f'Catálogo oficial no disponible: {game}')
    data=entry['data']
    if expected.lower() not in data['name'].lower() or 'Rockstar Games' not in data.get('publishers',[]):
        raise ValueError('El producto o el editor no coincide con el material solicitado')
    return data


def source_text(data):
    return BeautifulSoup(data.get('about_the_game',''),'html.parser').get_text(' ',strip=True)


def verify_topic(topic):
    documents=[]
    for check in topic['checks']:
        if check.get('game'):
            data=game_data(check['game']);text=source_text(data);url=f'https://store.steampowered.com/app/{data["steam_appid"]}/'
        else:
            url=check['url'];r=requests.get(url,headers={'User-Agent':UA},timeout=(15,40));r.raise_for_status();text=BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
        if not all(term.lower() in text.lower() for term in check['terms']):
            raise RuntimeError('La fuente ha cambiado: revisar el dato editorial '+topic['id'])
        documents.append({'url':url,'terms_present':check['terms'],'sha256':hashlib.sha256(text.encode()).hexdigest()})
    return documents


def valid_image_url(url):
    p=urlparse(url)
    steam=p.hostname in IMAGE_HOSTS and p.path.startswith('/store_item_assets/steam/apps/')
    rockstar=p.hostname=='www.rockstargames.com' and p.path.startswith('/VI/_next/static/media/')
    return p.scheme=='https' and (steam or rockstar) and p.path.lower().endswith(('.jpg','.png'))


def image_for(game, index):
    if game=='gta6':
        data={'name':'Grand Theft Auto VI','steam_appid':None};shots=[{'id':i,'path_full':u} for i,u in enumerate(gta6_gallery())]
        page=GTA6_GALLERY
    else:
        data=game_data(game);shots=data.get('screenshots',[]);page=f'https://store.steampowered.com/app/{data["steam_appid"]}/'
    if not 0<=index<len(shots):raise ValueError(f'No existe el plano {index} para {game}')
    url=shots[index]['path_full']
    if not valid_image_url(url):raise ValueError('Origen de imagen no autorizado')
    cache=ROOT/'.cache'/'screenshots';cache.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(url.encode()).hexdigest()[:24];p=cache/(key+'.jpg')
    if not p.exists():
        part=p.with_suffix('.part');size=0
        try:
            with requests.get(url,stream=True,headers={'User-Agent':UA},timeout=(15,40)) as r:
                r.raise_for_status()
                with part.open('wb') as f:
                    for b in r.iter_content(65536):
                        size+=len(b)
                        if size>12_000_000:raise ValueError('Imagen demasiado grande')
                        f.write(b)
            with Image.open(part) as im:
                if im.width<640 or im.height<360:raise ValueError('Imagen insuficiente incluso para el montaje de archivo')
                im.verify()
            part.replace(p)
        finally:part.unlink(missing_ok=True)
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    with Image.open(p) as im:native=[im.width,im.height]
    return p,{'game':game,'product':data['name'],'asset_id':shots[index]['id'],'url':url,
              'source_page':page,
              'publisher':'Rockstar Games','sha256':sha,'type':'official_screenshot','native_resolution':native,
              'license':'copyright Rockstar Games / Take-Two; no licencia libre','rights_status':'review_required'}


def _publisher_news(appid):
    response=requests.get('https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/',
        params={'appid':appid,'count':8,'maxlength':1,'feeds':'steam_community_announcements','format':'json'},timeout=(5,25))
    response.raise_for_status()
    return response.json().get('appnews',{}).get('newsitems',[])


def discover_ideas(topics, output, fetch_news=True):
    """Busca anuncios del editor en paralelo. Los resultados son candidatos, no nuevos hechos aprobados."""
    report={'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'approved_scripts':[{'id':t['id'],'title':t['title']} for t in topics if t.get('editorial_status')=='approved_fact'],
            'discovered_articles':[],'source_errors':[],
            'policy':'Los artículos encontrados son candidatos pendientes de verificación y guion; no se renderizan automáticamente.'}
    seen=set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending={}
        for game,(appid,_) in GAMES.items():
            try:
                log('Investigando catálogo y anuncios: '+game)
                game_data(game)
                if fetch_news:pending[pool.submit(_publisher_news,appid)]=game
            except (requests.RequestException,ValueError,KeyError,RuntimeError) as e:
                report['source_errors'].append({'game':game,'error':type(e).__name__})
        for future in as_completed(pending):
            game=pending[future]
            try:
                for item in future.result():
                    if item.get('feedname')!='steam_community_announcements':continue
                    url=item.get('url','')
                    if not url or url in seen:continue
                    seen.add(url);title=html.unescape(item.get('title',''))
                    report['discovered_articles'].append({'game':game,'title':title,'url':url,'date':item.get('date'),
                        'source':'anuncio del editor en Steam','status':'needs_editorial_review',
                        'relevance':sum(w in title.lower() for w in ['anniversary','story','classic','music','radio','making','trilogy'])})
            except (requests.RequestException,ValueError,KeyError,RuntimeError) as e:
                report['source_errors'].append({'game':game,'error':type(e).__name__})
    report['discovered_articles'].sort(key=lambda x:(-x['relevance'],-x.get('date',0)))
    Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    log(f'Investigación GTA: {len(report["discovered_articles"])} artículos del editor y {len(report["approved_scripts"])} guiones aprobados.')
    return report
