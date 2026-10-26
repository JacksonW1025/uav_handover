"""One-time precise repair of pre-SITL P12b insertion collision; no history touched."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'uav_lab/.local/checkouts/px4-raptor';out=R/'data/p12b-20261026-preparation/generated-anchor-repair.json'
if out.exists():raise FileExistsError(out)
files={};h=P/'src/modules/mc_raptor/mc_raptor.hpp';s=h.read_text();old=s
blocks=['''#ifdef __PX4_POSIX
    bool _p12_enabled{false}, _p12_seen{false}, _p12_repair{false};
    research_p12_s _p12{};
    uORB::Publication<research_p12_s> _p12_pub{ORB_ID(research_p12)};
#endif
''','''#ifdef __PX4_POSIX
    bool _p12b_enabled{false};
    research_p12b_s _p12b{};
    uORB::Publication<research_p12b_s> _p12b_pub{ORB_ID(research_p12b)};
#endif
''']
counts=[s.count(x) for x in blocks]
assert counts[0]>=1 and counts[1]>=1,counts
for b in blocks:s=s.replace(b,'')
anchor='\tvoid Run() override;';assert s.count(anchor)==1;s=s.replace(anchor,blocks[0]+anchor+'\n'+blocks[1].rstrip())
h.write_text(s);files[str(h.relative_to(P))]={'before':hashlib.sha256(old.encode()).hexdigest(),'after':hashlib.sha256(s.encode()).hexdigest(),'old_block_counts':counts}
p=P/'msg/CMakeLists.txt';s=p.read_text();old=s
for name in ['ResearchP12.msg','ResearchP12b.msg']:s='\n'.join(line for line in s.split('\n') if line.strip()!=name)
s=s.replace('\tVehicleAirData.msg\n','\tResearchP12.msg\n\tVehicleAirData.msg\n\tResearchP12b.msg\n');p.write_text(s);files[str(p.relative_to(P))]={'before':hashlib.sha256(old.encode()).hexdigest(),'after':hashlib.sha256(s.encode()).hexdigest()}
out.write_text(json.dumps({'scope':'generated Lab overlay anchor collision before any P12b SITL; repo overlay corrected; no old raw/freeze edits','files':files,'P12b_SITL_starts':0},indent=2)+'\n')
