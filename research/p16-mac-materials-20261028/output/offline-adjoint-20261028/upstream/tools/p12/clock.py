"""Two clocks: zero native deltas are real plateaus, never division sentinels."""
import numpy as np


def clock_edges(native, sample, wall):
    native=np.asarray(native,dtype=np.int64);sample=np.asarray(sample,dtype=np.int64)
    wall=np.asarray(wall,dtype=np.int64)
    if not (len(native)==len(sample)==len(wall)):raise ValueError('clock shape')
    dn=np.diff(native);ds=np.diff(sample);dw=np.diff(wall)
    positive=dn>0
    ratio=dw[positive]/dn[positive]/1000
    exceptions=[]
    for k in np.flatnonzero((dn!=ds)|(dn<=0)):
        exceptions.append({'from_row':int(k),'to_row':int(k+1),'native_us':native[k:k+2].tolist(),
            'sample_us':sample[k:k+2].tolist(),'host_ns':wall[k:k+2].tolist(),
            'native_delta_us':int(dn[k]),'sample_delta_us':int(ds[k]),'host_delta_ns':int(dw[k]),
            'wall_native_ratio':float(dw[k]/dn[k]/1000) if dn[k]>0 else None,
            'kind':'PLATEAU' if dn[k]==0 else 'REGRESSION' if dn[k]<0 else 'JUMP_OR_CATCHUP'})
    return {'edges':len(dn),'plateaus':int(np.sum(dn==0)),'regressions':int(np.sum(dn<0)),
        'nonmonotone_host':int(np.sum(dw<=0)),
        'native_sample_offset_min_us':int(np.min(native-sample)) if len(native) else None,
        'native_sample_offset_max_us':int(np.max(native-sample)) if len(native) else None,
        'positive_native_wall_ratio_range':[float(ratio.min()),float(ratio.max())] if len(ratio) else None,
        'exceptions':exceptions,'plateau_ratio':'UNDEFINED; retained as null with finite sample/host deltas',
        'guard':'native now-last_valid_read >200000; commits use executor call index/sample, not host time'}
