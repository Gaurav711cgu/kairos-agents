#!/usr/bin/env python3
"""Offline bounded CPU inference service. Run with a torch/transformers environment."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time


GENERATION_BUDGET_SECONDS = 60


def generation_finish_reason(tail, eos_token_id, maximum, elapsed_seconds):
    """Report the observable stopping condition without repairing incomplete output."""
    eos_ids = {eos_token_id} if isinstance(eos_token_id, int) else set(eos_token_id or [])
    if len(tail) and int(tail[-1]) in eos_ids:
        return "eos"
    if len(tail) >= maximum:
        return "max_tokens"
    if elapsed_seconds >= GENERATION_BUDGET_SECONDS:
        return "time_budget"
    return "stopped"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8120)
    args = parser.parse_args()
    import torch
    import transformers
    model_dir = Path(args.model).resolve()
    manifest = {}
    for filename in ("config.json","tokenizer.json","tokenizer_config.json","model.safetensors"):
        candidate = model_dir / filename
        if candidate.exists():
            hasher = hashlib.sha256()
            with candidate.open("rb") as source:
                for chunk in iter(lambda:source.read(1024*1024),b""):
                    hasher.update(chunk)
            manifest[filename] = hasher.hexdigest()
    revision = hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    torch.set_num_threads(4)
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_dir,local_files_only=True,trust_remote_code=False)
    model = transformers.AutoModelForCausalLM.from_pretrained(model_dir,local_files_only=True,trust_remote_code=False,
                                                           dtype=torch.float32).eval()
    semaphore = threading.BoundedSemaphore(1)
    busy = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def reply(self,status,value):
            data = json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass

        def do_GET(self):
            if self.path != "/health":
                return self.reply(404,{"detail":"Unknown endpoint"})
            return self.reply(200,{"status":"ready","model":"Qwen2.5-0.5B-Instruct","model_revision":revision,
                                  "runtime":"offline-cpu","torch":torch.__version__,"transformers":transformers.__version__,
                                  "busy":busy.is_set(),"generation_budget_seconds":GENERATION_BUDGET_SECONDS})

        def do_POST(self):
            if self.path != "/generate":
                return self.reply(404,{"detail":"Unknown endpoint"})
            try:
                length = int(self.headers.get("Content-Length","0"))
                if not 1 <= length <= 32768:
                    return self.reply(413,{"detail":"Request exceeds bounded context budget"})
                request = json.loads(self.rfile.read(length))
                messages = request["messages"]
                maximum = request.get("max_tokens",128)
                if not isinstance(messages,list) or not 1 <= len(messages) <= 8 or any(not isinstance(m,dict) or set(m) != {"role","content"} or m["role"] not in {"system","user","assistant"} or not isinstance(m["content"],str) for m in messages):
                    raise ValueError()
                if type(maximum) is not int or not 1 <= maximum <= 128 or request.get("temperature",0) != 0:
                    raise ValueError()
                rendered = tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
                inputs = tokenizer(rendered,return_tensors="pt")
                if inputs["input_ids"].shape[1] > 2048:
                    return self.reply(413,{"detail":"Input token budget exceeded"})
            except (ValueError,KeyError,TypeError):
                return self.reply(400,{"detail":"Invalid bounded generation request"})
            if not semaphore.acquire(blocking=False):
                return self.reply(429,{"detail":"Inference slot busy; no hidden queue"})
            busy.set()
            try:
                started = time.perf_counter()
                with torch.inference_mode():
                    generated = model.generate(**inputs,max_new_tokens=maximum,max_time=GENERATION_BUDGET_SECONDS,do_sample=False,
                                               pad_token_id=tokenizer.eos_token_id)
                tail = generated[0][inputs["input_ids"].shape[1]:]
                raw = tokenizer.decode(tail,skip_special_tokens=True)
                elapsed = time.perf_counter()-started
                self.reply(200,{"raw_response":raw,"rendered_request":rendered,
                    "model":"Qwen2.5-0.5B-Instruct","model_revision":revision,"model_file_digests":manifest,
                    "input_tokens":inputs["input_ids"].shape[1],"output_tokens":len(tail),
                    "duration_ms":round(elapsed*1000,3),
                    "finish_reason":generation_finish_reason(tail,tokenizer.eos_token_id,maximum,elapsed),
                    "generation_budget_seconds":GENERATION_BUDGET_SECONDS,
                    "runtime":{"device":"cpu","dtype":"float32","threads":4,"temperature":0,
                               "max_new_tokens":maximum,"max_time_seconds":GENERATION_BUDGET_SECONDS,
                               "time_budget_semantics":"Cooperative token-boundary stop; one model forward pass may overrun.",
                               "torch":torch.__version__,"transformers":transformers.__version__}})
            except Exception:
                self.reply(500,{"detail":"Inference failed; dispatch outcome must remain explicit"})
            finally:
                busy.clear()
                semaphore.release()

    server = ThreadingHTTPServer((args.host,args.port),Handler)
    server.daemon_threads = True
    print(f"Offline model ready on {args.host}:{args.port}; revision={revision}",flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
