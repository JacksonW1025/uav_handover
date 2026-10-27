"""Uniform direct child CPU/address-space limits before exec, no shell."""
import sys,os,resource
cpu=int(sys.argv[1]);memory=int(sys.argv[2]);resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_AS,(memory*1024**3,memory*1024**3));os.execv(sys.argv[3],sys.argv[3:])
