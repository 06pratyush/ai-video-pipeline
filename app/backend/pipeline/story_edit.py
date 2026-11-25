"""v2 edit: word-synced captions, crossfades, gentle camera push, music ducked under voice.

Everything here builds data or FFmpeg argument lists; nothing goes through a shell, and
caption text is escaped for ASS so a quote, brace or backslash in a script is just text.

Timeline model: scene ``i`` has a narration line of ``dur[i]`` seconds plus ``pad`` of
breath, so it occupies ``[T_i, T_i + L_i)`` with ``L_i = dur[i] + pad``. Each video segment
is rendered ``xfade`` seconds longer than its slot (except the last) and the next scene
dissolves in over that extra tail, so the picture changes exactly when the next line
starts and the total length equals the narration timeline.
"""
from __future__ import annotations

import difflib
import re

# --------------------------------------------------------------------------- timeline


def slots(durations: list[float], pad: float) -> list[tuple[float, float]]:
    """(start, length) of each scene on the timeline."""
    out, t = [], 0.0
    for d in durations:
        out.append((round(t, 3), round(d + pad, 3)))
        t += d + pad
    return out


def segment_lengths(durations: list[float], pad: float, xfade: float) -> list[float]:
    lens = [d + pad for d in durations]
    return [round(l + (xfade if i < len(lens) - 1 else 0.0), 3) for i, l in enumerate(lens)]


def xfade_offsets(durations: list[float], pad: float) -> list[float]:
    """Offset of each dissolve = start time of the next scene."""
    return [s for s, _ in slots(durations, pad)[1:]]


# --------------------------------------------------------------------------- words


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


def align_words(script_text: str, heard: list[dict], line_start: float,
                line_dur: float) -> list[dict]:
    """Put whisper's timings on the *script's* words (so captions never show a mishearing).

    Matched words take whisper's times; unmatched words are spread between their matched
    neighbours. With no whisper words at all, timing falls back to word-length proportion.
    """
    words = script_text.split()
    if not words:
        return []
    times: list[tuple[float, float] | None] = [None] * len(words)
    if heard:
        sm = difflib.SequenceMatcher(a=[_norm(w) for w in words],
                                     b=[_norm(h["word"]) for h in heard], autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            for k in range(n):
                h = heard[b + k]
                times[a + k] = (h["start"], h["end"])
    # Fill gaps by interpolating between known anchors (or the line's edges).
    weights = [max(1, len(_norm(w))) for w in words]
    i = 0
    while i < len(words):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 else 0.0
        right = times[j][0] if j < len(words) else line_dur
        right = max(right, left + 0.05 * (j - i))
        total = sum(weights[i:j])
        t = left
        for k in range(i, j):
            span = (right - left) * weights[k] / total
            times[k] = (t, t + span)
            t += span
        i = j
    return [{"word": w, "start": round(line_start + s, 3), "end": round(line_start + e, 3)}
            for w, (s, e) in zip(words, times)]


def chunk_words(words: list[dict], size: int = 3) -> list[list[dict]]:
    """Groups of ~``size`` words, breaking early after sentence punctuation, never a lone word."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= size or w["word"][-1:] in ".!?;:":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # A lone word reads as a stutter: join it to the chunk it is closest to in time.
    merged: list[list[dict]] = []
    for ch in chunks:
        if len(ch) == 1 and merged and ch[0]["start"] - merged[-1][-1]["end"] < 0.6:
            merged[-1].extend(ch)
        else:
            merged.append(ch)
    out: list[list[dict]] = []
    for k, ch in enumerate(merged):
        if len(ch) == 1 and k + 1 < len(merged):
            merged[k + 1][:0] = ch
        else:
            out.append(ch)
    return out


# --------------------------------------------------------------------------- captions


def ass_escape(text: str) -> str:
    """Make arbitrary text literal inside an ASS Dialogue line."""
    return (text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                .replace("\n", " ").replace("\r", " "))


def ass_time(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_ass(chunks: list[list[dict]], width: int, height: int,
              font: str = "Arial Black", size: int = 72, margin_v: int = 330,
              highlight: str = "&H0000D7FF&") -> str:
    """One Dialogue per spoken word: the whole chunk on screen, the active word highlighted.

    Colours are ASS &HBBGGRR&: white text, black outline, highlight defaults to amber.
    """
    head = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,6,2,2,60,60,{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for chunk in chunks:
        for k, w in enumerate(chunk):
            end = chunk[k + 1]["start"] if k + 1 < len(chunk) else w["end"]
            end = max(end, w["start"] + 0.06)
            parts = []
            for m, x in enumerate(chunk):
                t = ass_escape(x["word"].upper())
                parts.append(f"{{\\c{highlight}}}{t}{{\\c&H00FFFFFF&}}" if m == k else t)
            lines.append(f"Dialogue: 0,{ass_time(w['start'])},{ass_time(end)},Cap,,0,0,0,,"
                         + " ".join(parts))
    return head + "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- ffmpeg


def segment_filter(clip_len: float, seg_len: float, out_w: int, out_h: int, fps: int,
                   push: float = 0.05, max_slow: float = 1.15) -> str:
    """Video filter for one scene: fit length, scale to the frame, slow camera push.

    The clip is slowed by at most ``max_slow``; any remaining time holds the last frame,
    and the continuous push keeps even that hold moving, so nothing ever freezes.
    """
    slow = max(1.0, min(seg_len / max(clip_len, 0.1), max_slow))
    z = f"(1+{push:.4f}*t/{seg_len:.3f})"
    return (
        f"setpts={slow:.4f}*PTS,fps={fps},"
        f"scale={out_w}:{out_h}:flags=lanczos:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h},"
        f"tpad=stop_mode=clone:stop_duration={seg_len:.3f},trim=duration={seg_len:.3f},"
        f"scale=w='trunc({out_w}*{z}/2)*2':h='trunc({out_h}*{z}/2)*2':eval=frame:flags=lanczos,"
        f"crop={out_w}:{out_h},setsar=1,format=yuv420p"
    )


def xfade_graph(n: int, offsets: list[float], xfade: float) -> tuple[str, str]:
    """filter_complex chaining ``n`` inputs with dissolves. Returns (graph, output label)."""
    if n == 1:
        return "[0:v]null[vout]", "[vout]"
    parts, prev = [], "[0:v]"
    for i in range(1, n):
        out = "[vout]" if i == n - 1 else f"[x{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xfade:.3f}:"
                     f"offset={offsets[i - 1]:.3f}{out}")
        prev = out
    return ";".join(parts), "[vout]"


def mix_filter(total: float, voice: str = "[0:a]", music: str = "[1:a]",
               music_db: float = -12.0) -> str:
    """voice + music -> [aout]: music ducked whenever the voice speaks, faded in and out,
    whole mix loudness-normalised to -14 LUFS (YouTube/Shorts target)."""
    fade_out_at = max(0.0, total - 2.5)
    return (
        # amix takes its layout from the first input: lift the mono voice to stereo (centred)
        # so the music keeps its width instead of being folded down to mono.
        f"{voice}aresample=48000,aformat=channel_layouts=stereo,asplit=2[vkey][vmix];"
        f"{music}aresample=48000,aformat=channel_layouts=stereo,atrim=duration={total:.3f},volume={music_db}dB,"
        f"afade=t=in:d=1.5,afade=t=out:st={fade_out_at:.3f}:d=2.5[m];"
        "[m][vkey]sidechaincompress=threshold=0.03:ratio=8:attack=30:release=500[duck];"
        "[vmix][duck]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    )
