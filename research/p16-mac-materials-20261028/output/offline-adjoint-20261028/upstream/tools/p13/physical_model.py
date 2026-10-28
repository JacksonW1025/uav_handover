"""P13 conditional source rigid-body/rotor kernel, no log access or fit.
Full source kernel is separately tested; M5 uses its source constants and vertical force.
"""
import json,sys,xml.etree.ElementTree as X
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2]
from p11.models import plant as M4plant,R as matrix,qstep,tilt
S=np.array([[0.,1.,0.],[1.,0.,0.],[0.,0.,-1.]])
B=np.diag([1.,-1.,-1.]);mass=2.0643076923076924
pos=np.array([[.174,.174,-.06],[-.174,-.174,-.06],[.174,-.174,-.06],[-.174,.174,-.06]])-np.array([0,0,-.00186913101803548]);turn=np.array([1,1,-1,-1]);Ir=2.649858234714004e-5
I=np.diag([.02166666666666667,.02166666666666667,.04])
for p in pos:I+=.016076923076923075*(np.dot(p,p)*np.eye(3)-np.outer(p,p))+np.diag([(3.8464910483993325e-7+2.6115851691700804e-5)/2]*2+[Ir])
I+=2.*(.00186913101803548**2)*np.diag([1,1,0])

def source_step(p,v,q,w,rotor,next_rotor,dt=.004,phase=None):
 M=matrix(q);axis=M[:,2];link_v=v+np.cross(w,pos)@M.T
 drag=-abs(rotor)[:,None]*8.06428e-5*(link_v-np.outer(link_v@axis,axis))
 T=8.54858e-6*rotor**2;forces=-T[:,None]*axis+drag;force=forces.sum(axis=0)
 torques=np.cross(pos,forces@M).sum(axis=0);torques[2]+=np.dot(turn,T)*.016
 torques+=(-abs(rotor)[:,None]*1e-6*(link_v-np.outer(link_v@axis,axis))).sum(axis=0)@M
 spin=np.array([0,0,-Ir*np.dot(turn,rotor)/10]);spin_rate=np.array([0,0,-Ir*np.dot(turn,next_rotor-rotor)/(10*dt)])
 localI=I.copy();dI=np.zeros((3,3))
 if phase is not None:
  J=np.diag([3.8464910483993325e-7,2.6115851691700804e-5,Ir]);Javg=np.diag([(J[0,0]+J[1,1])/2]*2+[Ir])
  for i,phi in enumerate(phase):
   c=np.cos(phi);s=np.sin(phi);Q=np.array([[c,-s,0],[s,c,0],[0,0,1]]);Jp=Q@J@Q.T;localI+=Jp-Javg;speed=-turn[i]*rotor[i]/10;K=np.array([[0,-speed,0],[speed,0,0],[0,0,0]]);dI+=K@Jp-Jp@K
 dw=np.linalg.solve(localI,torques-spin_rate-dI@w-np.cross(w,localI@w+spin))
 vv=v+dt*(np.array([0,0,9.8])+force/mass);pp=p+dt*vv;ww=w+dt*dw
 rv=ww*dt;angle=np.linalg.norm(rv);dq=np.r_[np.cos(angle/2),rv*(np.sin(angle/2)/angle if angle>1e-16 else .5)]
 qw,qx,qy,qz=q;dw0,dx,dy,dz=dq;qq=np.array([qw*dw0-qx*dx-qy*dy-qz*dz,qw*dx+qx*dw0+qy*dz-qz*dy,qw*dy-qx*dz+qy*dw0+qz*dx,qw*dz+qx*dy-qy*dx+qz*dw0]);qq/=np.linalg.norm(qq)
 if phase is not None:phase+=-turn*next_rotor/10*dt
 return pp,vv,qq,ww
