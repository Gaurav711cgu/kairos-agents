/* global ReadableStream, TextEncoder, Request */
import { test } from "node:test";
import assert from "node:assert/strict";
import { boundedBody, BodyLimitError } from "./bounded-body.ts";
function streamed(chunks, headers = {}) {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk)); },
    cancel() { cancelled = true; },
  });
  return { request: new Request("http://localhost/command", { method: "POST", body, headers, duplex: "half" }), cancelled: () => cancelled };
}
test("chunked body cancels at byte budget even with false length", async () => {
  const value = streamed(["a".repeat(16000), "b".repeat(17000)], {"Content-Length":"1"});
  await assert.rejects(boundedBody(value.request), BodyLimitError);
  assert.equal(value.cancelled(), true);
});
test("UTF8 budget counts bytes, not characters", async () => {
  const value = streamed(["₹".repeat(11000)]);
  await assert.rejects(boundedBody(value.request), BodyLimitError);
});
test("bounded ordinary body retains exact bytes", async () => {
  const request = new Request("http://localhost", {method:"POST",body:'{"policy":"preserve","text":"₹"}'});
  assert.equal(await boundedBody(request), '{"policy":"preserve","text":"₹"}');
});
test("declared oversized body rejects before reading", async () => {
  const value = streamed(["a"], {"Content-Length":"99999"});
  await assert.rejects(boundedBody(value.request), BodyLimitError);
});
