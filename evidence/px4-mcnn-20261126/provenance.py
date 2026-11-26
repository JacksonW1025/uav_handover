import hashlib,json,subprocess,sys
from pathlib import Path
root,lab,px4=map(Path,sys.argv[1:4]);p=root/'evidence/px4-mcnn-20261126'
def h(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rec(path):return dict(path=str(path),sha256=h(path))
binary=px4/'build/px4_sitl_default/bin/px4'
stock=lab/'stock-bin/px4'
model=px4/'src/modules/mc_nn_control/control_net.cpp'
mapping=px4/'src/modules/mc_nn_control/actions_rescale.hpp'
runs=json.loads((p/'runs.json').read_text())
attempt=[]
for series in sorted(lab.glob('pair-*')):
    if not series.is_dir():continue
    info=series/'baseline.json'
    lablog=Path(str(series)+'.log')
    d=json.loads(info.read_text()) if info.exists() else {}
    reason=None
    if not d.get('ulog_sha256'):
        reason=d.get('error') or 'runner prerequisites did not yield completed evidence'
    elif not any(r['ulog']==d['ulog'] for r in runs.values()):
        reason={'t1_c':'exploratory; early yaw reference differed from normalized pairing','t1_n':'exploratory; paired rerun with matched yaw','t2_c':'exploratory; initial OFFBOARD yaw target was zero','t2_n':'exploratory; initial OFFBOARD yaw target was zero','t4_release':'timing design pilot; paired rerun','t4_hold':'pilot window expired before MCNN activation; reran actual hold'}.get(d.get('case'),'exploratory case')
    attempt.append(dict(name=series.name, reason_not_in_primary=reason,
                        runner_log=rec(lablog) if lablog.exists() else None, result=rec(info) if info.exists() else None,
                        ulog=dict(path=d['ulog'],sha256=d['ulog_sha256']) if d.get('ulog_sha256') else None))
(p/'attempts.json').write_text(json.dumps(attempt,indent=2,sort_keys=True)+'\n')
records={}
for k,r in runs.items():
    d=lab/f"pair-{k}-{r['run_tag']}"
    files=[d/'baseline.json',d/'commands.jsonl',d/'relay.csv',d/'reference.jsonl', *sorted((d/'motor').glob('motor-*.bin'))]
    if (d/'native.csv').is_file():files.append(d/'native.csv')
    records[k]=dict(ulog=rec(Path(r['ulog'])), other_raw_files=[rec(f) for f in files])
assert all(records[k]['ulog']['sha256']==v['ulog_sha256'] and v['binary_sha256']==h(binary) for k,v in runs.items())
hover=json.loads((lab/'coil-105/baseline.json').read_text())
d=dict(
    publication_base=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
    px4_commit=subprocess.check_output(['git','-C',str(px4),'rev-parse','HEAD'],text=True).strip(),
    gazebo_models_commit=subprocess.check_output(['git','-C',str(px4/'Tools/simulation/gz'),'rev-parse','HEAD'],text=True).strip(),
    gazebo_version="8.11.0", simulator="PX4_SITL Gazebo x500, default world, seed 20261126",
    build_flags=["CONFIG_MODULES_MC_NN_CONTROL=y","CONFIG_LIB_TFLM=y"],
    model_bytes=json.loads((lab/'linked-model.json').read_text()),
    model_source=rec(model), official_action_mapping_source=rec(mapping),
    stock_binary=rec(stock), paired_run_binary=rec(binary),
    observer_plugin=rec(lab/'libResearchMulticopterMotorModel.so'),
    simulator_relay=rec(lab/'sim-motor-relay'),
    stock_build_log=rec(lab.parent/'build-official-pinned-idlc.log'),
    instrument_build_log=rec(lab/'qualification-instrument-build.log'),
    frozen_params=dict(MC_NN_THRST_COEF=1.05,MC_NN_MIN_RPM=1000,MC_NN_MAX_RPM=22000,MC_NN_MANL_CTRL=0,THR_MDL_FAC=0),
    qualification_hover=dict(ulog=rec(Path(hover['ulog'])),results=rec(lab/'coil-105/baseline.json'),
        native_active_us=hover['neural_native_start_us'],binary_sha256=hover['binary_sha256']),
    raw_records=records)
assert d['qualification_hover']['binary_sha256']==d['stock_binary']['sha256']
(p/'provenance.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
