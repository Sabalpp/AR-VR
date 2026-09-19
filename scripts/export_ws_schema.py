#!/usr/bin/env python3
"""Regenerate the versioned wire schema from frame/config Pydantic models."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.schemas.api import Frame, ExerciseConfig


def obj(properties, required=None, extra=False):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':extra}

string = {'type':'string'}
number = {'type':'number'}
boolean = {'type':'boolean'}
nullable_number = {'type':['number','null']}
nullable_string = {'type':['string','null']}
frame = Frame.model_json_schema()
config = ExerciseConfig.model_json_schema()
definitions = frame.pop('$defs', {})
definitions.update(config.pop('$defs', {}))
definitions['Frame'] = frame
definitions['ExerciseConfig'] = config
config['properties'].update({'target_repetitions':{'type':'integer','minimum':1,'maximum':100},'authoritative_counter':{'const':'backend'},'counter_stream':{'enum':['phone','quest']},'audio_owner':{'enum':['phone','quest']},'control_owner':{'enum':['phone','quest']},'capture_hz':{'const':10},'batch_interval_ms':{'const':250},'seated_only':{'const':True},'passthrough_required':boolean})
# Cross-field invariants are also checked by Frame's runtime validators.
frame['allOf'] = [{'if':{'properties':{'coordinate_system':{'const':'image_normalized'}}},'then':{'required':['image_width','image_height'],'properties':{'units':{'const':'normalized'},'image_width':{'type':'integer','minimum':1},'image_height':{'type':'integer','minimum':1}}},'else':{'properties':{'units':{'const':'meters'}}}}]
client_payloads = {
    'device.join':obj({'token':string}),
    'device.status':obj({'clock_offset_ms':number,'tracking_valid':boolean}),
    'tracking.frame':{'$ref':'#/$defs/Frame'},
    'exercise.event':obj({'seq':{'type':'integer','minimum':0},'name':{'type':'string','maxLength':100},'occurred_at':{'type':'string','format':'date-time'}}),
    'session.pause':obj({}), 'session.resume':obj({}), 'session.complete':obj({}),
}
# Server definitions populated to match the API implementation; optional context is explicit.
server_payloads = {
    'session.config':obj({'config':{'$ref':'#/$defs/ExerciseConfig'},'mode':{'enum':['phone','quest','combined']},'authoritative_counter':{'const':'backend'},'device_id':string,'last_seq':{'type':'integer','minimum':-1},'server_time':{'type':'string','format':'date-time'}}),
    'session.state':obj({'ack_id':string,'status':{'enum':['active','paused','complete']},'repetitions':{'type':'integer','minimum':0},'phase':{'enum':['waiting_return','ready','reached']},'last_measurement':nullable_number,'tracking_valid':boolean,'authoritative_device_id':nullable_string,'candidate_since':nullable_number,'last_capture_ms':nullable_number,'resume_after_ms':nullable_number,'accepted_frames':{'type':'integer','minimum':0},'invalid_frames':{'type':'integer','minimum':0},'tracking_gaps':{'type':'integer','minimum':0}},['ack_id','status','repetitions','phase','last_measurement','tracking_valid']),
    'exercise.feedback':obj({'message':string,'cue_id':{'enum':['reach','tracking_lost','adjust']},'attempt_id':string},['message','cue_id']),
    'session.summary':obj({'session_id':string,'repetitions':{'type':'integer','minimum':0},'report_path':string}),
    'error':obj({'code':string,'message':string,'ack_id':nullable_string,'retryable':boolean},['code','message','retryable']),
}
# Combined-mode observation fields are explicitly optional for older sessions.
state_properties = server_payloads['session.state']['properties']
for name in ('phone_device_id',):
    state_properties[name] = nullable_string
for name in ('phone_last_capture_ms', 'phone_capture_server_ms', 'phone_valid_since_ms', 'phone_trunk_lean_deg'):
    state_properties[name] = nullable_number
for name in ('phone_setup_ready', 'phone_tracking_valid', 'phone_trunk_review'):
    state_properties[name] = boolean
for name in ('trunk_observed_frames', 'trunk_review_frames'):
    state_properties[name] = {'type':'integer','minimum':0}
for name in ('attempt', 'last_attempt'):
    state_properties[name] = {'type':['object','null'], 'additionalProperties':True}
for name in ('attempts_completed', 'attempts_target_not_held', 'attempts_interrupted'):
    state_properties[name] = {'type':'integer','minimum':0}
branches=[]
for direction, payloads in [('client',client_payloads),('server',server_payloads)]:
    for kind,payload in payloads.items():
        name=direction+'_'+kind.replace('.','_')
        properties={'version':{'const':1},'type':{'const':kind},'id':{'type':'string','minLength':1,'maxLength':100},'payload':payload}
        definitions[name]=obj(properties, ['version','type','id','payload'] if direction=='client' else ['version','type','payload'])
        branches.append({'$ref':'#/$defs/'+name})
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://reach.example/contracts/websocket.v1.schema.json','title':'Reach WebSocket protocol v1','oneOf':branches,'$defs':definitions}
(ROOT/'contracts/websocket.v1.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
