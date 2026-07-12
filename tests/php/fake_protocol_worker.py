#!/usr/bin/env python3
import hashlib
import json
import os
import struct
import sys


def exact(length):
    data = b''
    while len(data) < length:
        chunk = sys.stdin.buffer.read(length - len(data))
        if not chunk:
            raise RuntimeError('truncated')
        data += chunk
    return data


header_length = struct.unpack('!I', exact(4))[0]
header = json.loads(exact(header_length).decode())
payload = sys.stdin.buffer.read()
password = b''
while True:
    chunk = os.read(3, 4096)
    if not chunk:
        break
    password += chunk
cmdline = (
    open('/proc/self/cmdline', 'rb').read()
    if os.path.exists('/proc/self/cmdline')
    else b''
)
if password != b's ecret' or b's ecret' in cmdline:
    response = {
        'version': 1,
        'ok': False,
        'requestId': header.get('requestId'),
        'error': {
            'code': 'transport-failed',
            'message': 'password transport failed',
        },
    }
    output = b''
else:
    output = payload + b'!'
    response = {
        'version': 1,
        'ok': True,
        'requestId': header.get('requestId'),
        'changed': True,
        'sha256': hashlib.sha256(output).hexdigest(),
        'outcomes': [{'recordId': '13'}],
    }
response['payloadLength'] = len(output)
raw = json.dumps(response, separators=(',', ':')).encode()
sys.stdout.buffer.write(struct.pack('!I', len(raw)) + raw + output)
