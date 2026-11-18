"""Continuidad real de la voz: editar únicamente silencio y conservar sus palabras."""
import numpy as np


def silent_spans(samples, rate, threshold_db=-48, minimum=.45):
    step=max(1,round(rate*.005))
    mono=np.asarray(samples,dtype=np.float64)
    if mono.ndim>1:mono=mono.mean(axis=1)
    count=len(mono)//step
    if not count:return []
    rms=np.sqrt(np.mean(mono[:count*step].reshape(count,step)**2,axis=1))
    quiet=rms<10**(threshold_db/20)
    edges=np.diff(np.r_[False,quiet,False].astype(int))
    return [(int(a*step),int(b*step)) for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0])
            if (b-a)*step/rate>=minimum]


def tighten_pauses(samples,rate,words):
    """Acortar huecos largos a 280 ms, sin tocar intervalos hablados ni su velocidad."""
    cuts=[];keep=round(.28*rate)
    for a,b in silent_spans(samples,rate):
        if a==0:
            if b>round(.065*rate):cuts.append((0,b-round(.065*rate)))
        elif b>=len(samples)-round(.01*rate):
            # Conservar el último fonema, su marca de palabra y 180 ms de salida.
            end=max(round(words[-1]['end']*rate),a)+round(.18*rate)
            if end<b:cuts.append((end,b))
        else:
            # Las marcas del motor también deben quedar fuera de la edición.
            for left,right in zip(words,words[1:]):
                lo=max(a,round(left['end']*rate));hi=min(b,round(right['start']*rate))
                if hi-lo>round(.55*rate):
                    margin=keep//2;cuts.append((lo+margin,hi-margin));break
    chunks=[];cursor=0
    for a,b in cuts:
        chunks.append(samples[cursor:a]);cursor=b
    chunks.append(samples[cursor:]);result=np.concatenate(chunks)
    def mapped(t):
        point=round(t*rate)
        return max(0,(point-sum(max(0,min(point,b)-a) for a,b in cuts)))/rate
    adjusted=[{**w,'start':mapped(w['start']),'end':mapped(w['end'])} for w in words]
    if any(w['end']<=w['start'] for w in adjusted):raise ValueError('La edición ha invadido una palabra')
    return result,adjusted,{'edited_silences':len(cuts),'removed_seconds':sum(b-a for a,b in cuts)/rate,
        'target_pause_seconds':.28,'speech_speed_changed':False}
