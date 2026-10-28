"""Read-only integrity, import, identification and forecast checks; no SITL."""
from pathlib import Path
import argparse, copy, hashlib, importlib.metadata, json, sys, time

ROOT = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--integrity-only', action='store_true')
    ap.add_argument('--output', type=Path, help='New receipt file, outside frozen input files')
    args = ap.parse_args()
    start = time.perf_counter()
    manifest = json.loads((ROOT/'MANIFEST.json').read_text())
    for r in manifest['files']:
        p = ROOT/r['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Missing/changed material: '+r['path'])
    checks = dict(material_files_verified=len(manifest['files']), new_SITL=0)
    if not args.integrity_only:
        import numpy as np
        sys.path.insert(0, str(ROOT/'output/greybox-baseline-audit-20261028'))
        import core
        from fit_baselines import datasets, fit_ee
        from h2_strict_compare import load
        params=json.loads((core.ROOT/'models.json').read_text())
        ds, training, original = datasets()
        fitted = fit_ee(ds)
        delta = float(np.max(np.abs(core.vec(fitted)-core.vec(params['equation_error']))))
        assert delta < 1e-6, ('identification mismatch', delta)
        assert np.max(np.abs(core.vec(original)-core.vec(params['equation_error']))) < 1e-8
        rows=json.loads((ROOT/'output/offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
        results=json.loads((core.ROOT/'results.json').read_text())['results']
        expected=next(r for r in results if r['name']=='ordinary_EE' and r['scope']=='normal_template')['per_case']['rows']
        probes=[]
        for family in ['F2','F4']:
            r=next(r for r in rows if r['family']==family and r['arm']=='AB-short' and r['block']==1)
            inp=core.sanitize(r)
            inp['initial']=copy.deepcopy(next(q['initial'] for q in rows if q['family']==family and q['branch']=='NORMAL' and q['block']==1))
            pred, trace, _=core.forecast(inp,params['equation_error'])
            target=next(q for q in expected if q['id']==r['id'])
            err=max(abs(pred[k]-target[k]) for k in ['prediction','predicted_tilt'])
            assert err < 1e-5, ('forecast mismatch', family, err)
            poisoned=copy.deepcopy(r)
            poisoned.update(task='POISON',LP_max_loss_m=999.,LP_peak_tilt_deg=-999.,B_before={'unavailable':True})
            clean=core.sanitize(poisoned);clean['initial']=copy.deepcopy(inp['initial'])
            _, other, _=core.forecast(clean,params['equation_error'])
            assert np.array_equal(trace,other)
            probes.append(dict(id=r['id'],max_error=err,peak_loss=pred['prediction'],peak_tilt=pred['predicted_tilt']))
        # Import the complete comparative feature-loader to check transitive dependencies.
        loaded=load()
        assert len(loaded)==84
        sys.path.insert(0,str(ROOT/'output/sequential-budget-audit-20261028'))
        import sequential as seq
        metrics, order, predictions=seq.run('greybox_gp','map_variance',seq.FOLDS[0],0,seq.kernel())
        examples=json.loads((seq.ROOT/'sequential_examples.json').read_text())
        example=next(r for r in examples if r['learner']=='greybox_gp' and r['policy']=='map_variance' and r['heldout']==[seq.GROUPS[j]['id'] for j in seq.FOLDS[0]])
        assert order==example['sequence']
        assert np.max(np.abs(predictions-np.asarray(example['predictions']))) < 1e-6
        checks.update(training_trajectories=len(training),training_hashes_verified=True,
                      identification_parameter_max_delta=delta,forecast_probes=probes,
                      future_label_mutation_invariant=True,comparison_rows=len(loaded),
                      sequential_queries_reproduced=len(order),
                      python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','scikit-learn','pyulog']})
    checks['elapsed_seconds']=time.perf_counter()-start
    checks['status']='PASS'
    text=json.dumps(checks,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as f:f.write(text)
    print(text)

if __name__=='__main__':main()
