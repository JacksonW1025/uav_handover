"""Meter pure standalone analyses. Do notwrap nested self-meteredcampaigns."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *
if __name__=='__main__':
 tag,cpu,reserve,wall=sys.argv[1:5];assert sys.argv[5]=='--';x=run(sys.argv[6:],B/'tasks'/tag,cpu=int(cpu),reserve_cpu=int(reserve),wall=int(wall),scope='standalone analysis '+tag);print(x);raise SystemExit(0 if x['rc']==0 else 1)
