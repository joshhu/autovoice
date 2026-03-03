#!/usr/bin/env python3
# scripts/run_tts_aligned.py
# 逐句合成並對齊原始時間軸：每個 segment 各自合成，放置於正確時間點
# 若合成音訊過長，使用 ffmpeg atempo 加速以符合可用時間窗口
import sys
import os
import json
import tempfile
import subprocess
import numpy as np
import soundfile as sf


def adjust_speed(audio: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """使用 ffmpeg atempo 調整速度（factor > 1 加速，< 1 減速）
    atempo 每個 filter 限制 0.5–2.0，超過 2x 需要串接兩個。
    """
    if abs(factor - 1.0) < 0.03:
        return audio

    # 建立 atempo 濾鏡鏈（支援超過 2x 加速）
    filters = []
    remaining = factor
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    filter_str = ",".join(filters)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in:
        sf.write(f_in.name, audio, sr)
        in_path = f_in.name
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_out:
        out_path = f_out.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-filter:a", filter_str, out_path],
            capture_output=True, check=True
        )
        result, _ = sf.read(out_path, dtype="float32")
    finally:
        os.unlink(in_path)
        os.unlink(out_path)

    return result


def get_attn_implementation() -> str:
    try:
        import flash_attn  # noqa: F401
        return "kernels-community/flash-attn3"
    except ImportError:
        return "sdpa"


def run_tts_aligned(
    ref_wav_path: str,
    ref_text_path: str,
    segments_json_path: str,
    language: str,
    output_wav_path: str,
    model_size: str = "1.7B",
    total_duration: float = None,
) -> None:
    """
    逐句合成 TTS 並對齊原始時間軸。

    參數：
        ref_wav_path:      參考音訊 WAV 路徑
        ref_text_path:     參考音訊文字稿路徑
        segments_json_path: 含時間軸的翻譯段落 JSON
                            格式: [{"start":0.5,"end":5.8,"original":"...","translated":"..."}]
        language:          目標語言（英文名稱）
        output_wav_path:   輸出 WAV 路徑
        model_size:        "0.6B" 或 "1.7B"
        total_duration:    輸出總時長（秒），None 則自動從最後一段推算
    """
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel

    # 載入參考音訊
    ref_data, ref_sr = sf.read(ref_wav_path, dtype="float32")
    if ref_data.ndim > 1:
        ref_data = np.mean(ref_data, axis=-1)
    ref_audio = (ref_data, int(ref_sr))

    with open(ref_text_path, encoding="utf-8") as f:
        ref_text = f.read().strip()

    # 載入段落翻譯
    with open(segments_json_path, encoding="utf-8") as f:
        segments = json.load(f)

    if not segments:
        print("錯誤：segments JSON 為空", file=sys.stderr)
        sys.exit(1)

    # 載入 TTS 模型
    attn_impl = get_attn_implementation()
    print(f"使用 attention 實作: {attn_impl}", flush=True)
    print(f"載入 Qwen3-TTS Base {model_size} 模型...", flush=True)
    model_path = snapshot_download(f"Qwen/Qwen3-TTS-12Hz-{model_size}-Base")
    tts = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda",
        dtype=torch.bfloat16,
        attn_implementation=attn_impl,
    )

    # 第一步：逐句合成，取得真實 sr
    print(f"\n開始逐句合成（共 {len(segments)} 段）...", flush=True)
    synthesized = []
    output_sr = None

    for i, seg in enumerate(segments):
        text = seg["translated"]
        start = seg["start"]
        end = seg["end"]
        # 下一段開始時間 = 可用窗口的右邊界
        if i + 1 < len(segments):
            next_start = segments[i + 1]["start"]
        else:
            next_start = seg["end"] + 5.0  # 最後一段給 5 秒緩衝
        available = next_start - start

        print(f"  [{i+1}/{len(segments)}] {start:.1f}s–{end:.1f}s 可用 {available:.1f}s: {text[:35]}...", flush=True)

        # x_vector_only_mode=True：只取音色特徵，不依賴參考文字語言
        wavs, sr = tts.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=ref_audio,
            ref_text=None,
            x_vector_only_mode=True,
            max_new_tokens=2048,
        )
        wav = wavs[0]
        if output_sr is None:
            output_sr = sr

        synth_dur = len(wav) / sr
        print(f"    合成時長: {synth_dur:.1f}s", flush=True)

        # 若超出可用窗口，加速以符合（留 5% 間隙）
        if synth_dur > available * 0.95:
            factor = synth_dur / (available * 0.95)
            print(f"    加速 {factor:.2f}x 以符合時間窗口", flush=True)
            wav = adjust_speed(wav, sr, factor)
            synth_dur = len(wav) / sr
            print(f"    調整後時長: {synth_dur:.1f}s", flush=True)

        synthesized.append({"start": start, "wav": wav})

    # 第二步：組裝輸出音訊（填入靜音底軌 + 各段放置於對應時間點）
    if total_duration is None:
        last = synthesized[-1]
        total_duration = last["start"] + len(last["wav"]) / output_sr + 1.0

    total_samples = int(total_duration * output_sr)
    output_audio = np.zeros(total_samples, dtype=np.float32)

    for item in synthesized:
        start_sample = int(item["start"] * output_sr)
        wav = item["wav"]
        end_sample = start_sample + len(wav)
        if end_sample > len(output_audio):
            # 自動擴展緩衝區
            output_audio = np.pad(output_audio, (0, end_sample - len(output_audio)))
        output_audio[start_sample:end_sample] += wav

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    sf.write(output_wav_path, output_audio, output_sr)

    duration = len(output_audio) / output_sr
    print(f"\n對齊合成完成: {output_wav_path}", flush=True)
    print(f"  總時長: {duration:.1f} 秒，語言: {language}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("用法: python run_tts_aligned.py <ref_wav> <ref_txt> <segments_json> <language> <output_wav> [model_size]")
        print("  segments_json 格式: [{\"start\":0.5,\"end\":5.8,\"original\":\"...\",\"translated\":\"...\"}]")
        sys.exit(1)
    model = sys.argv[6] if len(sys.argv) > 6 else "1.7B"
    total_dur = float(sys.argv[7]) if len(sys.argv) > 7 else None
    run_tts_aligned(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], model, total_dur)
