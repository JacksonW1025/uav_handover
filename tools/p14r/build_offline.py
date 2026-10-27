"""Build actual source OutputPredictor diagnostic/API; no flight or Lab edit."""
import sys,json,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);px=R/'uav_lab/.local/checkouts/px4-raptor';inc=['src/lib','src/lib/matrix','src','platforms/common/include','platforms/posix/include','platforms/posix/src/px4/common/include','build/px4_sitl_raptor','src/modules/ekf2/EKF/output_predictor'];common=['g++','-std=c++17','-O2','-fno-signed-zeros','-freciprocal-math','-fno-trapping-math']+['-I'+str(px/p) for p in inc]+['-I'+str(R/'research/state')];sources=[px/'src/modules/ekf2/EKF/output_predictor/output_predictor.cpp',px/'src/lib/lat_lon_alt/lat_lon_alt.cpp',px/'src/lib/geo/geo.cpp'];records=[]
 for name,src,extra in [('replay.bin','source_replay.cpp',[]),('libop.bin','op_api.cpp',['-shared','-fPIC'])]:
  cmd=common+extra+[str(R/'tools/p14r'/src),*map(str,sources),'-o',str(out/name)];st=time.perf_counter()
  with (out/(name+'.log')).open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
  records.append({'command':cmd,'rc':rc,'elapsed_s':time.perf_counter()-st});assert rc==0
 write(out/'manifest.json',{'source_hashes':{str(p.relative_to(R)):sha(p) for p in sources+[R/'tools/p14r/source_replay.cpp',R/'tools/p14r/op_api.cpp']},'binaries':{n:sha(out/n) for n in ['replay.bin','libop.bin']},'commands':records,'scope':'actual OutputPredictor/LatLonAlt/MapProjection, POSIX logging guards excluded, no new simulator','future_data':'none in compiled algorithm'})
if __name__=='__main__':main()
