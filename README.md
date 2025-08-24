# 🎥 x265-AutoEncoder

Batch re-encode your video library into **HEVC/x265** with automatic hardware acceleration support.  
Preserves **all audio tracks, subtitles, chapters, and attachments** while shrinking video size.  

---

## ✨ Features
- 🚀 **Automatic encoder detection**  
  Chooses the best available backend:  
  - NVIDIA (NVENC)  
  - Intel (QSV)  
  - AMD (AMF)  
  - CPU fallback (libx265)  

- 📂 **Batch processing**  
  Encode all video files in a folder at once.  

- 🔊 **Lossless audio/subs**  
  Audio, subtitles, chapters, and attachments are copied without re-encoding.  

- 📝 **Smart filenames**  
  Output names include `_x265`, with backend suffix if hardware was used  
  (e.g. `Movie_x265_nvenc.mkv`, `Episode_x265_qsv.mkv`).  

- 📊 **Live progress bar**  
  Shows percentage, current speed (e.g. `2.4x`), and ETA per file.  

- ⚡ **CRF-based quality**  
  Default: `CRF=21`, `preset=slow` (visually lossless).  

---

## 📦 Requirements
- Python 3.8+  
- [FFmpeg + FFprobe](https://ffmpeg.org/download.html) in PATH  

Check installation with:
```bash
ffmpeg -version
ffprobe -version
```

---

## 🚀 Usage
1. Clone this repo:
   ```bash
   git clone https://github.com/ittudeitachi/x265-AutoEncoder
   cd x265-AutoEncoder
   ```

2. Install dependencies (none beyond Python stdlib + ffmpeg in PATH).  

3. Edit **`main.py`** to set your input/output directories:
   ```python
   INPUT_DIR  = r"C:\Users\You\Videos\Input"
   OUTPUT_DIR = r"C:\Users\You\Videos\Output"
   ```

4. Run:
   ```bash
   python main.py
   ```

---

## 📊 Example Output
```
============================================================
 x265-AutoEncoder v1.3.0
============================================================
 Input   : C:\Users\You\Videos\Input
 Output  : C:\Users\You\Videos\Output
 Encoder : Intel (QSV)
 Suffix  : _x265_qsv
 CRF     : 21
 Preset  : slow
 Workers : 1
============================================================
▶️  Encoding: Love Island (US) - S07E01 - Episode 1.mkv
    Duration: 103m 5s
    [██████░░░░░░░░░░░░░░░░░░░]  25.3%  speed 2.45x  ETA  28m 42s
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).  
You must include attribution to the original project:  
**“x265-AutoEncoder by Ibrahim Irusham Rashad”** in your documentation or user interface if you distribute this software or any derivative work.

---

## 🙏 Acknowledgments
- **FFmpeg** — for the powerful audio/video toolkit  

> This project is not affiliated with or endorsed by FFmpeg. This tool is for educational and personal use only. 
