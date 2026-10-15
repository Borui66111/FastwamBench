"""Verify Wan-AI backbone component integrity + whether the eval path loads them."""
import json, os, struct, sys

WAN = "/data1/liborui/fastwam_bench/checkpoints/Wan-AI/Wan2.2-TI2V-5B"

print("=== 1. safetensors shard integrity (header parse + byte-length check) ===")
idx = os.path.join(WAN, "diffusion_pytorch_model.safetensors.index.json")
total_declared = 0
if os.path.exists(idx):
    meta = json.load(open(idx))
    wm = meta.get("metadata", {})
    print("index metadata total_size:", wm.get("total_size"))
    shards = sorted(set(meta["weight_map"].values()))
    for s in shards:
        p = os.path.join(WAN, s)
        if not os.path.exists(p):
            print(f"  MISSING {s}")
            continue
        sz = os.path.getsize(p)
        # safetensors: first 8 bytes = header length (little endian uint64)
        with open(p, "rb") as f:
            hdr_len = struct.unpack("<Q", f.read(8))[0]
            hdr = json.loads(f.read(hdr_len))
        # compute declared tensor bytes
        tb = 0
        dtypes = {}
        for k, v in hdr.items():
            if k == "__metadata__":
                continue
            shape = v["shape"]
            dt = v["dtype"]
            dtypes[dt] = dtypes.get(dt, 0) + 1
            n = 1
            for d in shape:
                n *= d
            szmap = {"F32": 4, "F16": 2, "BF16": 2, "I64": 8, "I32": 4, "U8": 1, "BOOL": 1}
            tb += n * szmap.get(dt, 2)
        need = 8 + hdr_len + tb
        ok = "OK " if sz >= need else "TRUNCATED"
        print(f"  {ok} {s}: file={sz} need={need} tensors={len(hdr)-1} dtypes={dtypes}")
        total_declared += tb
    print("total tensor bytes across shards:", total_declared, f"({total_declared/1e9:.2f} GB)")
else:
    print("  index json MISSING")

print()
print("=== 2. .pth component sizes (expect t5 ~11.36GB, vae ~2.82GB) ===")
for f in ["models_t5_umt5-xxl-enc-bf16.pth", "Wan2.2_VAE.pth"]:
    p = os.path.join(WAN, f)
    print(f"  {f}: {'MISSING' if not os.path.exists(p) else os.path.getsize(p)}")

print()
print("=== 3. tokenizer present? ===")
for root, dirs, files in os.walk("/data1/liborui/fastwam_bench/checkpoints/Wan-AI"):
    for f in files:
        if "tokenizer" in f or f.endswith(".json") and "token" in f:
            print("  ", os.path.join(root, f))
