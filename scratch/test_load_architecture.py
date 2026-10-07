#!/usr/bin/env python3
import asyncio
import time
import os
import json
import subprocess
import resource
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import tenseal as ts

ROOT_DIR = Path(__file__).resolve().parent.parent

# 1. Setup TenSEAL context
context = ts.context(
    ts.SCHEME_TYPE.CKKS,
    poly_modulus_degree=8192,
    coeff_mod_bit_sizes=[60, 40, 40, 60]
)
context.generate_galois_keys()
context.global_scale = 2**40

v1 = np.random.randn(256).astype(np.float64)
v1 /= np.linalg.norm(v1)
v2 = np.random.randn(256).astype(np.float64)
v2 /= np.linalg.norm(v2)

ct1 = ts.ckks_vector(context, v1)
ct2 = ts.ckks_vector(context, v2)
enrolled_bytes = ct1.serialize()
probe_bytes = ct2.serialize()

server_ctx = context.copy()
server_ctx.make_context_public()
enrolled_vec = ts.ckks_vector_from(server_ctx, enrolled_bytes)

executor = ThreadPoolExecutor(max_workers=4)

def do_dot_product(p_bytes):
    t0 = time.perf_counter_ns()
    pv = ts.ckks_vector_from(server_ctx, p_bytes)
    res = enrolled_vec.dot(pv)
    out_b = res.serialize()
    t1 = time.perf_counter_ns()
    s_ms = (t1 - t0) / 1e6
    return len(out_b), s_ms

async def handle_client(reader, writer):
    data = await reader.read(4)
    if not data:
        writer.close()
        return
    msg_len = int.from_bytes(data, 'big')
    payload = await reader.readexactly(msg_len)
    
    # Process in thread pool
    loop = asyncio.get_running_loop()
    out_len, s_ms = await loop.run_in_executor(executor, do_dot_product, payload)
    
    resp = json.dumps({"status": 200, "service_time_ms": s_ms, "out_len": out_len}).encode()
    writer.write(len(resp).to_bytes(4, 'big') + resp)
    await writer.drain()
    writer.close()

async def run_server():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 9876)
    print("Server started on port 9876")
    return server

async def client_request(probe_b):
    t0 = time.perf_counter()
    reader, writer = await asyncio.open_connection('127.0.0.1', 9876)
    writer.write(len(probe_b).to_bytes(4, 'big') + probe_b)
    await writer.drain()
    
    data = await reader.read(4)
    resp_len = int.from_bytes(data, 'big')
    resp_bytes = await reader.readexactly(resp_len)
    writer.close()
    await writer.wait_closed()
    t1 = time.perf_counter()
    r_ms = (t1 - t0) * 1000.0
    info = json.loads(resp_bytes.decode())
    return r_ms, info['service_time_ms']

async def main():
    srv = await run_server()
    async with srv:
        print("Testing single client request...")
        r_ms, s_ms = await client_request(probe_bytes)
        print(f"Success! Client R = {r_ms:.2f} ms, Server S = {s_ms:.2f} ms")
        srv.close()
        await srv.wait_closed()
        executor.shutdown(wait=False)

if __name__ == '__main__':
    asyncio.run(main())
