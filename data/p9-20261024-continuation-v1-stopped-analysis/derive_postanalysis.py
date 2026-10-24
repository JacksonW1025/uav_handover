"""Create an explicit stopped-epoch display version; never edit frozen sources."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[2]
src=root/'data/p9-20261024-continuation-v1-preparation/postanalysis_continuation.py'
dst=Path(__file__).resolve().parent/'postanalysis_stopped.py'
s=src.read_text()
replacements=[
("if formal['status']!='COMPLETE_WITH_ORIGINAL_INFRA_MISSING' or report['execution_status']!='COMPLETE_WITH_ORIGINAL_INFRA_MISSING':", "if formal['status']!='CONTINUATION_INCOMPLETE' or report['execution_status']!='CONTINUATION_INCOMPLETE':"),
("raise SystemExit('Continuation complete with original missing102 required')", "raise SystemExit('Stopped continuation required; no completion claim')"),
("report['attempts']!={'development':10,'formal':173}", "report['attempts']!={'development':10,'formal':162}"),
("'ORIGINAL_INFRA_MISSING' if r['id']=='C-CZ15-g0.1-reference-P9-Z' and started else", "'ORIGINAL_INFRA_MISSING' if r['id']=='C-CZ15-g0.1-reference-P9-Z' and started else ('FROZEN_ANALYSIS_EXCEPTION_AFTER_FLIGHT_FAILURE' if r['id']=='D-07-P9-Z' and started else"),
("('STARTED_UNRESOLVED' if started else 'NOT_STARTED_FROZEN_SEARCH_STOP'))", "('STARTED_UNRESOLVED' if started else 'NOT_STARTED_FROZEN_SEARCH_STOP')))"),
("if r['stage']!='C-search':budget_errors.append('required static run missing: '+r['id']);state='MISSING_REQUIRED_START'", "if r['stage']!='C-search':state='NOT_RUN_AFTER_MEASUREMENT_EXCEPTION'"),
("r['id']!='C-CZ15-g0.1-reference-P9-Z':budget_errors", "r['id'] not in ['C-CZ15-g0.1-reference-P9-Z','D-07-P9-Z']:budget_errors"),
("'ACCOUNTING_CLOSED_WITH_KNOWN_INFRA_MISSING'", "'ACCOUNTING_ENUMERATED_INCOMPLETE_NO_ACCEPTANCE'"),
("'reference_missing_n':1", "'reference_missing_n':1,'new_frozen_measurement_exception_id':'D-07-P9-Z','D_not_run':11"),
("续接71条原始数据审计", "续接59条完成记录原始数据重测（全批完整性FAIL）"),
("nine paired sequence clusters", "six completed paired sequence clusters; three planned clusters incomplete"),
("九个配对序列簇", "六个已完成配对序列簇（原计划九簇）"),
("'D has nine related sequence clusters, not 36 independent samples'", "'D planned nine clusters; only six four-arm clusters measured, one extra original arm aborted before closed gap and 11 arms not run'"),
]
for old,new in replacements:
    if old not in s:raise RuntimeError('derivation anchor absent: '+old)
    s=s.replace(old,new)
s=s.replace('Kept outside tools/ while the candidate is running to preserve its identity.','Explicit post-flight stopped-analysis version; no new simulation or fit.')
compile(s,str(dst),'exec');dst.write_text(s)
(Path(__file__).resolve().parent/'derivation.json').write_text(json.dumps({'source':str(src.relative_to(root)),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'derived':str(dst.relative_to(root)),'derived_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'changes':replacements,'scope':'display and enumerate partial evidence only; no acceptance or frozen input changes'},indent=2)+'\n')
print(dst)
