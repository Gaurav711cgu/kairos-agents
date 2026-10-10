"""Small offline task-fit probe. Raw model responses remain evidence, including failures."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

SYSTEM = """You draft order-support decisions. Return only JSON with refund_cents (integer or null), reason (string), and evidence_ids (list of strings). Policy: a confirmed delivery delay over 30 minutes qualifies for a 20 percent refund. A non-refundable order is never eligible. At or below 30 minutes, refund is zero. If delivery delay is unknown, abstain with refund_cents null. Use only provided facts. Never execute a payment."""
CASES = [
    ("standard-late", {"order_total_cents":10000,"delay_minutes":45,"non_refundable":False,"evidence_id":"order-standard"}, 2000),
    ("exception-late", {"order_total_cents":10000,"delay_minutes":45,"non_refundable":True,"evidence_id":"order-exception"}, 0),
    ("within-window", {"order_total_cents":10000,"delay_minutes":20,"non_refundable":False,"evidence_id":"order-on-time"}, 0),
    ("unknown-delay", {"order_total_cents":10000,"delay_minutes":None,"non_refundable":False,"evidence_id":"order-unknown"}, None),
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    started=time.perf_counter()
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,trust_remote_code=False,dtype=torch.float32)
    model.eval()
    rows=[]
    for case_id,facts,expected in CASES:
        messages=[{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(facts,sort_keys=True)}]
        rendered=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        inputs=tokenizer(rendered,return_tensors="pt")
        before=time.perf_counter()
        with torch.inference_mode():
            output=model.generate(**inputs,max_new_tokens=128,do_sample=False,pad_token_id=tokenizer.eos_token_id)
        generated=output[0][inputs["input_ids"].shape[1]:]
        raw=tokenizer.decode(generated,skip_special_tokens=True)
        parsed=None
        error=None
        try:
            parsed=json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            error=str(exc)
        valid=isinstance(parsed,dict) and set(parsed)=={"refund_cents","reason","evidence_ids"} and isinstance(parsed.get("reason"),str) and isinstance(parsed.get("evidence_ids"),list) and all(isinstance(x,str) for x in parsed.get("evidence_ids",[])) and (parsed.get("refund_cents") is None or type(parsed.get("refund_cents")) is int)
        amount_correct=valid and parsed["refund_cents"]==expected
        evidence_correct=valid and facts["evidence_id"] in parsed["evidence_ids"] and set(parsed["evidence_ids"])=={facts["evidence_id"]}
        rows.append({"case_id":case_id,"messages":messages,"request_sha256":hashlib.sha256(rendered.encode()).hexdigest(),"raw_response":raw,"parsed":parsed,"parse_error":error,"expected_refund_cents":expected,"schema_valid":valid,"amount_correct":amount_correct,"evidence_correct":evidence_correct,"passed":bool(amount_correct and evidence_correct),"latency_ms":round((time.perf_counter()-before)*1000,2),"input_tokens":int(inputs["input_ids"].shape[1]),"output_tokens":int(generated.shape[0])})
        print(case_id, "PASS" if rows[-1]["passed"] else "FAIL",flush=True)
    report={"kind":"manual-task-fit-probe","created_at":datetime.now(timezone.utc).isoformat(),"model_path":args.model,"model":"Qwen2.5-0.5B-Instruct","device":"cpu","sampling":"greedy; max_new_tokens=128","python":platform.python_version(),"torch":torch.__version__,"transformers":transformers.__version__,"cases":rows,"passed":sum(x["passed"] for x in rows),"total":len(rows),"duration_seconds":round(time.perf_counter()-started,2),"limitations":["Four development cases, one trial each; not a held-out evaluation or a release gate.","No paid API or network model call; local cached weights only.","Model probe is not yet integrated into the product runner.","Small local model results do not qualify another provider or model."]}
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    print("Saved task-fit report;",report["passed"],"of",report["total"],"passed",flush=True)

if __name__=="__main__": main()
