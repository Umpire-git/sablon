"""Rastgele bozulmuş tasarımlarla motorun sağlamlığı (elle çalıştırılır): python tests/fuzz_tasarim.py [tohum] [adet]"""
import json, random, copy, traceback, glob, collections, signal, sys, time
import os; ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from sablon.design import from_dict
from sablon.ai import evaluate
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
ex = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(ROOT, "ornekler", "*.json")))]
crash = collections.Counter(); samples = {}; slow = []
class TO(Exception): pass
def h(*a): raise TO()
signal.signal(signal.SIGALRM, h)
def mutate(d):
    d = copy.deepcopy(d); pans = d["parcalar"][0]["paneller"]
    k = rng.randrange(12); p = rng.choice(pans)
    if k == 0: p["aci"] = str(rng.choice([-180, -90, 45, 135, 180, 270]))
    elif k == 1: p["genislik"] = rng.choice(["0", "-5", "1e6", "W*3", "x+1", "", ")"])
    elif k == 2: p["ebeveyn"] = rng.choice(["yok", p["id"], pans[0]["id"]]); p["kenar"] = rng.choice(["alt", "ust", "sol", "sag", ""])
    elif k == 3: p["ofset"] = str(rng.uniform(-200, 200))
    elif k == 4 and len(pans) > 1: pans.remove(p)
    elif k == 5: p["profil_ust"] = {"tip": rng.choice(["kavis", "sivri", "oyuk", "yuvarlak"]), "olcu": str(rng.uniform(-20, 80))}
    elif k == 6: p["koseler"] = {"sol_alt": "50", "sag_alt": "50", "sag_ust": "100", "sol_ust": "0"}
    elif k == 7: p["daralma"] = str(rng.uniform(0, 60))
    elif k == 8 and d["ozellikler"]: d["ozellikler"][0]["panel"] = rng.choice([q["id"] for q in pans]); d["ozellikler"][0]["x"] = str(rng.uniform(-50, 150))
    elif k == 9: d["icerikler"] = [{"tip": "kart", "adet": rng.randint(0, 30), "panel": rng.choice([q["id"] for q in pans])}]
    elif k == 10: p["yariktan_gecer"] = True
    elif k == 11: d["degiskenler"].append({"ad": "zz", "deger": "1/0", "aciklama": ""})
    return d
N = int(sys.argv[2]) if len(sys.argv) > 2 else 120
ok = 0
for i in range(N):
    d = rng.choice(ex)
    for _ in range(rng.randint(1, 3)): d = mutate(d)
    t0 = time.time(); signal.alarm(20)
    try:
        evaluate(from_dict(d)); ok += 1
    except TO:
        slow.append(json.dumps(d)[:0]); crash["ZAMAN AŞIMI >20s"] += 1
        samples.setdefault("ZAMAN AŞIMI >20s", [json.dumps([p.get("id")+":"+p.get("genislik","")+"/"+p.get("yukseklik","")+"/"+p.get("aci","") for p in d["parcalar"][0]["paneller"]])[:300]])
    except Exception as e:
        key = type(e).__name__ + ": " + str(e)[:80]
        crash[key] += 1; samples.setdefault(key, traceback.format_exc().splitlines()[-4:])
    finally:
        signal.alarm(0)
print("ok", ok, "sorun", sum(crash.values()))
for k, v in crash.most_common(10):
    print(v, k); print("   ", samples[k])
