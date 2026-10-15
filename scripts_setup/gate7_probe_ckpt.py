"""Diff checkpoint MoT keys against the model's expected MoT keys (strict=False silent-drop check)."""
import warnings, torch, collections
warnings.filterwarnings("ignore")

CKPT = "/data1/liborui/fastwam_bench/checkpoints/fastwam_release/libero_optional_idm_2cam224.pt"

payload = torch.load(CKPT, map_location="cpu", weights_only=False)
print("payload top-level keys:", list(payload.keys()))
mot = payload.get("mot")
if mot is not None:
    ks = list(mot.keys())
    print("mot num keys:", len(ks))
    print("mot sample keys:", ks[:8])
    # count params + bytes
    n = sum(v.numel() for v in mot.values() if hasattr(v, "numel"))
    print(f"mot total params: {n/1e9:.3f} B")
    pref = collections.Counter(k.split(".")[0] for k in ks)
    print("mot top-level prefixes:", dict(pref))
if "proprio_encoder" in payload:
    print("proprio_encoder present:", sum(v.numel() for v in payload['proprio_encoder'].values())/1e6, "M params")
