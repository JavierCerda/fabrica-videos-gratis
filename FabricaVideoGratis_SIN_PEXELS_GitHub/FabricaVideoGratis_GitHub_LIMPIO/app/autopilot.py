"""Consumir investigación horaria, producir cinco Shorts y publicarlos sin repeticiones."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from .pipeline import ROOT,OUT,log
from .editorial_queue import UTC,ingest,select_pending,signature
from .production_state import StateStore
from .youtube_publisher import YouTubePublisher,readiness,quota_day,remaining_uploads,next_slot,seo,classify_upload_error
from .studio import produce,write_json
from .quality import inspect
from .youtube_bridge import BridgeError


def report_summary(report,folder):
    write_json(folder/'automation_report.json',report)
    lines=['## Shorts GTA · '+report['status'],
        f"Generados: {len(report.get('videos',[]))} · Programados: {len(report.get('published',[]))} · Pruebas privadas: {len(report.get('test_uploads',[]))} · Pendientes: {report.get('pending',0)}"]
    if report.get('missing'):lines.append('Conexión pendiente: '+', '.join(report['missing']))
    if report.get('reason'):lines.append(report['reason'])
    lines.extend(f"- [{v['title']}]({v['url']})" for v in report.get('published',[]))
    lines.extend(f"- Prueba privada: [{v['title']}]({v['url']})" for v in report.get('test_uploads',[]))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as stream:stream.write('\n'.join(lines)+'\n')
    log(json.dumps({k:v for k,v in report.items() if k not in ('ingestion','videos')},ensure_ascii=False))


def run_batch(mode='production',batch_size=None,local_state=None):
    if mode=='upload-test':return run_private_test(local_state)
    now=dt.datetime.now(UTC);config=json.loads((ROOT/'config/automation.json').read_text())
    if batch_size:config['batch_size']=min(5,max(1,batch_size))
    folder=OUT/(now.strftime('%Y%m%d_%H%M%S')+'_autopilot');folder.mkdir(parents=True,exist_ok=True)
    packet=json.loads((ROOT/'topics/inbox.json').read_text())
    store=StateStore(config['state_branch'],local_state) if mode in ('production','queue') else None
    state=store.load() if store else {'schema_version':1,'pending':[],'history':[],'attempts':{}}
    report={'status':'running','mode':mode,'created_at':now.isoformat(),'videos':[],'published':[]}
    report['ingestion']=ingest(state,packet,now,config)
    select_pending(state,now,config)  # Retirar noticias caducadas también cuando falte OAuth.
    if store:store.save(state)
    publisher=None
    if mode=='queue':
        report.update(status='queue_saved',pending=len(state['pending']))
        report_summary(report,folder);return report
    if mode=='production':
        if not config.get('publication_enabled',False):
            report.update(status='publication_paused',pending=len(state['pending']),
                missing=readiness()['missing'],
                reason='Revisión de voz, guiones y medios. La cola se conserva sin subir vídeos.')
            report_summary(report,folder);return report
        check=readiness()
        if not check['ready']:
            report.update(status='connection_required',missing=check['missing'],pending=len(state['pending']))
            report_summary(report,folder);return report
        publisher=YouTubePublisher()
        if getattr(publisher,'private_test_only',False) is True:
            report.update(status='private_connection_only',pending=len(state['pending']),
                reason='Canal conectado para pruebas privadas. La publicación pública requiere una conexión habilitada y verificada para producción.')
            report_summary(report,folder);return report
        markers=publisher.recent_markers()
        for old in state['history']:
            if old['status'] in ('uploading','uncertain') and old['key'] in markers:
                old.update(status='recovered',video_id=markers[old['key']])
                state['pending']=[t for t in state['pending'] if t['queue_key']!=old['key']]
        store.save(state)
        hour=now.strftime('%Y-%m-%dT%H')
        if state.get('last_production_hour')==hour:
            report.update(status='hour_already_processed',pending=len(state['pending']))
            report_summary(report,folder);return report
    blocked={h['key'] for h in state['history'] if h['status'] in ('uploading','uncertain')}
    chosen=[t for t in select_pending(state,now,config)
        if t['queue_key'] not in blocked and t.get('editorial_version',0)>=config.get('editorial_version',0)]
    if publisher:chosen=chosen[:remaining_uploads(state,now,config['daily_upload_limit'])]
    if not chosen:
        status='quota_wait' if publisher and not remaining_uploads(state,now,config['daily_upload_limit']) else 'waiting_for_research'
        report.update(status=status,pending=len(state['pending']))
        if store:store.save(state)
        report_summary(report,folder);return report
    if publisher:
        state['last_production_hour']=now.strftime('%Y-%m-%dT%H');store.save(state)
    for topic in chosen:
        key=signature(topic);video=produce(topic,folder);qa=inspect(video)
        report['videos'].append({'id':topic['id'],'path':str(video),'quality_passed':qa['passed']})
        if not publisher:continue
        current=dt.datetime.now(UTC)
        if not remaining_uploads(state,current,config['daily_upload_limit']):break
        slot=next_slot(state,current,config['spacing_minutes'])
        body=seo(topic,key,slot,config)
        record={'key':key,'topic_id':topic['id'],'facts':' '.join(topic['editorial']['facts']),
            'source_urls':topic['sources'],'kind':topic['content_type'],'status':'uploading',
            'started_at':current.isoformat(),'publish_at':slot}
        state['history'].append(record)
        day=quota_day(current);state['attempts'][day]=state['attempts'].get(day,0)+1
        store.save(state)  # Reservar antes del efecto externo; un fallo no provoca otra subida.
        try:result=publisher.upload(video,body,notify=config['notify_subscribers'])
        except Exception as exc:
            reset=classify_upload_error(exc,dt.datetime.now(UTC))
            if reset:
                record['status']='deferred';state['quota_block_until']=reset;store.save(state)
                report.update(status='quota_wait',pending=len(state['pending']),reason='YouTube ha limitado las subidas; la cola se conserva hasta '+reset)
                report_summary(report,folder);return report
            record['status']='uncertain';record['error_type']=type(exc).__name__;store.save(state)
            if isinstance(exc,BridgeError):
                record['error_code']=exc.code;store.save(state)
            report.update(status='upload_needs_reconciliation',pending=len(state['pending']))
            report_summary(report,folder)
            raise RuntimeError('La subida no se ha confirmado; el próximo ciclo buscará el ID antes de volver a publicar') from None
        record.update(status='scheduled' if result['schedule_verified'] else 'schedule_unconfirmed',video_id=result['video_id'],url=result['url'])
        state['pending']=[t for t in state['pending'] if t['queue_key']!=key]
        store.save(state);write_json(video.parent/'youtube_publication.json',{**result,'publish_at':slot,'seo':body})
        report['published'].append(result)
        if not result['schedule_verified']:
            report.update(status='schedule_needs_review',pending=len(state['pending']),reason='Vídeo subido, pero YouTube no confirmó su fecha de publicación pública.')
            report_summary(report,folder);return report
    report.update(status='preview_complete' if not publisher else 'complete',pending=len(state['pending']))
    if store:store.save(state)
    report_summary(report,folder);return report


def run_private_test(local_state=None):
    """Una prueba privada autorizada: sin programar publicación ni activar el flujo público."""
    now=dt.datetime.now(UTC);config=json.loads((ROOT/'config/automation.json').read_text())
    folder=OUT/(now.strftime('%Y%m%d_%H%M%S')+'_upload_test');folder.mkdir(parents=True,exist_ok=True)
    store=StateStore(config['state_branch'],local_state);state=store.load()
    packet=json.loads((ROOT/'topics/inbox.json').read_text())
    ingestion=ingest(state,packet,now,config);selected=select_pending(state,now,config);store.save(state)
    blocked={h['key'] for h in state['history']}
    chosen=[t for t in selected if t['queue_key'] not in blocked]
    report={'status':'running','mode':'upload-test','created_at':now.isoformat(),
        'videos':[],'published':[],'test_uploads':[],'ingestion':ingestion,'pending':len(state['pending'])}
    if not chosen:
        report['status']='waiting_for_research';report_summary(report,folder);return report
    check=readiness();publisher=YouTubePublisher() if check['ready'] else None
    topic=chosen[0];key=signature(topic);video=produce(topic,folder);qa=inspect(video)
    if not qa['passed']:raise RuntimeError('La prueba no supera el control de calidad')
    report['videos'].append({'id':topic['id'],'path':str(video),'quality_passed':True})
    if publisher is None:
        report.update(status='connection_required',missing=check['missing'],
            reason='Vídeo de prueba generado y validado. Falta OAuth para subirlo como privado, sin programación pública.')
        report_summary(report,folder);return report
    if not remaining_uploads(state,now,config['daily_upload_limit']):
        report['status']='quota_wait';report_summary(report,folder);return report
    if key in publisher.recent_markers():
        report.update(status='upload_already_exists',reason='Ya existe un vídeo con esta huella; no se repite la subida.')
        report_summary(report,folder);return report
    body=seo(topic,key,None,config)
    record={'key':key,'topic_id':topic['id'],'facts':' '.join(topic['editorial']['facts']),
        'source_urls':topic['sources'],'kind':topic['content_type'],'status':'uploading',
        'purpose':'private_test','started_at':now.isoformat(),'publish_at':None}
    state['history'].append(record);day=quota_day(now)
    state['attempts'][day]=state['attempts'].get(day,0)+1;store.save(state)
    try:
        result=publisher.upload(video,body,notify=False)
        record.update(video_id=result.get('video_id'),url=result.get('url'))
        if not result.get('private_verified'):raise RuntimeError('YouTube no confirmó una prueba privada sin fecha pública')
    except Exception as exc:
        reset=classify_upload_error(exc,dt.datetime.now(UTC))
        record['status']='deferred' if reset else 'uncertain';record['error_type']=type(exc).__name__
        if isinstance(exc,BridgeError):record['error_code']=exc.code
        if reset:state['quota_block_until']=reset
        store.save(state);report['status']='quota_wait' if reset else 'upload_needs_reconciliation'
        report_summary(report,folder)
        if reset:return report
        raise RuntimeError('La prueba privada no se ha confirmado; no se repetirá la subida automáticamente') from None
    record.update(status='private_test',video_id=result['video_id'],url=result['url'])
    state['pending']=[t for t in state['pending'] if t['queue_key']!=key];store.save(state)
    write_json(video.parent/'youtube_publication.json',{**result,'private_test':True,'seo':body})
    report.update(status='private_test_complete',test_uploads=[result],pending=len(state['pending']))
    report_summary(report,folder);return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('preview','production','queue','upload-test'),default='production')
    parser.add_argument('--batch-size',type=int);parser.add_argument('--local-state')
    args=parser.parse_args();run_batch(args.mode,args.batch_size,args.local_state)
