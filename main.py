import os
import re
import subprocess
from pathlib import Path
from time import monotonic

TOOL_NAME = "x265-AutoEncoder"
VERSION   = "1.3.0"

# Edit these paths
INPUT_DIR  = r"C:\Users\iirusham\Downloads\Video\I"
OUTPUT_DIR = r"C:\Users\iirusham\Downloads\Video\O"

CRF    = "21"
PRESET = "slow"

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v"}

# Pretty names for banner display
ENCODER_NAMES = {
    "nvenc": "NVIDIA (NVENC)",
    "qsv":   "Intel (QSV)",
    "amf":   "AMD (AMF)",
    "x265":  "CPU (x265)"
}

def _check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg","-version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.run(["ffprobe","-version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return True
    except Exception:
        print("❌ FFmpeg/ffprobe not found. Install and add to PATH (ffmpeg/ffprobe -version).")
        return False

def print_banner(encoder_choice: str):
    suffix = "_x265" if encoder_choice == "x265" else f"_x265_{encoder_choice}"
    line = "=" * 60
    print(line)
    print(f" {TOOL_NAME} v{VERSION}")
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

def build_cmd(input_file: Path, output_file: Path, enc: str):
    # Keep all streams; copy audio & subs
    common = ["-map", "0", "-c:a", "copy", "-c:s", "copy"]

    if enc == "nvenc":
        return ["ffmpeg","-y","-hide_banner","-stats",
                "-i", str(input_file),
                "-c:v", "hevc_nvenc",
                "-preset", map_preset_nvenc(PRESET),
                "-rc", "vbr", "-cq", CRF,
                *common, str(output_file)]
    if enc == "qsv":
        return ["ffmpeg","-y","-hide_banner","-stats",
                "-i", str(input_file),
                "-c:v", "hevc_qsv",
                "-preset", map_preset_qsv(PRESET),
                "-global_quality", CRF,
                *common, str(output_file)]
    if enc == "amf":
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
                   "-t","1","-c:v","hevc_nvenc","-f","null","NUL"]
        elif enc == "qsv":
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","1","-c:v","hevc_qsv","-f","null","NUL"]
        elif enc == "amf":
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","1","-c:v","hevc_amf","-f","null","NUL"]
        else:
            cmd = ["ffmpeg","-hide_banner","-loglevel","error",
                   "-f","lavfi","-i","testsrc2=size=128x72:rate=10",
                   "-t","1","-c:v","libx265","-f","null","NUL"]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return True
    except Exception:
        return False

def detect_encoder() -> str:
    for enc in ["nvenc","qsv","amf"]:
        if probe_encoder(enc):
            return enc
    return "x265"

def gather_inputs(inp: Path):
    return [p for p in sorted(inp.iterdir()) if p.is_file() and p.suffix.lower() in VIDEO_EXTS]

# ---------- ETA helpers ----------

TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)(?:\.(\d+))?", re.IGNORECASE)
SPEED_RE = re.compile(r"speed=\s*([0-9]*\.?[0-9]+)x", re.IGNORECASE)

def hms_to_seconds(h, m, s, ms="0") -> float:
    return int(h)*3600 + int(m)*60 + int(s) + (int(ms)/10**len(ms) if ms else 0.0)

def get_duration_seconds(path: Path) -> float:
    """Return media duration in seconds using ffprobe (float)."""
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

# ---------- encode with live ETA ----------

def encode_one(src: Path, dst_dir: Path, enc: str):
    suffix = "_x265" if enc == "x265" else f"_x265_{enc}"
    out = dst_dir / f"{src.stem}{suffix}.mkv"
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_cmd(src, out, enc)

    total = get_duration_seconds(src)
    if total <= 0:
        # still encode, just without ETA
        total = None

    print(f"▶️  Encoding: {src.name}")
    if total:
        print(f"    Duration: {int(total//60)}m {int(total%60)}s")

    # Run ffmpeg and read stderr lines live
    start_t = monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    cur_secs = 0.0
    cur_speed = 1.0

    try:
        while True:
            line = proc.stderr.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue

            # Parse time= and speed=
            tmatch = TIME_RE.search(line)
            if tmatch:
                cur_secs = hms_to_seconds(*tmatch.groups(default="0"))

            smatch = SPEED_RE.search(line)
            if smatch:
                try:
                    cur_speed = float(smatch.group(1))
                    if cur_speed <= 0:
                        cur_speed = 1e-6
                except ValueError:
                    pass

            # Print ETA
            if total:
                done = max(0.0, min(cur_secs / total, 1.0))
                remaining = (total - cur_secs) / max(cur_speed, 1e-6)
                bar_len = 24
                filled = int(done * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r    [{bar}] {done*100:5.1f}%  speed {cur_speed:>4.2f}x  ETA {format_eta(remaining):>8}", end="", flush=True)

        proc.wait()
        print()  # newline after progress row

        if proc.returncode == 0:
            print(f"✅ {src.name} → {out.name}")
            return True
        else:
            # Read any remaining stderr for message
            err = proc.stderr.read()
            print(f"❌ {src.name} failed\n{err}\n")
            return False

    except KeyboardInterrupt:
        proc.kill()
        print("\n⏹️  Stopped by user.")
        return False

def main():
    if not _check_ffmpeg():
        return

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
        if encode_one(f, out_dir, enc):
            ok += 1
    fail = len(files) - ok
    print(f"Done. Success: {ok}, Failed: {fail}")

if __name__ == "__main__":
    main()
