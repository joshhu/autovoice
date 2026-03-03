#!/usr/bin/env python3
# scripts/run_tts.py
# 使用 Qwen3-TTS Base 進行聲音克隆與文字合成
# 參考 app.py 的 generate_voice_clone 用法
import sys
import os
import re
import numpy as np
import soundfile as sf

# 語言名稱對應表（Qwen3-TTS 使用英文語言名）
LANG_MAP = {
    "zh": "Chinese", "chinese": "Chinese", "中文": "Chinese",
    "ja": "Japanese", "japanese": "Japanese", "日文": "Japanese", "日語": "Japanese",
    "en": "English", "english": "English", "英文": "English",
    "ko": "Korean", "korean": "Korean", "韓文": "Korean",
    "fr": "French", "french": "French", "法文": "French",
    "de": "German", "german": "German", "德文": "German",
    "es": "Spanish", "spanish": "Spanish", "西班牙文": "Spanish",
    "pt": "Portuguese", "portuguese": "Portuguese", "葡萄牙文": "Portuguese",
}


def normalize_language(lang: str) -> str:
    """將語言代碼或中文名稱轉換為 Qwen3-TTS 所需的英文名稱"""
    return LANG_MAP.get(lang.lower(), lang.capitalize())


def load_audio(wav_path: str) -> tuple:
    """載入 WAV 為 float32 陣列，回傳 (data, sample_rate)"""
    data, sr = sf.read(wav_path, dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=-1)
    return data, int(sr)


def split_text(text: str, max_chars: int = 200) -> list:
    """將長文字按句子分割，避免單段過長"""
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    chunks = []
    current = ""
    for sent in sentences:
        if not sent.strip():
            continue
        if len(current) + len(sent) <= max_chars:
            current += sent + " "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sent + " "
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def get_attn_implementation() -> str:
    """嘗試 flash-attn，失敗則 fallback 到 sdpa"""
    try:
        import flash_attn  # noqa: F401
        return "kernels-community/flash-attn3"
    except ImportError:
        pass
    try:
        import flash_attn_2  # noqa: F401
        return "flash_attention_2"
    except ImportError:
        pass
    return "sdpa"


def run_tts_clone(
    ref_wav_path: str,
    ref_text_path: str,
    target_text: str,
    language: str,
    output_wav_path: str,
    model_size: str = "1.7B",
) -> None:
    """
    使用 Qwen3-TTS Base 模型進行聲音克隆並合成目標文字。

    參數：
        ref_wav_path: 參考音訊 WAV 路徑（30 秒）
        ref_text_path: 參考音訊的文字稿路徑
        target_text: 要合成的目標文字
        language: 語言（支援中文代碼或英文名稱）
        output_wav_path: 輸出 WAV 路徑
        model_size: 模型大小，"0.6B" 或 "1.7B"
    """
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel

    lang = normalize_language(language)
    ref_audio = load_audio(ref_wav_path)

    with open(ref_text_path, encoding="utf-8") as f:
        ref_text = f.read().strip()

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

    chunks = split_text(target_text)
    print(f"文字分為 {len(chunks)} 段合成", flush=True)

    all_wavs = []
    sr = None
    for i, chunk in enumerate(chunks, 1):
        print(f"  合成第 {i}/{len(chunks)} 段: {chunk[:40]}...", flush=True)
        wavs, sr = tts.generate_voice_clone(
            text=chunk,
            language=lang,
            ref_audio=ref_audio,
            ref_text=ref_text,
            x_vector_only_mode=False,
            max_new_tokens=2048,
        )
        all_wavs.append(wavs[0])

    combined = np.concatenate(all_wavs) if len(all_wavs) > 1 else all_wavs[0]

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    sf.write(output_wav_path, combined, sr)

    duration = len(combined) / sr
    print(f"\n合成完成: {output_wav_path}", flush=True)
    print(f"  時長: {duration:.1f} 秒，語言: {lang}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("用法: python run_tts.py <ref_wav> <ref_txt> <target_text> <language> <output_wav> [model_size]")
        print("  model_size: 0.6B 或 1.7B（預設 1.7B）")
        sys.exit(1)
    model = sys.argv[6] if len(sys.argv) > 6 else "1.7B"
    run_tts_clone(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], model)
