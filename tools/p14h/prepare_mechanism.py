"""Seal bounded native-read release diagnostic beforefirstSTART; no launcher."""
import sys,json,copy,hashlib,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *

def main():
 out=register(sys.argv[1],'mechanism A and localresponse around readboundary, F4singleA fixedsame task, 2seeds x2sides',maximum_starts=4)
 cfg=json.load(open(R/'config/p14r/additional/p14r-d06-F4-AB-medium-s270103.json'));cfg['p11']['event_mask']=[0];cfg['p11']['budget']={'mechanism':4,'independent':12,'total':16};cfg['p14r']['role']='P14H diagnostic, no old countuse';cfg['p14h']={'version':'fullP-postEKF+native-read-release-v1','resume_side':'BEFORE','release_rule':'latest actual allowedread; BEFORE targetread minus4ms, AFTER actualtargetread plus.3ms; bounded40ms gapexit gate, observedarrival/read definesachievedbranch','fullP_snapshot':True,'fast_poll_window_s':[-.03,.05],'fast_poll_timeout_s':.00025,'no_control_or_protection_change':True}
 rows=[]
 for j,(seed,side) in enumerate([(142710201,'BEFORE'),(142710202,'AFTER'),(142710201,'AFTER'),(142710202,'BEFORE')]):
  ident=f'p14h-d{j+1:02d}-F4-A-{side.lower()}-s{seed}';c=copy.deepcopy(cfg);c['p14h']['resume_side']=side;p=R/'config/p14h'/f'{ident}.json';write(p,c);rows.append({'id':ident,'seed':seed,'side':side,'config':str(p.relative_to(R)),'config_sha256':sha(p),'kind':'p5_gap','condition':'p11-case','treatment':'P11-Z','source':'P14R d06 F4, Aonly newreleaseprotocol, oldB removed atfixedabsolute plan','budget_class':'mechanism','question':'actualsource readboundary andfusion/cache feedback localresponse withcrossP snapshot; no sameinitialclaim','prestart_prediction':{'branch':'BEFORE aims read atselectedboundary, AFTER aimsnextallowedread8mslater; transportmaymoveBEFOREtolaterbranch, failureofphase is retained','first_action_change':'historical source F4 readjump L2~.026 fromP14G, conditionalnotactualnewinitial guarantee','tilt_height_change_direction':'UNKNOWN untiloffline/sourcepoint comparison; do not invent monotonicrisk','premises':'regularphysical/sample4ms, force_sync2, latesttransport; actual newinitial/cache/OPcovariance retained','source_input':'historical d06 preA, exposed, doesnotreadnewfuture'}})
 write(out/'plan.json',{'rows':rows,'starts_cap':4,'mechanism_not_independent_validation':True,'sequential_review_required':True,'pairing':'seedblocked, no equality ofinitials; actual read/commit branch is mechanismoutcome, no post-hocselectpairs','source_rules':'real read,timeout,capture,resume/commit/consume unchanged; addedrunnerrelease affectsmessage timing only'})
 print('MECHANISM_SEALED',len(rows))
if __name__=='__main__':main()
