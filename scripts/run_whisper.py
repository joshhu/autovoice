#!/usr/bin/env python3
# scripts/run_whisper.py
# 使用 faster-whisper Large-v3 進行語音辨識
import sys
import json
import os


def transcribe(input_wav: str, output_json: str,
               model_size: str = "large-v3") -> dict:
    """使用 faster-whisper 轉錄音訊，輸出 JSON 與純文字兩個檔案。"""
    from faster_whisper import WhisperModel

    print(f"載入 Whisper {model_size} 模型...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    print(f"開始辨識: {input_wav}")
    segments_generator, info = model.transcribe(
        input_wav,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    # 注意：segments 是 generator，必須迭代消耗
    segments_list = []
    full_text_parts = []

    for seg in segments_generator:
        segments_list.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())
        print(f"  [{seg.start:.1f}s -> {seg.end:.1f}s] {seg.text.strip()}")

    result = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "text": " ".join(full_text_parts),
        "segments": segments_list,
    }

    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n辨識完成")
    print(f"  語言: {info.language} (信心: {info.language_probability:.1%})")
    print(f"  段落數: {len(segments_list)}")
    print(f"  結果: {output_json}")

    # 同時輸出純文字版
    txt_path = output_json.replace(".json", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result["text"])
    print(f"  純文字: {txt_path}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python run_whisper.py <input_wav> <output_json> [model_size]")
        print("  model_size: large-v3 (預設), medium, small")
        sys.exit(1)

    model = sys.argv[3] if len(sys.argv) > 3 else "large-v3"
    transcribe(sys.argv[1], sys.argv[2], model)
