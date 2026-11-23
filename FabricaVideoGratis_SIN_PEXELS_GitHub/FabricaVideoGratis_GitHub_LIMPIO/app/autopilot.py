"""Consumir investigación horaria, producir cinco Shorts y publicarlos sin repeticiones."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from .pipeline import ROOT,OUT,log
from .editorial_queue import UTC,ingest,select_pending,signature,timestamp
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


def verified_history(record,result,now):
    record.update(video_id=result['video_id'],url=result['url'],verified_at=now.isoformat(),
        privacy_status=result['status']['privacyStatus'],schedule_verified=result.get('schedule_verified',False),
        public_verified=result.get('public_verified',False),
        verification_method='youtube_data_api_videos_list',channel_id=result.get('channel_id'))


def reconcile_uploads(state,publisher,now):
    """Consultar, nunca volver a insertar, los intentos inciertos y las publicaciones vencidas."""
    blocked=[]
    for record in state['history']:
        uncertain=record['status'] in ('uploading','uncertain','schedule_unconfirmed')
        due=record['status']=='scheduled' and record.get('publish_at') and timestamp(record['publish_at'])<=now
        if not (uncertain or due):continue
        try:result=publisher.inspect_upload(record['key'],record.get('publish_at'))
        except Exception as exc:
            record['verification_error']=exc.code if isinstance(exc,BridgeError) else type(exc).__name__
            blocked.append(record['key']);continue
        if not result.get('found'):
            blocked.append(record['key']);continue
        verified_history(record,result,now)
        if record.get('publish_at'):
            if not result.get('schedule_verified'):
                blocked.append(record['key']);continue
            record['status']='published' if result.get('public_verified') else 'scheduled'
        else:
            if not result.get('private_verified'):
                blocked.append(record['key']);continue
            record['status']='private_test'
        state['pending']=[t for t in state['pending'] if t['queue_key']!=record['key']]
        record.pop('verification_error',None)
    if blocked:state['publication_hold']={'keys':blocked,'checked_at':now.isoformat()}
    else:state.pop('publication_hold',None)
    return blocked


def remaining_this_hour(state,now,limit):
    hour=now.strftime('%Y-%m-%dT%H')
    used=sum(1 for h in state['history'] if h.get('started_at') and not h.get('purpose') and
        timestamp(h['started_at']).strftime('%Y-%m-%dT%H')==hour)
    return max(0,limit-used)


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
        held=reconcile_uploads(state,publisher,now)
        store.save(state)
        if held:
            report.update(status='publication_needs_review',pending=len(state['pending']),
                reason='Subida anterior sin confirmación completa. Solo se consultará su estado; no se insertan más vídeos.')
            report_summary(report,folder)
            raise RuntimeError('Publicación bloqueada: la subida anterior sigue sin confirmar; no se insertan más vídeos')
        hour=now.strftime('%Y-%m-%dT%H')
        if not remaining_this_hour(state,now,config['batch_size']):
            report.update(status='hour_already_processed',pending=len(state['pending']))
            report_summary(report,folder);return report
    blocked={h['key'] for h in state['history']
        if not (h['status']=='rejected_before_upload' and h.get('reconciliation',{}).get('confirmed_no_upload') is True)}
    chosen=select_pending(state,now,config,excluded_keys=blocked)
    if publisher:chosen=chosen[:min(remaining_uploads(state,now,config['daily_upload_limit']),remaining_this_hour(state,now,config['batch_size']))]
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
        if not qa['passed']:raise RuntimeError('El vídeo no supera el control de calidad')
        if not publisher:continue
        current=dt.datetime.now(UTC)
        if not remaining_uploads(state,current,config['daily_upload_limit']):break
        existing=publisher.inspect_upload(key)
        if existing.get('found') or existing.get('uncertain'):
            state['publication_hold']={'keys':[key],'checked_at':current.isoformat()};store.save(state)
            report.update(status='publication_needs_review',pending=len(state['pending']),
                reason='YouTube o el diario ya contienen esta huella. No se repite la inserción.')
            report_summary(report,folder);return report
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
                if isinstance(exc,BridgeError) and exc.code=='DAILY_UPLOAD_LIMIT':
                    # El puente rechaza este caso ANTES de intentar insertar un vídeo.
                    record['status']='rejected_before_upload'
                    record['reconciliation']={'confirmed_no_upload':True}
                else:
                    # Un rechazo remoto posterior al intento no demuestra ausencia de subida.
                    record['status']='deferred'
                state['quota_block_until']=reset;store.save(state)
                report.update(status='quota_wait',pending=len(state['pending']),reason='YouTube ha limitado las subidas; la cola se conserva hasta '+reset)
                report_summary(report,folder);return report
            record['status']='uncertain';record['error_type']=type(exc).__name__;store.save(state)
            if isinstance(exc,BridgeError):
                record['error_code']=exc.code;store.save(state)
            state['publication_hold']={'keys':[key],'checked_at':current.isoformat()};store.save(state)
            report.update(status='upload_needs_reconciliation',pending=len(state['pending']))
            report_summary(report,folder)
            raise RuntimeError('La subida no se ha confirmado; el próximo ciclo buscará el ID antes de volver a publicar') from None
        record.update(status='scheduled' if result['schedule_verified'] else 'schedule_unconfirmed',video_id=result['video_id'],url=result['url'])
        verified_history(record,result,dt.datetime.now(UTC))
        state['pending']=[t for t in state['pending'] if t['queue_key']!=key]
        store.save(state);write_json(video.parent/'youtube_publication.json',{**result,'publish_at':slot,'seo':body})
        report['published'].append(result)
        if not result['schedule_verified']:
            state['publication_hold']={'keys':[key],'checked_at':current.isoformat()};store.save(state)
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
    ingestion=ingest(state,packet,now,config)
    blocked={h['key'] for h in state['history']}
    chosen=select_pending(state,now,config,excluded_keys=blocked)
    store.save(state)
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


def production_failure_reason(report):
    """Una tarea sin publicaciones verificadas no debe mostrarse como éxito en Actions."""
    if report.get('mode')!='production':return None
    if report.get('status')=='complete' and report.get('published'):return None
    detail=report.get('reason') or 'Revisar el informe de la ejecución y el estado de la cola.'
    return f"Ningún Short nuevo publicado y confirmado: {report.get('status','desconocido')}. {detail}"


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('preview','production','queue','upload-test'),default='production')
    parser.add_argument('--batch-size',type=int);parser.add_argument('--local-state')
    args=parser.parse_args();report=run_batch(args.mode,args.batch_size,args.local_state)
    issue=production_failure_reason(report)
    if issue:raise SystemExit(issue)
