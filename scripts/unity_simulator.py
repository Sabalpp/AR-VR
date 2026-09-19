#!/usr/bin/env python3
"""Synthetic Quest-coordinate protocol exerciser. Never represents real captures.
Run with the backend virtualenv (httpx, websockets). See docs/unity-interface.md.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import websockets


def now():
    return datetime.now(timezone.utc).isoformat()


async def run(args):
    origin = args.origin.rstrip('/')
    parsed = urlparse(origin)
    if parsed.scheme != 'https' and not (args.allow_local_http and parsed.hostname in ('localhost', '127.0.0.1')):
        raise SystemExit('Use an HTTPS public origin. --allow-local-http is for laptop-only testing.')
    password = os.environ.get('SIMULATOR_PASSWORD', 'DemoPatient123!')
    async with httpx.AsyncClient(base_url=origin, timeout=20) as client:
        async def post(path, data):
            response = await client.post('/api/v1' + path, json=data)
            response.raise_for_status()
            return response.json()
        auth = await post('/auth/login', {'email':args.email, 'password':password})
        client.headers['Authorization'] = 'Bearer ' + auth['access_token']
        session = await post('/sessions', {'assignment_id':args.assignment_id,'mode':'quest','is_synthetic':True})
        session_id = session['id']
        pairing = await post('/sessions/' + session_id + '/pairing', {'source':'simulator'})
        device = await post('/devices/pair', {'code':pairing['code'],'label':'SYNTHETIC Unity protocol simulator'})
        print('SYNTHETIC ONLY — no physical phone or Quest was used. Session:', session_id)
        ws_url = origin.replace('https://','wss://',1).replace('http://','ws://',1) + '/api/v1/ws/' + session_id
        async with websockets.connect(ws_url, max_queue=16, max_size=262144) as ws:
            async def exchange(kind, payload):
                message_id = str(uuid4())
                await ws.send(json.dumps({'version':1,'type':kind,'id':message_id,'payload':payload}))
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if message['type'] == 'error':
                        raise RuntimeError(message)
                    if message['type'] in ('session.config','session.summary') or message.get('payload',{}).get('ack_id') == message_id:
                        return message
            config_message = await exchange('device.join', {'token':device['device_token']})
            print('Connected:', json.dumps(config_message))
            payload = config_message.get('payload',{})
            snapshot = payload.get('config',payload.get('configuration',payload))
            target = snapshot.get('quest_target_m', {'x':0,'y':1,'z':0.5})
            await exchange('device.status', {'clock_offset_ms':0,'tracking_valid':True})
            return_distance = snapshot['quest_return_m'] + max(.1, snapshot['quest_return_m'] * .2)
            reach_distance = snapshot['quest_reach_m'] / 2
            hold_samples = math.ceil(snapshot['hold_ms'] / 100) + 3
            seq = 0
            for repetition in range(args.repetitions):
                # Stable synthetic return/reach/return honoring the saved thresholds.
                for distance in (return_distance, reach_distance, return_distance):
                    for _ in range(hold_samples):
                        wrist = {'x':target['x']+distance,'y':target['y'],'z':target['z'],'visibility':1,'inferred':False}
                        frame = {'seq':seq,'captured_at':now(),'coordinate_system':'quest_local','units':'meters','tracking_valid':True,'joints':{'right_wrist':wrist}}
                        await exchange('tracking.frame', frame)
                        seq += 1
                        await asyncio.sleep(.1)
                await exchange('exercise.event', {'seq':repetition,'name':'unity_local_reach_complete','occurred_at':now()})
                print('Synthetic movement cycle', repetition+1)
            result = await exchange('session.complete', {})
            if result['type'] != 'session.summary':
                result = json.loads(await asyncio.wait_for(ws.recv(),20))
            print(json.dumps(result, indent=2))
        print('Review the explicitly synthetic session:', origin + '/dashboard/sessions/' + session_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--assignment-id', required=True)
    parser.add_argument('--email', default='patient@demo.local')
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--allow-local-http', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 100:
        parser.error('--repetitions must be 1..100')
    asyncio.run(run(args))
