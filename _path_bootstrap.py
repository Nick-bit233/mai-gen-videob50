import os, subprocess, sys, re, time, glob
BASE = os.path.dirname(os.path.abspath(__file__))
CLIP_DIR = os.path.join(BASE, chr(98)+chr(53)+chr(48)+chr(95)+chr(100)+chr(97)+chr(116)+chr(97)+chr(115), os.listdir(os.path.join(BASE, chr(98)+chr(53)+chr(48)+chr(95)+chr(100)+chr(97)+chr(116)+chr(97)+chr(115)))[0], chr(118)+chr(105)+chr(100)+chr(101)+chr(111)+chr(115)+chr(95)+chr(99)+chr(112)+chr(117)+chr(95)+chr(98)+chr(97)+chr(116)+chr(99)+chr(104)+chr(101)+chr(115))
FFMPEG = os.path.join(BASE, chr(102)+chr(102)+chr(109)+chr(112)+chr(101)+chr(103)+chr(46)+chr(101)+chr(120)+chr(101))
FFPROBE = os.path.join(BASE, chr(102)+chr(102)+chr(112)+chr(114)+chr(111)+chr(98)+chr(101)+chr(46)+chr(101)+chr(120)+chr(101))
