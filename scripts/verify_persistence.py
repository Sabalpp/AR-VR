"""Real PostgreSQL + Uvicorn restart check. All frames are explicitly SYNTHETIC.
Run from backend: DATABASE_URL=... uv run python ../scripts/verify_persistence.py
Requires migrated, seeded database. Creates isolated synthetic sessions; deletes nothing.
"""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
assert os.environ.get('DATABASE_URL', '').startswith('postgresql'), 'Supply a migrated PostgreSQL test DATABASE_URL'
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
base = f'http://127.0.0.1:{port}/api/v1'
process = None
log = open('/tmp/arvr-persistence-server.log', 'w')

def start():
    global process
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT/'backend', stdout=log, stderr=log)
    for _ in range(100):
        try:
            if httpx.get(f'http://127.0.0.1:{port}/api/openapi.json').status_code == 200: return
        except httpx.ConnectError: pass
        if process.poll() is not None: raise RuntimeError('Server failed; see /tmp/arvr-persistence-server.log')
        time.sleep(.1)
    raise RuntimeError('Server readiness timeout')

def stop():
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=10)

def req(method, path, token=None, body=None, expected=200):
    r = httpx.request(method, base+path, headers={'Authorization':f'Bearer {token}'} if token else {}, json=body, timeout=20)
    assert r.status_code == expected, (path,r.status_code,r.text)
    return r.json()

def collection(data,key): return data if isinstance(data,list) else data[key]

def login(email): return req('POST','/auth/login',body={'email':email,'password':os.environ.get('DEMO_PASSWORD','DemoTherapist123!' if email.startswith('therapist') else 'DemoPatient123!')})['access_token']

try:
    start()
    therapist = login('therapist@demo.local')
    patient_token = login('patient@demo.local')
    patients=collection(req('GET','/patients',therapist),'patients')
    exercises=collection(req('GET','/exercises',therapist),'exercises')
    assignment=req('POST','/assignments',therapist,{'patient_id':patients[0]['id'],'exercise_definition_id':exercises[0]['id'],'repetitions':3},expected=201)
    session=req('POST','/sessions',patient_token,{'assignment_id':assignment['id'],'mode':'phone','is_synthetic':True},expected=201)
    sid=session['id']
    pair=req('POST',f'/sessions/{sid}/pairing',patient_token,{'source':'simulator'})
    device=req('POST','/devices/pair',body={'code':pair['code'],'label':'SYNTHETIC restart acceptance'})
    dt=device['device_token']
    # right elbow at origin of vectors; bent=90, reach=180 projected degrees.
    t=datetime.now(timezone.utc)-timedelta(seconds=5)
    frames=[]
    for seq in range(16):
        reached=5<=seq<=9
        frames.append({'seq':seq,'captured_at':(t+timedelta(milliseconds=100*seq)).isoformat(),'coordinate_system':'image_normalized','units':'normalized','image_width':640,'image_height':480,'tracking_valid':True,'joints':{'right_shoulder':{'x':.3,'y':.5,'visibility':1},'right_elbow':{'x':.5,'y':.5,'visibility':1},'right_wrist':{'x':.7 if reached else .5,'y':.5 if reached else .7,'visibility':1}}})
    initial=req('POST',f'/sessions/{sid}/movement',dt,{'frames':frames})
    duplicate=req('POST',f'/sessions/{sid}/movement',dt,{'frames':frames})
    assert initial['accepted'] == 16 and initial['state']['repetitions'] == 1, 'Incorrect frame or repetition count'
    assert duplicate['accepted'] == 0 and duplicate['duplicates'] == 16, 'Duplicate frames accepted'
    before=req('GET',f'/sessions/{sid}/replay',therapist)
    stop(); start()
    after=req('GET',f'/sessions/{sid}/replay',therapist)
    assert before==after, 'Replay changed after server process restart'
    completed=req('POST',f'/sessions/{sid}/complete',dt,{})
    again=req('POST',f'/sessions/{sid}/complete',dt,{})
    assert completed==again, 'Completion not idempotent'
    req('POST',f'/sessions/{sid}/checkin',patient_token,{'pain':2,'effort':3,'notes':'SYNTHETIC verification fixture, not patient feedback.'})
    report=req('GET',f'/sessions/{sid}/report',therapist)
    stop(); start()
    assert req('GET',f'/sessions/{sid}/report',therapist)==report, 'Report did not survive restart'
    output={'kind':'synthetic_postgresql_restart_verification','session_id':sid,'ingest':initial,'duplicate':duplicate,'completion':completed,'report':report,'replay_identical_after_restart':True,'report_identical_after_restart':True}
    print(json.dumps(output,indent=2))
finally:
    stop()
    log.close()
