"""v2 pipeline tests: workflow wiring, ComfyUI client behaviour, timeline maths, captions,
and the safety properties the v2 code relies on.

Runs without a GPU, ComfyUI or models: ComfyUI is replaced by a tiny fake HTTP server.

    venv311\\Scripts\\python.exe app\\backend\\tests\\test_v2_pipeline.py
    (or: python -m pytest app/backend/tests/test_v2_pipeline.py)
"""
import ast
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.backend.pipeline import story_edit as E  # noqa: E402
from app.backend.pipeline import comfy_client as C  # noqa: E402
from app.backend.pipeline import wan_client, image_client, smooth_client, music_client  # noqa: E402

WF = ROOT / "app" / "workflows"


# ----------------------------------------------------------------------------- workflows


def _links_resolve(wf: dict):
    for nid, node in wf.items():
        for name, val in node["inputs"].items():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                assert val[0] in wf, f"{nid}.{name} links to missing node {val[0]}"


def test_every_workflow_is_valid_api_json_with_resolving_links():
    files = sorted(WF.glob("*.json"))
    assert len(files) >= 5, files
    for f in files:
        wf = json.loads(f.read_text(encoding="utf-8"))
        for nid, node in wf.items():
            assert "class_type" in node and "inputs" in node, f"{f.name}:{nid}"
        _links_resolve(wf)


def test_wan_t2v_and_i2v_build():
    tpl = C.load_workflow("wan22_ti2v_5b_gguf.json")
    wf = wan_client.build_workflow(tpl, "a boat", 481, 833, 121, 20, 7)
    assert wf["latent"]["inputs"]["width"] == 480 and wf["latent"]["inputs"]["height"] == 832
    assert "start_image" not in wf["latent"]["inputs"]
    neg = tpl["negative"]["inputs"]["text"]
    assert wf["negative"]["inputs"]["text"] == neg, "negative prompt must not be overwritten"
    wf2 = wan_client.build_workflow(tpl, "a boat", 480, 832, 121, 20, 7, start_image="aivs_x.png")
    assert wf2["latent"]["inputs"]["start_image"] == ["start", 0]
    assert wf2["start"]["class_type"] == "LoadImage"
    _links_resolve(wf2)
    assert "start" not in tpl, "template must not be mutated"


def test_frames_rule():
    for s in (0.1, 1, 2.5, 5, 5.04):
        n = wan_client.frames_for_seconds(s)
        assert (n - 1) % 4 == 0 and n >= 5
    assert wan_client.frames_for_seconds(5.0) == 121


def test_image_modes():
    tpl = C.load_workflow("flux_kontext_gguf.json")
    try:
        image_client.build_workflow(tpl, "kontext", "x", 768, 1344, 1)
        raise AssertionError("kontext without a reference must fail")
    except ValueError:
        pass
    wf = image_client.build_workflow(tpl, "kontext", "x", 770, 1350, 1, reference="aivs_r.png")
    assert wf["ref"]["inputs"]["image"] == "aivs_r.png"
    assert wf["latent"]["inputs"]["width"] % 16 == 0 and wf["latent"]["inputs"]["height"] % 16 == 0
    w, h = image_client.keyframe_size(480, 832)
    assert w % 16 == 0 and h % 16 == 0 and abs(w / h - 480 / 832) < 0.03 and 0.8e6 < w * h < 1.2e6


def test_smooth_without_upscale_rewires():
    tpl = C.load_workflow("rife_upscale.json")
    wf = smooth_client.build_workflow(tpl, "clip.mp4", upscale=False)
    assert wf["video"]["inputs"]["images"] == ["rife", 0] and "upscale" not in wf
    _links_resolve(wf)
    wf = smooth_client.build_workflow(tpl, "clip.mp4", fps=48)
    assert wf["video"]["inputs"]["fps"] == 48.0 and wf["load"]["inputs"]["file"] == "clip.mp4"


def test_music_length_clamped():
    tpl = C.load_workflow("ace_step_music.json")
    assert music_client.build_workflow(tpl, "x", 1)["latent"]["inputs"]["seconds"] == 5.0
    assert music_client.build_workflow(tpl, "x", 10_000)["latent"]["inputs"]["seconds"] == 600.0
    assert music_client.build_workflow(tpl, "x", 79.3)["positive"]["inputs"]["lyrics"] == "[inst]"


def test_set_inputs_rejects_unknown_node():
    try:
        C.set_inputs({"a": {"inputs": {}}}, {"b": {"x": 1}})
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


# ----------------------------------------------------------------------------- fake ComfyUI


class _Fake(BaseHTTPRequestHandler):
    mode = "ok"
    uploads: list = []

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n)
        if self.path == "/prompt":
            if _Fake.mode == "reject":
                return self._json({"error": "node_errors: bad"}, 400)
            return self._json({"prompt_id": "p1"})
        if self.path == "/upload/image":
            _Fake.uploads.append(data)
            return self._json({"name": "stored.png", "subfolder": "", "type": "input"})
        return self._json({})

    def do_GET(self):
        if self.path.startswith("/history/"):
            if _Fake.mode == "error":
                return self._json({"p1": {"status": {"status_str": "error", "messages": [
                    ["execution_error", {"node_id": "sampler", "node_type": "KSampler",
                                         "exception_message": "CUDA out of memory"}]]}}})
            if _Fake.mode == "pending":
                return self._json({})
            return self._json({"p1": {"status": {"completed": True, "status_str": "success"},
                                      "outputs": {
                                          # LoadVideo lists its *input* first; it must be skipped.
                                          "load": {"images": [{"filename": "in.mp4", "subfolder": "",
                                                               "type": "input"}]},
                                          "save": {"images": [
                                          {"filename": "x.mp4", "subfolder": "aivs", "type": "output",
                                           "animated": [True]}]}}}})
        if self.path.startswith("/view"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"VIDEO" if "filename=x.mp4" in self.path else b"WRONG FILE")
            return
        self._json({})


def _server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_client_finds_video_under_images_key_and_downloads():
    srv, url = _server()
    try:
        _Fake.mode = "ok"
        d = Path(tempfile.mkdtemp())
        out = C.ComfyClient(url).run({"a": {"class_type": "X", "inputs": {}}}, d / "o.mp4",
                                     C.VIDEO_EXT, timeout_s=10)
        assert out.read_bytes() == b"VIDEO" and not (d / "o.mp4.part").exists()
    finally:
        srv.shutdown()


def test_client_surfaces_comfy_errors_and_rejections_and_times_out():
    srv, url = _server()
    try:
        c = C.ComfyClient(url)
        _Fake.mode = "error"
        try:
            c.run({}, Path(tempfile.mkdtemp()) / "o.mp4", C.VIDEO_EXT, timeout_s=10)
            raise AssertionError("expected ComfyError")
        except C.ComfyError as e:
            assert "CUDA out of memory" in str(e) and "KSampler" in str(e)
        _Fake.mode = "reject"
        try:
            c.submit({})
            raise AssertionError("expected ComfyError")
        except C.ComfyError as e:
            assert "node_errors" in str(e)
        _Fake.mode = "pending"
        try:
            c.wait("p1", timeout_s=0.5, poll_s=0.1)
            raise AssertionError("expected TimeoutError")
        except TimeoutError:
            pass
    finally:
        srv.shutdown()


def test_upload_name_is_generated_not_taken_from_the_caller():
    srv, url = _server()
    try:
        d = Path(tempfile.mkdtemp())
        evil = d / "..%2f..%2fevil.png"
        evil.write_bytes(b"PNG")
        _Fake.uploads.clear()
        C.ComfyClient(url).upload(evil)
        body = _Fake.uploads[-1].decode("latin-1")
        assert 'filename="aivs_' in body and "evil" not in body and ".." not in body
    finally:
        srv.shutdown()


# ----------------------------------------------------------------------------- timeline


def test_timeline_adds_up_and_dissolves_land_on_line_starts():
    durs, pad, xf = [5.62, 4.47, 5.15], 0.35, 0.4
    slots = E.slots(durs, pad)
    assert slots[0] == (0.0, 5.97) and abs(slots[2][0] - (5.97 + 4.82)) < 1e-6
    segs = E.segment_lengths(durs, pad, xf)
    assert segs[-1] == round(durs[-1] + pad, 3) and segs[0] == round(durs[0] + pad + xf, 3)
    offsets = E.xfade_offsets(durs, pad)
    assert offsets == [s for s, _ in slots[1:]]
    # xfade output length = sum(segments) - n_dissolves * xfade = narration timeline length.
    assert abs((sum(segs) - xf * (len(durs) - 1)) - sum(d + pad for d in durs)) < 1e-6


def test_align_words_keeps_script_text_with_whisper_timing():
    heard = [{"word": "Long", "start": 0.1, "end": 0.4}, {"word": "ago,", "start": 0.45, "end": 0.8},
             {"word": "peeple", "start": 0.9, "end": 1.2}, {"word": "forgot", "start": 1.3, "end": 1.7}]
    out = E.align_words("Long ago, people forgot God.", heard, 10.0, 2.2)
    assert [w["word"] for w in out] == ["Long", "ago,", "people", "forgot", "God."]
    assert out[0]["start"] == 10.1 and out[3]["end"] == 11.7
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(out, out[1:]))
    assert 11.7 <= out[4]["start"] < out[4]["end"] <= 12.2 + 1e-6
    blind = E.align_words("one two three", [], 0.0, 3.0)
    assert blind[0]["start"] == 0.0 and abs(blind[-1]["end"] - 3.0) < 1e-6


def test_chunks_never_leave_a_lone_word_and_break_on_sentences():
    ws = [{"word": w, "start": i, "end": i + 1} for i, w in
          enumerate("The rain fell. For forty days and nights".split())]
    chunks = E.chunk_words(ws, 3)
    assert all(len(c) > 1 for c in chunks), [[w["word"] for w in c] for c in chunks]
    assert chunks[0][-1]["word"] == "fell."
    # "...the great door closed." -> "door" + "closed." must not leave "closed." alone.
    ws = [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in
          enumerate("and every creature went inside, and the great door closed.".split())]
    chunks = E.chunk_words(ws, 3)
    assert all(len(c) > 1 for c in chunks), [[w["word"] for w in c] for c in chunks]
    assert [w["word"] for c in chunks for w in c] == [w["word"] for w in ws]


def test_ass_escaping_makes_hostile_text_literal():
    s = E.ass_escape("a{\\pos(0,0)}b\\N c}")
    assert "{" not in s.replace("\\{", "") and "}" not in s.replace("\\}", "")
    ass = E.build_ass([[{"word": "{\\an8}x", "start": 0, "end": 1}, {"word": "y", "start": 1, "end": 2}]],
                      1080, 1920)
    assert "\\{\\\\AN8\\}X" in ass, ass.splitlines()[-1]


def test_filters_parse_in_ffmpeg():
    if not shutil.which("ffmpeg"):
        return
    vf = E.segment_filter(5.04, 6.37, 1080, 1920, 48)
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=480x832:r=24:d=1",
                        "-vf", vf, "-frames:v", "3", "-f", "null", "-"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    graph = E.mix_filter(3.0)
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=3",
                        "-f", "lavfi", "-i", "sine=f=440:d=5", "-filter_complex", graph,
                        "-map", "[aout]", "-f", "null", "-"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ----------------------------------------------------------------------------- safety


def _py_files():
    for d in ("app/backend/pipeline", "app/backend/services", "scripts"):
        yield from (ROOT / d).glob("*.py")


def test_no_shell_true_anywhere_in_the_pipeline():
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                assert not (isinstance(node.value, ast.Constant) and node.value.value), f"shell=True in {f}"


def test_no_trust_remote_code_and_comfy_is_local_only():
    for f in _py_files():
        assert "trust_remote_code=True" not in f.read_text(encoding="utf-8"), f
    assert C.COMFYUI_URL.startswith("http://127.0.0.1")
    src = (ROOT / "app/backend/services/comfyui_manager.py").read_text(encoding="utf-8")
    assert '"--listen", "127.0.0.1"' in src


def test_setup_models_refuses_foreign_hosts_and_escaping_paths():
    sys.path.insert(0, str(ROOT / "scripts"))
    import setup_models as S
    for bad in ("http://huggingface.co/x", "https://evil.example/x.gguf", "file:///etc/passwd"):
        try:
            S.check_url(bad)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    S.check_url("https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/x.gguf")
    try:
        S.safe_dest({"install_path": "../../outside", "file": "x.bin"})
        raise AssertionError("path escape accepted")
    except ValueError:
        pass
    catalog = json.loads((ROOT / "installer/catalog.json").read_text(encoding="utf-8"))
    for m in catalog["models"]:
        for f in m.get("files", []):
            S.check_url(S.file_url(f))
            S.safe_dest(f)


def test_story_character_keys_cannot_become_paths():
    sys.path.insert(0, str(ROOT / "scripts"))
    import render_story as R
    d = Path(tempfile.mkdtemp())
    p = d / "s.json"
    p.write_text(json.dumps({"style": "x", "scenes": [{"narration": "a", "prompt": "b"}],
                             "characters": {"../../x": {"description": "y"}}}))
    try:
        R.load_story(p)
        raise AssertionError("path-like character key accepted")
    except SystemExit:
        pass


def test_sample_story_loads():
    sys.path.insert(0, str(ROOT / "scripts"))
    import render_story as R
    s = R.load_story(ROOT / "stories" / "noahs_ark.json")
    assert s["characters"] and len(s["scenes"]) >= 10
    for sc in s["scenes"]:
        assert "{" not in R.fill(sc["prompt"], s), sc["prompt"]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failed)} passed, {len(failed)} failed")
    raise SystemExit(1 if failed else 0)
