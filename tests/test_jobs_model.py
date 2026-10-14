"""Contract and offline classification checks; not model-quality observations."""
import pytest
from kairos_api.model_runtime import BlobStore, classify_and_grade, model_request
from kairos_api.scenarios import get_scenario, assemble_context


def classify(scenario,raw,policy="preserve"):
    return classify_and_grade(scenario,assemble_context(get_scenario(scenario),policy),{"raw_response":raw})


def test_deterministic_arithmetic_and_independent_truth():
    result = classify("late-order-standard",'{"disposition":"refund","reason":"Late","evidence_ids":["policy.base","order.receipt"]}')
    assert result["decision"]["refund_cents"] == 360 and result["grade"]["passed"]
    failure = classify("late-order-exception",'{"disposition":"refund","reason":"Late","evidence_ids":["policy.base","order.receipt"]}',"compact")
    assert failure["decision"]["refund_cents"] == 480 and not failure["grade"]["passed"]
    abstain = classify("insufficient-evidence",'{"disposition":"abstain","reason":"Missing","evidence_ids":["policy.evidence","order.receipt"]}')
    assert abstain["decision"]["refund_cents"] is None and abstain["grade"]["passed"]


@pytest.mark.parametrize("raw",[
    "```json\n{}\n```", "{}", "[]",'{"disposition":"refund","reason":"x","evidence_ids":["invented"]}',
    '{"disposition":"refund","reason":"x","evidence_ids":[]}',
    '{"disposition":"refund","reason":"x","evidence_ids":["policy.base"],"refund_cents":999}',
    '{"disposition":"unknown","reason":"x","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"x","evidence_ids":["policy.base","policy.base"]}',
])
def test_strict_unrepaired_output_failures(raw):
    result = classify("late-order-standard",raw)
    assert result["decision"] is None and not result["grade"]["passed"] and result["parse_error"]


def test_omitted_exception_never_enters_model_request():
    blocks = assemble_context(get_scenario("late-order-exception"),"compact")
    request = model_request(blocks)
    assert "[policy.exception]" not in request["messages"][1]["content"]
    assert request["max_tokens"] == 128 and request["temperature"] == 0


def test_content_addressed_blob_atomic_capture_and_corruption(tmp_path):
    store = BlobStore(tmp_path)
    first = store.put({"raw_response":"exact\n spacing"})
    assert first == store.put({"raw_response":"exact\n spacing"})
    assert store.get(first["sha256"])["raw_response"] == "exact\n spacing"
    with pytest.raises(ValueError):
        store.get("../secret")
    (tmp_path/first["sha256"]).write_text("changed")
    with pytest.raises(ValueError,match="mismatch"):
        store.get(first["sha256"])


def test_reason_bound_and_required_disposition_provenance():
    import json
    long_reason = json.dumps({"disposition":"zero","reason":"x"*2001,"evidence_ids":["policy.exception"]})
    assert classify("late-order-exception",long_reason)["parse_error"]
    assert classify("late-order-exception",'{"disposition":"zero","reason":"Exception","evidence_ids":["order.receipt"]}')["parse_error"]
    assert classify("insufficient-evidence",'{"disposition":"abstain","reason":"Missing","evidence_ids":["order.receipt"]}')["parse_error"]


@pytest.mark.parametrize("raw",[
    '{"disposition":"refund","disposition":"zero","reason":"x","evidence_ids":["policy.base"]}',
    '{"disposition":"zero","reason":"x","evidence_ids":["policy.base"],"extra":NaN}',
])
def test_duplicate_and_nonfinite_json_rejected(raw):
    assert classify("late-order-standard",raw)["parse_error"]


@pytest.mark.parametrize("tail,eos,maximum,elapsed,expected",[
    ([1,2],2,128,61,"eos"),([1,2],3,2,61,"max_tokens"),
    ([1],2,128,60,"time_budget"),([1],2,128,1,"stopped"),
    ([1,2],[2,3],128,1,"eos"),
])
def test_offline_service_reports_observed_finish_without_repair(tail,eos,maximum,elapsed,expected):
    from scripts.serve_local_model import generation_finish_reason
    assert generation_finish_reason(tail,eos,maximum,elapsed) == expected



def test_model_http_slot_is_bounded_and_captures_budget_without_real_inference(tmp_path,monkeypatch):
    import contextlib
    from concurrent.futures import ThreadPoolExecutor
    from http.server import ThreadingHTTPServer
    import json
    import sys
    import threading
    from types import SimpleNamespace
    from urllib.error import HTTPError
    from urllib.request import Request,urlopen
    import scripts.serve_local_model as service
    started,release = threading.Event(),threading.Event()
    observed = {}
    class FakeModel:
        def eval(self):
            return self
        def generate(self,**kwargs):
            observed.update(kwargs)
            started.set()
            assert release.wait(5)
            return [[10,11,12,5,2]]
    class FakeTokenizer:
        eos_token_id = 2
        def apply_chat_template(self,*args,**kwargs):
            return "exact rendered request"
        def __call__(self,*args,**kwargs):
            return {"input_ids":SimpleNamespace(shape=(1,3))}
        def decode(self,*args,**kwargs):
            return "exact raw response"
    monkeypatch.setitem(sys.modules,"torch",SimpleNamespace(__version__="fixture",float32="fixture",set_num_threads=lambda _:None,inference_mode=contextlib.nullcontext))
    monkeypatch.setitem(sys.modules,"transformers",SimpleNamespace(__version__="fixture",AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:FakeTokenizer()),AutoModelForCausalLM=SimpleNamespace(from_pretrained=lambda *a,**k:FakeModel())))
    class ServerReady(Exception):
        pass
    holder = {}
    def server_factory(address,handler):
        server = ThreadingHTTPServer(("127.0.0.1",0),handler)
        holder["server"] = server
        def ready():
            raise ServerReady()
        server.serve_forever = ready
        return server
    monkeypatch.setattr(service,"ThreadingHTTPServer",server_factory)
    monkeypatch.setattr(sys,"argv",["model-service","--model",str(tmp_path)])
    with pytest.raises(ServerReady):
        service.main()
    server = holder["server"]
    thread = threading.Thread(target=lambda:ThreadingHTTPServer.serve_forever(server),daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = json.dumps({"messages":[{"role":"user","content":"classify"}],"max_tokens":128,"temperature":0}).encode()
    def post():
        with urlopen(Request(base+"/generate",data=payload,headers={"Content-Type":"application/json"}),timeout=5) as response:
            return json.load(response)
    try:
        assert not json.load(urlopen(base+"/health",timeout=2))["busy"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(post)
            assert started.wait(3)
            assert json.load(urlopen(base+"/health",timeout=2))["busy"]
            with pytest.raises(HTTPError) as rejected:
                post()
            assert rejected.value.code == 429
            release.set()
            capture = result.result(timeout=5)
        assert observed["max_time"] == 60 and observed["max_new_tokens"] == 128
        assert capture["raw_response"] == "exact raw response"
        assert capture["rendered_request"] == "exact rendered request"
        assert capture["finish_reason"] == "eos" and capture["generation_budget_seconds"] == 60
        assert capture["runtime"]["max_time_seconds"] == 60
        assert not json.load(urlopen(base+"/health",timeout=2))["busy"]
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
