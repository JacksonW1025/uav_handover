"""P8-B：在 Thor 上由 p8_space.py + p8_list_index.json 重建三种离线方法的用例清单，写出 p8_lists.json。
候选池和项目那边冻结时完全相同（同一个随机数种子、同一个 p8_space.sample），清单只是池子里的下标。不含任何模型预测。
用法：cd tools/p8 && python3 p8_build_lists.py  → 打印全部用例名的 sha256（必须和提示词里给的一致）和 p8_lists.json 的 sha256。"""
import os, sys, json, hashlib, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import p8_space as S
NPOOL = 2000

def pool_of(sut, seed):
    r = np.random.default_rng(1000 * seed + (7 if sut == "T1" else 3)); out = []
    while len(out) < NPOOL:
        c = S.sample(r, sut)
        if S.fits(c): out.append(c)
    return out

if __name__ == "__main__":
    idx = json.load(open(os.path.join(HERE, "p8_list_index.json"))); lists = {}
    for sut in S.SUTS:
        for seed in range(3):
            pool = pool_of(sut, seed)
            for m in ("random", "contest", "ours"):
                lists[f"{m}/{sut}/{seed}"] = [{"name": S.name(c, sut), "case": c, "windows_s": S.windows(c), "pre_gap_s": S.budget(c)[0],
                                               "post_gap_s": S.budget(c)[1], "cell": list(S.cell(c))} for c in (pool[i] for i in idx[f"{m}/{sut}/{seed}"])]
    p = os.path.join(HERE, "p8_lists.json")
    with open(p, "w") as f: json.dump({"lists": lists}, f, indent=1, ensure_ascii=False); f.write("\n")
    names = "\n".join(e["name"] for k in sorted(lists) for e in lists[k])
    print("names", hashlib.sha256(names.encode()).hexdigest())
    print("p8_lists.json", hashlib.sha256(open(p, "rb").read()).hexdigest())
