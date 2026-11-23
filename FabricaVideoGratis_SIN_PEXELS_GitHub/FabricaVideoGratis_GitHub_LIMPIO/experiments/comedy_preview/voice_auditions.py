"""Comparativa de voces SIN publicación ni autenticación de YouTube.

No afecta a la narración activa: produce únicamente MP3 con el mismo texto.
"""
import asyncio
import hashlib
import json
from pathlib import Path

from app.pipeline import OUT, duration, run
from app.neural_voice import synthesize

SAMPLE = (
    "En GTA cinco puedes convertir a un perro en el protagonista de tu película. "
    "Sí, un perro. Y Trevor pasando a secundario. "
    "El modo Director de ordenador te deja montar escenas con personajes y animales. "
    "El perro da menos problemas."
)

KOKORO_ASSETS = {
    "kokoro-v1.0.onnx":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
    "voices-v1.0.bin":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
}


def download_models(folder):
    import requests
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in KOKORO_ASSETS.items():
        target = folder / name
        if target.is_file() and target.stat().st_size > 1_000_000:
            continue
        partial = target.with_suffix(target.suffix + ".part")
        total = 0
        try:
            with requests.get(url, timeout=(25, 150), stream=True) as response:
                response.raise_for_status()
                with partial.open("wb") as stream:
                    for block in response.iter_content(1024 * 1024):
                        total += len(block)
                        if total > 500_000_000:
                            raise RuntimeError("El modelo excede el máximo permitido")
                        stream.write(block)
            if total < 1_000_000:
                raise RuntimeError("Descarga vacía o incompleta: " + name)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    return folder / "kokoro-v1.0.onnx", folder / "voices-v1.0.bin"


def as_mp3(wav, path):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav),
         "-af", "loudnorm=I=-18:TP=-2:LRA=7", "-c:a", "libmp3lame",
         "-ar", "48000", "-b:a", "160k", str(path)])
    if not 4 < duration(path) < 40:
        raise RuntimeError("Muestra demasiado corta o larga: " + path.name)


def main():
    import os
    if os.getenv("RUN_MODE") != "preview":
        raise RuntimeError("Prohibida la prueba fuera del modo preview")
    if any(os.getenv(var) for var in ("YT_BRIDGE_URL", "YT_CLIENT_ID", "YT_REFRESH_TOKEN")):
        raise RuntimeError("La muestra no puede disponer de conexiones de YouTube")

    out = OUT / "muestras-voces-gta"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for name, voice in (("A-Ximena", "es-ES-XimenaNeural"),
                        ("B-Elvira", "es-ES-ElviraNeural")):
        wav = out / (name + ".wav")
        try:
            asyncio.run(synthesize(SAMPLE, wav, voice, "comedy_preview"))
            dest = out / (name + ".mp3")
            as_mp3(wav, dest)
            results.append({"name": name, "engine": "Edge TTS",
                            "voice": voice, "seconds": round(duration(dest), 2),
                            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
        finally:
            wav.unlink(missing_ok=True)
            wav.with_suffix(".words.json").unlink(missing_ok=True)

    # Kokoro es opcional: si la voz local falla, las muestras Edge se conservan;
    # jamás sustituye silenciosamente la voz productiva ni llama a YouTube.
    try:
        from kokoro_onnx import Kokoro
        from misaki.espeak import EspeakG2P
        import soundfile as sf
        model_file, voices_file = download_models(out / "cache")
        kokoro = Kokoro(str(model_file), str(voices_file))
        phonemes, _ = EspeakG2P(language="es")(SAMPLE)
        for name, voice in (("C-Alex-Kokoro", "em_alex"),
                            ("D-Santa-Kokoro", "em_santa")):
            wav = out / (name + ".wav")
            try:
                audio, sample_rate = kokoro.create(
                    phonemes, voice=voice, speed=1.02, is_phonemes=True)
                sf.write(str(wav), audio, sample_rate)
                dest = out / (name + ".mp3")
                as_mp3(wav, dest)
                results.append({"name": name, "engine": "Kokoro ONNX local CPU",
                                "voice": voice, "seconds": round(duration(dest), 2),
                                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
            finally:
                wav.unlink(missing_ok=True)
    except Exception as exc:
        results.append({"name": "Kokoro", "status": "not_available",
                        "error_type": type(exc).__name__, "message": str(exc)[:300]})
        print("Kokoro no disponible en esta ejecución:", repr(exc))

    manifest = {"status": "preview_only", "youtube_uploaded": False,
                "same_exact_script": SAMPLE, "auditions": results}
    (out / "voces.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if not any(r.get("voice") == "es-ES-ElviraNeural" for r in results):
        raise RuntimeError("Faltó la muestra española Elvira")


if __name__ == "__main__":
    main()
