#!/usr/bin/env python3
"""Independent A3 source replay, exact prefix refusal and data-counterexample check.

Does not import generate/compatibility or their adapter. Reuses the unchanged
A2 exact P checker only as a matrix lemma. Source reference is never handcopied.
"""
import argparse
from fractions import Fraction as F
import gzip
import importlib.util
import json
from pathlib import Path

from source import ROOT, Oracle, runner, snapshot, sha, startup_observation

H=F(1,250);SCALE=10**12;EP=F(1,2**21)+F(1,10**12)
LP,LV=F(13,1000),F(29,1000)


def ff(x):return F.from_float(float(x))


def matrix_check(lemma,raw,kp,kv):
    from math import factorial
    p=[[F(x,10**10) for x in row] for row in raw];n=47
    lower=[r[:] for r in p]
    for i in range(n):lower[i][i]-=F(1,2)
    lemma.pd(lower);assert max(sum(map(abs,r)) for r in p)<30000
    for i,c in enumerate([F(15,100000),F(8,10000),F(2,5)]):
        b=[r[:] for r in p];b[i][i]-=1/c;lemma.pd(b)
    assert p[3][3]<F(11,2)**2 and p[4][4]<25
    rho=[sum((-F(1,20))**j/factorial(j) for j in range(k)) for k in [20,21]]
    margins=[]
    for rr in rho:
        a=lemma.a_matrix(kp,kv,rr)
        cols=[[(i,a[i][j]) for i in range(n) if a[i][j]] for j in range(n)]
        q=[[p[i][j]-sum(u*p[k][l]*v for k,u in cols[i] for l,v in cols[j]) for j in range(n)] for i in range(n)]
        margin=min(q[i][i]-F(1,2)-sum(abs(q[i][j]) for j in range(n) if j!=i) for i in range(n))
        assert margin>0;margins.append(str(margin))
    return rho,{'P_bounds':'.5 I<P<30000 I','difference_lower':'1/2 I','exact_Q_margins':margins,
         'output_square_constants':['3/20000','1/1250','2/5'],'target_column_norm_upper':['11/2','5'],
         'new_lateral_candidate_not_scaled_old_P':True}


def portable_data_check(data):
    from math import factorial
    rho=[sum((-F(1,20))**j/factorial(j) for j in range(n)) for n in [20,21]]
    checked=[]
    for row in data['portable_counterexamples']:
        qs=[]
        c,s=ff(row['cos_yaw']),ff(row['sin_yaw'])
        for vals in row['quaternion']:
            w,x,y,z=map(ff,vals)
            qs.append(-F('9.80665')*(c*2*(x*z+w*y)+s*2*(y*z-w*x))/(1-2*(x*x+y*y)))
        command=-ff(row['kp'])*ff(row['delayed_clipped_position'])-ff(row['kv'])*ff(row['delayed_clipped_velocity'])
        residual=[qs[1]-r*qs[0]-(1-r)*command for r in rho]
        lower=min(abs(x) for x in residual) if residual[0]*residual[1]>0 else F(0)
        # cos/sin binary64 coefficients define the stored diagnostic mapping;
        # rational quaternion algebra is recomputed independently here.
        assert abs(qs[0]-ff(row['q'][0]))<F(1,10**12)
        assert abs(qs[1]-ff(row['q'][1]))<F(1,10**12)
        assert lower>F(633,10**10)  # .633*1e-7, a necessary coordinate bound
        checked.append({'sample_us':row['sample_us'],'profile_bound_offset_us':row['profile_bound_offset_us'],
                        'exact_abs_residual_lower':str(lower),'necessary_q_bound':'633/10000000000',
                        'margin_lower':str(lower-F(633,10**10))})
    return checked


def verify(directory, compatibility):
    directory=directory.resolve();compatibility=compatibility.resolve()
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(directory/name)!=digest:raise ValueError('INPUT_HASH_MISMATCH: '+name)
    ledger=json.loads((directory/'source-ledger.json').read_text())
    assert not ledger['oracle_adapter_mismatches'], 'SOURCE_ORACLE_ADAPTER_MISMATCH'
    snap=json.loads((directory/'source-snapshot.json').read_text())
    assert snap==snapshot(), 'SOURCE_SNAPSHOT_NOT_CURRENT_OR_INCOMPLETE'
    assert 'previous_trajectory_setpoint_stale = false;' in snap['guard']
    startup=json.loads((directory/'startup-observation.json').read_text()) if (directory/'startup-observation.json').exists() else None
    if startup:assert startup==startup_observation(), 'ACTUAL_STARTUP_MAPPING_MISMATCH'
    axis=1 if startup else 0
    r,clock=runner(startup);oracle=Oracle(snap,startup)
    pre=json.loads((directory/'prestream.json').read_text())
    for label in ['activation','before_start_stream']:
        assert oracle.tick(pre[label]['input'])==pre[label]['output']
    spec=importlib.util.spec_from_file_location('retained_exact_matrix_lemma',ROOT/'tools/p10r2/verify.py')
    lemma=importlib.util.module_from_spec(spec);spec.loader.exec_module(lemma)
    old=json.loads((ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json').read_text())
    model=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text())
    # P is selected only after the source flow/startup is fixed, not vice versa.
    raw=json.loads((directory/'matrix-candidate.json').read_text())['P_integer'] if startup else old['P_integer']
    kp,kv=map(ff,[model['kp'][axis],model['kv'][axis]])
    rho,matrix=matrix_check(lemma,raw,kp,kv)
    radius=F(1,10**9) if startup else F(0)
    cap_error=F(0);cap_g=[F(0),F(0)];history=[[F(0),F(0)] for _ in range(22)]
    failure=None;prefixes=0;last_read=0;old_stale=True;equal=[];events=[]
    previous=None;max_round=F(0);max_e=F(0);max_d=F(0)
    nominal_previous=None;nominal_errors=[];max_nominal_residual=F(0);max_pose_q_mismatch=F(0);initial_mapping_norm=F(0)
    with gzip.open(directory/'trace.jsonl.gz','rt') as stream:
        for k,line in enumerate(stream):
            row=json.loads(line);us=row['profile_us'];assert us==4000*k
            clock.us=us;before=len(r.trajpub.messages)
            if us<=ledger['stream_stop_profile_us']:r.stream()
            updated=len(r.trajpub.messages)>before
            assert bool(row['input'][2])==updated
            if updated:
                import struct
                b32=lambda x:struct.unpack('!f',struct.pack('!f',x))[0]
                msg=r.trajpub.messages[-1]
                assert row['input'][10:14]==[b32(msg.position[0]),b32(msg.velocity[0]),b32(msg.position[1]),b32(msg.velocity[1])]
                last_read=100000000+us
            if startup:
                import math
                yaw=startup['origin_event']['yaw_rad'];c,s=math.cos(yaw),math.sin(yaw);ox,oy=startup['origin_event']['origin_ned_m'][:2]
                want=[ox+c*row['p'][0]+s*row['p'][1],c*row['v'][0]+s*row['v'][1],oy+s*row['p'][0]-c*row['p'][1],s*row['v'][0]-c*row['v'][1]]
                assert max(abs(x-y) for x,y in zip(row['input'][6:10],want))<1e-12
            else:assert row['input'][6:10]==[row['p'][0],row['v'][0],-row['p'][1],-row['v'][1]]
            actual=oracle.tick(row['input']);assert actual==row['oracle'], 'SOURCE_REPLAY_DISAGREES'
            assert actual[:11]==row['adapter'], 'ADAPTER_DISAGREES'
            stale,cap,_,skip,last,*_=actual[:11]
            assert last==last_read and not skip
            expected_stale=100000000+us-last_read>200000
            assert bool(stale)==expected_stale and row['read_age_us']==100000000+us-last_read
            if row['read_age_us']==200000:
                assert not stale;equal.append(us)
            if cap or old_stale and not stale:events.append((us,'CAPTURE' if cap else 'RESUME'))
            old_stale=bool(stale)
            g=[[F(x,SCALE) for x in line] for line in row['forward_generators']]
            body=[ff(row[name][axis]) for name in ['p','v','q']]
            both=[[ff(row[name][axis]) for name in ['p','v','q']] for axis in range(2)]
            if startup:
                quat=[ff(b32(x)) for x in row['input'][14:18]] if updated else [ff(struct.unpack('!f',struct.pack('!f',x))[0]) for x in row['input'][14:18]]
                w,x,y,z=quat;bx=2*(x*z+w*y);by=2*(y*z-w*x);bz=1-2*(x*x+y*y)
                qgeom=[-F('9.80665')*(ff(c)*bx+ff(s)*by)/bz,-F('9.80665')*(ff(s)*bx-ff(c)*by)/bz]
                max_pose_q_mismatch=max(max_pose_q_mismatch,*(abs(qgeom[i]-both[i][2]) for i in range(2)))
            if nominal_previous is not None:
                kk=k-1;delayed=max(0,kk-22)
                for axis in range(2):
                    pa,va,qa=nominal_previous[axis]
                    kpa,kva=ff(model['kp'][axis]),ff(model['kv'][axis])
                    de,dd=nominal_errors[delayed][axis]
                    for rr in rho:
                        qn=rr*qa-(1-rr)*(kpa*de+kva*dd)
                        vn=va+H/2*(qa+qn);pn=pa+H/2*(va+vn)
                        residual=max(abs(a-b) for a,b in zip(both[axis],[pn,vn,qn]))
                        assert residual<F(1,10**10),'NONLINEAR_NOMINAL_UPDATE_MISMATCH'
                        max_nominal_residual=max(max_nominal_residual,residual)
            errors=[]
            for axis in range(2):
                ee=both[axis][0]-ff(row['target_flu'][axis]);dd=both[axis][1]-ff(row['target_flu'][2+axis])
                errors.append((max(-F(1,2),min(F(1,2),ee)),max(F(-1),min(F(1),dd))))
            nominal_errors.append(errors);nominal_previous=both
            if k==0:
                expected=[[F(0),F(0)] for _ in range(47)]
                expected[0][0]=F(1,100);expected[2][1]=F(1,10)
                for i in range(3,47,2):expected[i][0]=F(1,100)
                assert g==expected
                if startup:
                    assert body==[ff(startup[n][axis]) for n in ['relative_position_flu','velocity_flu','q_flu']]
                    history=[list(map(ff,row['forward_error'])) for _ in range(22)]
                    err=[body[0]-ff(row['target_flu'][axis]),body[1]-ff(row['target_flu'][2+axis])]
                    rawp=startup['position_ned'];rawv=startup['velocity_ned']
                    mapped_p=ff(s)*(ff(rawp[0])-ff(ox))-ff(c)*(ff(rawp[1])-ff(oy))
                    mapped_v=ff(s)*ff(rawv[0])-ff(c)*ff(rawv[1])
                    initial_mapping_norm=2000*max(*(abs(x-y) for x,y in zip(err,history[0])),abs(mapped_p-body[0]),abs(mapped_v-body[1]),abs(qgeom[axis]-body[2]))
                    assert initial_mapping_norm<radius
                else:
                    assert body==[0,0,0] and row['input'][10:14]==[0.,-0.,0.,-0.]
            # Exact physical/generator difference checks for every certified
            # prefix. Later clipped nominal is retained but no false linear proof.
            if failure is None and previous is not None:
                b0,g0,ce0,cd0,er0,es0,hist0,observed_errors=previous
                maximum=[F(0)]*3
                for rr in rho:
                    for col in range(3):
                        a=b0 if col==0 else [g0[i][col-1] for i in range(3)]
                        he=hist0[-1][0] if col==0 else g0[-2][col-1]
                        hd=hist0[-1][1] if col==0 else g0[-1][col-1]
                        qn=rr*a[2]-(1-rr)*(kp*he+kv*hd)
                        vn=a[1]+H/2*(a[2]+qn);pn=a[0]+H/2*(a[1]+vn)
                        out=body if col==0 else [g[i][col-1] for i in range(3)]
                        maximum[col]=max(abs(x-y) for x,y in zip(out,[pn,vn,qn]))
                        if col:
                            assert g[3][col-1]==ce0[col] and g[4][col-1]==cd0[col]
                            assert g[5:]==g0[3:-2]
                maximum[0]=max(maximum[0],abs(observed_errors[0]-ce0[0]),abs(observed_errors[1]-cd0[0]))
                rounding=2000*sum(maximum)
                assert rounding<=F(1,10**8),'ROUNDING_NOT_COVERED'
                max_round=max(max_round,rounding)
                radius=lemma.up(radius+F(11,2)*er0+5*es0+F(1,10**8)+F(1,10**7))
                history=[observed_errors]+hist0[:-1]
            if failure is None:
                if cap:
                    cap_g=g[0][:];cap_error=LP*radius+2*EP
                target_g=cap_g if stale else [F(0),F(0)]
                er=cap_error if stale else F(0);es=F(0)
                targetp,targetv=ff(row['target_flu'][axis]),ff(row['target_flu'][2+axis])
                ge=[g[0][j]-target_g[j] for j in range(2)];gd=g[1][:]
                assert row['forward_error_generators']==[[int(x*SCALE) for x in ge],[int(x*SCALE) for x in gd]]
                ce=[body[0]-targetp,*ge];cd=[body[1]-targetv,*gd]
                e_upper=abs(ce[0])+sum(map(abs,ge))+LP*radius+er
                d_upper=abs(cd[0])+sum(map(abs,gd))+LV*radius
                d_lower=abs(cd[0])-sum(map(abs,gd))-LV*radius
                if e_upper>=F(1,2) or d_upper>=1:
                    failure={'profile_us':us,'relative_first_gap_s':us/1e6-ledger['first_gap_profile_s'],
                        'cause':'UNSATURATED_CERTIFICATE_NOT_APPLICABLE_AT_SOURCE_CAPTURE' if cap else 'PREFIX_TUBE_CANNOT_CLOSE',
                        'actual_source_capture':bool(cap),'axis_velocity_error_lower':str(d_lower),
                        'axis_velocity_error_upper':str(d_upper),'entire_initial_set_exceeds_velocity_clip':d_lower>1,
                        'radius_P':str(radius),'position_upper':str(e_upper),
                        'scope':'failure of linear unsaturated certificate, not a proof of tilt failure'}
                    if startup:
                        # Any orthonormal yaw frame with both |dv_i|<=1 has norm<=sqrt2.
                        # The fixed logged-frame lateral component alone exceeds sqrt2,
                        # so capture yaw rounding cannot rescue native unclipped domain.
                        norm2=ff(c)**2+ff(s)**2
                        assert d_lower*d_lower>2*norm2
                        failure['yaw_independent_geometric_clip_exclusion']=True
                        failure['proof']='||v_xy|| >= |v_l_fixed|/sqrt(c^2+s^2) > sqrt(2); at T0 target velocity=0, at least one native clip axis exceeds 1 for every capture yaw'
                        failure['position_upper']=None
                        failure['position_reset_scope']='not needed for refusal; no post-reset position enclosure claimed'
                else:
                    max_e=max(max_e,e_upper);max_d=max(max_d,d_upper)
                    prefixes+=1;previous=(body,g,ce,cd,er,es,[pair[:] for pair in history],list(map(ff,row['forward_error'])))
        rows=k+1
    oracle.close()
    assert failure is not None and failure['entire_initial_set_exceeds_velocity_clip']
    assert events==[(e['profile_us'],e['kind']) for e in ledger['events']]
    assert rows==ledger['rows'] and equal
    empirical=json.loads(compatibility.read_text());data_checks=portable_data_check(empirical)
    return {'schema':'p10-a3-independent-audit-1','gate':'NOT_PASSED',
        'source_interface':'all recorded 7350 nominal-body source events/reads/held references replayed; interval body resets checked through first certificate failure',
        'source_replayed_rows':rows,'events':events,'strict_equality_fresh_profile_us':equal,
        'proxy_initialization':'empty/earliest-sample startup lift verified; no fictitious prior history',
        'nonzero_initial_set':'actual observed startup center + two lateral generators (.01m position,.1m/s2 q); shared earliest e/d samples' if startup else 'legacy yaw0 candidate',
        'certified_axis':axis,'actual_startup_bound':startup['state_sample_us'] if startup else None,
        'axis_unsaturated_prefixes_verified':prefixes,'first_certificate_failure':failure,
        'matrix_lemma':matrix,'max_difference_rounding_P_upper':str(max_round),
        'full_clipped_nominal_max_coordinate_residual':str(max_nominal_residual),
        'initial_mapping_P_norm_upper':str(initial_mapping_norm),
        'nominal_source_quaternion_q_lift_max_mismatch':str(max_pose_q_mismatch),
        'pose_lift_scope':'nominal computed mapping check only; not a strict set or actual-controller model-error bound and not substituted for the refuted A2 w condition',
        'max_prefix_position_upper':str(max_e),'max_prefix_velocity_upper':str(max_d),
        'full_sequence_set_certificate':'UNKNOWN_AFTER_SATURATION; no unsaturated A applied thereafter',
        'actual_error_interface':'REFUTED_FOR_SPECIFIED_MAPPED_P9_DEVELOPMENT_DATA; not a new hard error bound',
        'portable_exact_data_counterexamples':data_checks,
        'actual_clock_interface':'4ms logged samples observed; exact A3 callback/read schedule remains conditional, not verified by a profile bound',
        'test_or_repair_admission':'REJECT_THIS_UNSATURATED_CERTIFICATE_AND_THE_REFUTED_A2_DATA_INTERFACE',
        'height_and_actual_intersample_output':'NOT_CERTIFIED; independent scope, not sole gate reason',
        'input_sha256':{name:sha(path) for name,path in {
            'source/manifest.json':directory/'manifest.json','source/trace.jsonl.gz':directory/'trace.jsonl.gz',
            'source/source-ledger.json':directory/'source-ledger.json','compatibility.json':compatibility,
            'retained_PD_and_A_primitives':ROOT/'tools/p10r2/verify.py',
            'original_A2_certificate_provenance':ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json'}.items()},
        'verifier_sha256':sha(Path(__file__)),'new_SITL_starts':0,'new_development_flights':0,'new_formal_flights':0,'new_real_flights':0,'B_C_D_started':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--compatibility',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    result=verify(a.input,a.compatibility)
    with (a.output/'audit.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['gate','source_replayed_rows','axis_unsaturated_prefixes_verified','first_certificate_failure']}))
