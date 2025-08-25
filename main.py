import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path
from time import monotonic

APP = "x265-AutoEncoder"
VERSION = "1.4.0"

# ==== USER CONFIG ====
INPUT_DIR   = r"C:\Users\iirusham\Downloads\Video\I"
OUTPUT_DIR  = r"C:\Users\iirusham\Downloads\Video\O"

CRF         = "21"
PRESET      = "slow"

# Behavior
RECURSIVE               = True     # walk subfolders
MIRROR_TREE             = True     # replicate folder tree in OUTPUT_DIR
SKIP_IF_OUTPUT_EXISTS   = True     # skip if output file already exists
SKIP_IF_SOURCE_HEVC     = False    # skip if the source video is already HEVC/H.265
ALWAYS_MKV              = True     # force .mkv output; set False to keep original ext for mp4/etc

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v"}

ENCODER_NAMES = {
    "nvenc": "NVIDIA (NVENC)",
    "qsv":   "Intel (QSV)",
    "amf":   "AMD (AMF)",
    "x265":  "CPU (x265)"
}

NULLDEV = "NUL" if os.name == "nt" else "/dev/null"

def _check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg","-version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.run(["ffprobe","-version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return True
    except Exception:
        print("❌ FFmpeg/ffprobe not found. Add to PATH (ffmpeg/ffprobe -version).")
        return False

def print_banner(encoder_choice: str):
    suffix = "_x265" if encoder_choice == "x265" else f"_x265_{encoder_choice}"
    line = "=" * 64
    print(line)
    print(f" {APP} v{VERSION}")
    print(line)
    print(f" Input   : {INPUT_DIR}")
    print(f" Output  : {OUTPUT_DIR}")
    print(f" Encoder : {ENCODER_NAMES.get(encoder_choice, encoder_choice)}")
    print(f" Suffix  : {suffix}")
    print(f" CRF     : {CRF}")
    print(f" Preset  : {PRESET}")
    print(f" Workers : 1")
    print(line)

def map_preset_nvenc(preset: str) -> str:
    p = preset.lower()
    if p in {"veryslow","slower","slow"}: return "p5"
    if p == "medium": return "p6"
    return "p7"

def map_preset_qsv(preset: str) -> str:
    p = preset.lower()
    if p in {"veryfast","faster","fast","medium"}: return p
    if p in {"slow","slower","veryslow"}: return "medium"
    return "fast"

def map_quality_amf(preset: str) -> str:
    p = preset.lower()
    if p in {"veryslow","slower","slow"}: return "quality"
    if p == "medium": return "balanced"
    return "speed"

def probe_codec(path: Path) -> dict:
    """Return basic stream info using ffprobe."""
    try:
        res = subprocess.run(
            ["ffprobe","-v","error","-print_format","json",
             "-show_streams","-select_streams","v:0", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, text=True
        )
        data = json.loads(res.stdout)
        return (data.get("streams") or [{}])[0]
    except Exception:
        return {}

def is_source_hevc(path: Path) -> bool:
    v = probe_codec(path)
    codec = (v.get("codec_name") or "").lower()
    return codec in {"hevc", "h265"}

def build_cmd(input_file: Path, output_file: Path, enc: str):
    # Keep everything we reasonably can
    common = [
        "-map", "0",
        "-map_chapters", "0",
        "-c:a", "copy",
        "-c:s", "copy",
        "-c:d", "copy",   # data streams
        "-c:t", "copy"    # attachments (fonts, etc.)
    ]

    if enc == "nvenc":
        # True constant quality behavior: b:v/maxrate = 0 with rc vbr + cq
        return ["ffmpeg","-y","-hide_banner","-stats",
                "-i", str(input_file),
                "-c:v", "hevc_nvenc",
                "-preset", map_preset_nvenc(PRESET),
                "-rc", "vbr", "-cq", CRF, "-b:v", "0", "-maxrate", "0",
                *common, str(output_file)]

    if enc == "qsv":
        # global_quality is QP-like; use LA if available (kept simple here)
        return ["ffmpeg","-y","-hide_banner","-stats",
                "-i", str(input_file),
                "-c:v", "hevc_qsv",
                "-preset", map_preset_qsv(PRESET),
                "-global_quality", CRF,
                *common, str(output_file)]

    if enc == "amf":
        # AMF CQ-ish mode via -q; ensure usage+quality
        return ["ffmpeg","-y","-hide_banner","-stats",
                "-i", str(input_file),
                "-c:v", "hevc_amf",
                "-usage", "transcoding",
                "-quality", map_quality_amf(PRESET),
                "-rc", "vbr", "-q", CRF,
                *common, str(output_file)]

    # CPU x265
    return ["ffmpeg","-y","-threads","0","-hide_banner","-stats",
            "-i", str(input_file),
            "-c:v","libx265","-preset",PRESET,"-crf",CRF,
            *common, str(output_file)]

def probe_encoder(enc: str) -> bool:
    try:
        if enc == "nvenc":
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","0.5","-c:v","hevc_nvenc","-f","null", NULLDEV()]
        elif enc == "qsv":
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","0.5","-c:v","hevc_qsv","-f","null", NULLDEV()]
        elif enc == "amf":
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","0.5","-c:v","hevc_amf","-f","null", NULLDEV()]
        else:
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","0.5","-c:v","libx265","-f","null", NULLDEV()]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return True
    except Exception:
        return False

def NULLDEV():
    return "NUL" if os.name == "nt" else "/dev/null"

def detect_encoder() -> str:
    for enc in ["nvenc","qsv","amf"]:
        if probe_encoder(enc):
            return enc
    return "x265"

def gather_inputs(inp: Path):
    if RECURSIVE:
        files = []
        for p in inp.rglob("*"):
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
                files.append(p)
        return sorted(files)
    return [p for p in sorted(inp.iterdir()) if p.is_file() and p.suffix.lower() in VIDEO_EXTS]

# ---------- ETA helpers ----------

TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)(?:\.(\d+))?", re.IGNORECASE)
SPEED_RE = re.compile(r"speed=\s*([0-9]*\.?[0-9]+)x", re.IGNORECASE)

def hms_to_seconds(h, m, s, ms="0") -> float:
    return int(h)*3600 + int(m)*60 + int(s) + (int(ms)/10**len(ms) if ms else 0.0)

def get_duration_seconds(path: Path) -> float:
    try:
        res = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, text=True
        )
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def format_eta(seconds_left: float) -> str:
    if seconds_left < 0: seconds_left = 0
    m, s = divmod(int(seconds_left), 60)
    h, m = divmod(m, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

def make_out_path(src: Path, root_in: Path, root_out: Path, enc: str) -> Path:
    rel = src.relative_to(root_in) if MIRROR_TREE else Path(src.name)
    stem = rel.stem
    suffix = "_x265" if enc == "x265" else f"_x265_{enc}"
    ext = ".mkv" if ALWAYS_MKV else rel.suffix
    out_rel = rel.with_name(f"{stem}{suffix}{ext}")
    return root_out / out_rel

def encode_one(src: Path, dst_dir: Path, enc: str, in_root: Path):
    out = make_out_path(src, in_root, dst_dir, enc)
    out.parent.mkdir(parents=True, exist_ok=True)

    if SKIP_IF_OUTPUT_EXISTS and out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        print(f"⏭️  Skipping (up-to-date): {src}")
        return True

    if SKIP_IF_SOURCE_HEVC and is_source_hevc(src):
        print(f"⏭️  Skipping (already HEVC): {src.name}")
        return True

    cmd = build_cmd(src, out, enc)

    total = get_duration_seconds(src) or None
    print(f"▶️  Encoding: {src}")
    if total:
        print(f"    Duration: {int(total//60)}m {int(total%60)}s")

    start_t = monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    cur_secs = 0.0
    cur_speed = 1.0

    try:
        while True:
            line = proc.stderr.readline()
            if not line:
                if proc.poll() is not None:
                    # ✅ Final bar update to 100% before leaving the loop
                    if total:
                        done = 1.0
                        bar_len = 28
                        bar = "█" * bar_len
                        print(f"\r    [{bar}] 100.0%  speed {cur_speed:>4.2f}x  ETA     0s",
                              end="", flush=True)
                    break
                continue

            tmatch = TIME_RE.search(line)
            if tmatch:
                cur_secs = hms_to_seconds(*tmatch.groups(default="0"))

            smatch = SPEED_RE.search(line)
            if smatch:
                try:
                    cur_speed = max(float(smatch.group(1)), 1e-6)
                except ValueError:
                    pass

            if total:
                done = max(0.0, min(cur_secs / total, 1.0))
                remaining = (total - cur_secs) / max(cur_speed, 1e-6)
                bar_len = 28
                filled = int(done * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r    [{bar}] {done*100:5.1f}%  speed {cur_speed:>4.2f}x  ETA {format_eta(remaining):>8}", end="", flush=True)

        proc.wait()
        if total:
            print()  # newline after progress row

        if proc.returncode == 0:
            elapsed = monotonic() - start_t
            print(f"✅ {src.name} → {out.name}  ({int(elapsed)//60}m {int(elapsed)%60}s)")
            return True
        else:
            err = proc.stderr.read()
            print(f"\n❌ {src.name} failed\n{err}\n")
            return False

    except KeyboardInterrupt:
        proc.kill()
        print("\n⏹️  Stopped by user.")
        return False

def main():
    if not _check_ffmpeg():
        sys.exit(1)

    in_dir  = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    enc = detect_encoder()
    print_banner(enc)

    files = gather_inputs(in_dir)
    if not files:
        print("No input videos found.")
        return

    ok = 0
    for f in files:
        if encode_one(f, out_dir, enc, in_dir):
            ok += 1
    fail = len(files) - ok
    print(f"Done. Success: {ok}, Failed: {fail}")

if __name__ == "__main__":
    main()
