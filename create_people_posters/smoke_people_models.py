"""Opt-in, offline DDColor -> BiRefNet Portrait -> Pillow integration smoke test."""

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageChops, ImageOps, ImageStat

from people_workspaces import atomic_json, reject_links

SCRIPT = Path(__file__).resolve()
BASE = SCRIPT.parent


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def color_metrics(path):
    with Image.open(path) as image:
        image.load()
        r,g,b = ImageOps.exif_transpose(image).convert("RGB").split()
        spread = ImageChops.difference(ImageChops.lighter(ImageChops.lighter(r,g),b),
                                      ImageChops.darker(ImageChops.darker(r,g),b))
        histogram = spread.histogram()
        return {"dimensions":list(r.size), "mode":image.mode,"format":image.format,
                "mean_channel_spread":ImageStat.Stat(spread).mean[0],
                "colored_fraction":sum(histogram[3:]) / (r.width*r.height),
                "luminance_range":list(ImageOps.grayscale(image).getextrema())}


def validate_grayscale(path):
    info = color_metrics(path)
    if info["mean_channel_spread"] != 0:
        raise ValueError("Supply a genuine grayscale photograph; the smoke test does not desaturate color inputs")
    if info["luminance_range"][1] - info["luminance_range"][0] < 32:
        raise ValueError("Input is too flat for a photographic smoke test")
    return info


def local_only(event, arguments):
    if event in {"socket.connect","socket.getaddrinfo"}:
        raise RuntimeError("Network disabled for the smoke test; install dependencies and cache models separately")


def run_stage(stage, workspace):
    reject_links(workspace)
    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("managed_by") != "kometa-model-smoke-v1":
        raise ValueError("Unrecognized smoke workspace")
    # No network, publishing, model downloads or normal pipeline staging.
    sys.addaudithook(local_only)
    source = workspace / manifest["input_copy"]
    if digest(source) != manifest["source_sha256"]:
        raise ValueError("Smoke input changed")
    started = time.perf_counter()
    if stage == "ddcolor":
        import colorize_noncolor_ddcolor as ddcolor
        model_dir = Path(manifest["ddcolor_model_dir"])
        if not ddcolor.valid_model_cache(model_dir):
            raise ValueError("Existing DDColor config.json/pytorch_model.bin cache is missing or invalid")
        if not (Path(manifest["vendor_dir"]) / "ddcolor").is_dir():
            raise ValueError("Existing DDColor vendor source is missing")
        colorizer = ddcolor.DDColorBatchColorizer(str(model_dir),manifest["ddcolor_device"],manifest["input_size"])
        observed = {"forward_calls":0}
        def forward(module, arguments, output):
            observed["forward_calls"] += 1
            observed["input_shape"] = list(arguments[0].shape)
            observed["output_shape"] = list(output.shape)
            observed["finite_output"] = bool(colorizer.torch.isfinite(output).all().item())
        hook = colorizer.pipeline.model.register_forward_hook(forward)
        try:
            destination = workspace / "colorized.jpg"
            colorizer.colorize(source,destination,manifest["jpeg_quality"])
        finally:
            hook.remove()
        metrics = color_metrics(destination)
        if (observed["forward_calls"] < 1 or not observed.get("finite_output")
                or not ddcolor.valid_output(destination,tuple(manifest["input_metrics"]["dimensions"]))
                or metrics["colored_fraction"] < 0.01 or metrics["mean_channel_spread"] <= 1):
            raise ValueError("DDColor inference/output/chroma validation failed: " + str((observed,metrics)))
        result = {**observed,"output":metrics,"sha256":digest(destination),"model_dir":str(model_dir),
                  "model_sha256":digest(model_dir / "pytorch_model.bin"),"torch":version("torch"),
                  "torchvision":version("torchvision"),"device":str(colorizer.device)}
    elif stage == "rembg":
        from remove_bg_birefnet import LocalRemover, Settings
        home = Path(manifest["rembg_home"])
        if not any(home.rglob("birefnet-portrait.onnx")):
            raise ValueError("Existing BiRefNet Portrait cache missing; cache the model before this offline test")
        remover = LocalRemover(Settings(model="birefnet-portrait",home=home))
        observed = {"onnx_run_calls":0}
        inner = remover.session.inner_session
        original = inner.run
        def run(*arguments,**keywords):
            output = original(*arguments,**keywords)
            observed["onnx_run_calls"] += 1
            return output
        inner.run = run
        try:
            result = remover.process(workspace / "colorized.jpg",workspace / "transparent.png")
            if result["status"] != "processed" or not observed["onnx_run_calls"]:
                raise ValueError("Expected fresh BiRefNet Portrait inference, not a cached/skipped output")
            result.update(observed)
        finally:
            inner.run = original
            remover.close()
    else:
        from create_people_poster import render_batch, STYLES, output_path
        config = workspace / "poster-job"
        root = config / "people_dirs"
        for kind in ("original","Downloads"):
            (root / kind).mkdir(parents=True,exist_ok=True)
        shutil.copyfile(workspace / "colorized.jpg",root / "original/Smoke Test.jpg")
        shutil.copyfile(workspace / "transparent.png",root / "Downloads/Smoke Test.png")
        result = render_batch(config,["Smoke Test"])
        if result["failed"] or result["processed"] != 1:
            raise ValueError("Python/Pillow poster validation failed: " + str(result))
        outputs = {}
        for style in STYLES:
            path = output_path(root,style,"Smoke Test")
            outputs[style] = {**color_metrics(path),"sha256":digest(path),"path":str(path)}
        if len(outputs) != 7:
            raise ValueError("Expected all seven local renderer outputs")
        result["outputs"] = outputs
    if digest(source) != manifest["source_sha256"]:
        raise ValueError("Input copy changed during smoke test")
    result.update(stage=stage,status="passed",seconds=round(time.perf_counter()-started,3),python=sys.executable)
    atomic_json(workspace / (stage + ".json"),result)
    print(json.dumps(result,indent=2,ensure_ascii=True))


def interpreter(name):
    path = BASE / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(path) if path.is_file() else sys.executable


def main(argv=None):
    from dotenv import load_dotenv
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--stage")
    if not bootstrap.parse_known_args(argv)[0].stage:
        load_dotenv(BASE / "config/.env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",action="store_true",help="Explicitly opt into real CPU/model inference")
    parser.add_argument("--input",type=Path,help="Unmodified genuine grayscale photograph; preserved in place")
    parser.add_argument("--workspace-root",type=Path,default=BASE / "config/smoke-tests")
    parser.add_argument("--ddcolor-python",default=interpreter(".venv-ddcolor"))
    parser.add_argument("--rembg-python",default=interpreter(".venv-rembg"))
    parser.add_argument("--vendor-dir",type=Path,default=Path(os.getenv("COLORIZE_DDCOLOR_VENDOR_DIR") or BASE / "config/vendor/DDColor"))
    parser.add_argument("--model-dir",type=Path,default=Path(os.getenv("COLORIZE_DDCOLOR_MODELS_DIR") or BASE / "config/models/ddcolor") / os.getenv("COLORIZE_MODEL","ddcolor_modelscope"))
    parser.add_argument("--rembg-home",type=Path,default=Path(os.getenv("REMBG_HOME") or BASE / "config/models/rembg"))
    parser.add_argument("--timeout",type=int,default=1800,help="Maximum seconds per isolated stage")
    parser.add_argument("--stage",choices=["ddcolor","rembg","render"],help=argparse.SUPPRESS)
    parser.add_argument("--workspace",type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.stage:
        if not args.run or not args.workspace:
            parser.error("Internal stages require explicit --run and --workspace")
        run_stage(args.stage,args.workspace.resolve())
        return 0
    if not args.run or not args.input or args.timeout <= 0:
        parser.error("Explicit --run, --input and a positive timeout are required")
    source = args.input.expanduser().resolve()
    reject_links(source)
    before = (digest(source),source.stat().st_mtime_ns)
    metrics = validate_grayscale(source)
    root = args.workspace_root.expanduser().absolute()
    reject_links(root)
    root.mkdir(parents=True,exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="ddcolor-",dir=root)).resolve()
    copy = workspace / ("input" + source.suffix.lower())
    shutil.copyfile(source,copy)
    manifest = {"managed_by":"kometa-model-smoke-v1","source":str(source),"source_sha256":before[0],
                "source_mtime_ns":before[1],"input_copy":copy.name,"input_metrics":metrics,
                "ddcolor_model_dir":str(args.model_dir.expanduser().resolve()),
                "vendor_dir":str(args.vendor_dir.expanduser().resolve()),
                "rembg_home":str(args.rembg_home.expanduser().resolve()),
                "ddcolor_device":os.getenv("COLORIZE_DEVICE","cpu"),
                "input_size":int(os.getenv("COLORIZE_INPUT_SIZE","512")),
                "jpeg_quality":int(os.getenv("COLORIZE_JPEG_QUALITY","95"))}
    atomic_json(workspace / "manifest.json",manifest)
    environment = dict(os.environ)
    for key in ("GITHUB_TOKEN","GH_TOKEN","TMDB_KEY"):
        environment.pop(key,None)
    environment.update(PEOPLE_CONFIG_DIR=str(workspace / "runtime"),
                       COLORIZE_DDCOLOR_VENDOR_DIR=manifest["vendor_dir"],
                       COLORIZE_VENDOR_DIR=str(Path(manifest["vendor_dir"]).parent),
                       COLORIZE_DDCOLOR_MODELS_DIR=str(Path(manifest["ddcolor_model_dir"]).parent),
                       COLORIZE_INPUT_OTHER=str(workspace / "unused-input"),
                       COLORIZE_OUTPUT_COLOR=str(workspace / "unused-output"),
                       HF_HOME=str(workspace / "cache/hf"),TORCH_HOME=str(workspace / "cache/torch"),
                       HF_HUB_OFFLINE="1",PYTHONIOENCODING="utf-8",PYTHONUNBUFFERED="1")
    summary = {"workspace":str(workspace),"status":"running","stages":{},"network":"disabled in stage processes"}
    print("[SMOKE] Isolated workspace: " + str(workspace),flush=True)
    try:
        for stage,python in (("ddcolor",args.ddcolor_python),("rembg",args.rembg_python),("render",args.rembg_python)):
            print("[SMOKE] Running real " + stage,flush=True)
            with (workspace / (stage + ".log")).open("w",encoding="utf-8") as log:
                completed = subprocess.run([python,str(SCRIPT),"--run","--stage",stage,"--workspace",str(workspace)],
                                           env=environment,cwd=BASE,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            if completed.returncode:
                raise RuntimeError(f"{stage} exited {completed.returncode}; inspect {workspace / (stage + '.log')}")
            summary["stages"][stage] = json.loads((workspace / (stage + ".json")).read_text(encoding="utf-8"))
        summary["status"] = "passed"
    except Exception as error:
        summary.update(status="failed",error=str(error))
    finally:
        summary["source_unchanged"] = source.is_file() and before == (digest(source),source.stat().st_mtime_ns)
        if not summary["source_unchanged"]:
            summary.update(status="failed",error="Original smoke source changed; inspect before further testing")
        atomic_json(workspace / "summary.json",summary)
    print(json.dumps({k:v for k,v in summary.items() if k != "stages"},indent=2))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
