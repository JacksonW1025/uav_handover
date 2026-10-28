"""Load only mathematical functions/classes from archived source using AST.
No original command-line entrypoints, imports, campaign code or remote code run.
"""
import ast,numpy as np
from core import ROOT
S=ROOT/'upstream/tools'
E={'np':np,'DT':.004,'G':9.80665,'REMAP':[0,2,3,1]}
def add(path,names):
 tree=ast.parse((S/path).read_text())
 selected=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in names]
 assert {x.name for x in selected}==set(names),(path,names)
 exec(compile(ast.Module(body=selected,type_ignores=[]),str(S/path),'exec'),E)
add('p3_memory.py',['rotation','gru_step'])
add('p11/observe.py',['multiply','inputs','network'])
add('p11/state.py',['f32','yaw_of','Target'])
add('p11/models.py',['R','qstep','tilt','speeds','motor_step','features','plant','reference','assert_input'])
add('p12/execution.py',['step']);E['motor_step']=E['step']
add('p12/state.py',['EventTarget','Controller'])
add('p12/models.py',['forecast']);M3=E['forecast']
E['mass']=2.0643076923076924
E['pos']=np.array([[.174,.174,-.06],[-.174,-.174,-.06],[.174,-.174,-.06],[-.174,.174,-.06]])-np.array([0,0,-.00186913101803548])
add('p13/models.py',['forecast']);M5=E['forecast']
