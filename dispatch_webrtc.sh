#!/bin/bash

CALL_TYPE=$1
ROOM_NAME=$2  # first argument to script
echo "CALL_TYPE=$CALL_TYPE"
echo "ROOM_NAME=$ROOM_NAME"

METADATA=$(cat <<EOF
{
  "name": "Ajay",
  "email": "x@gmail.com",
  "phone": "+919450929771",
  "call_type": "$CALL_TYPE"
}
EOF
)

lk dispatch create \
  --room "$ROOM_NAME" \
  --agent-name 'Everest Agent' \
  --api-key 'APIoLr2sRCRJWY5' \
  --api-secret 'yE3wUkoQxjWjhteMAed9ubm5mYg3iOfPT6qBQfffzgJC' \
  --metadata "$METADATA" \
  --url 'wss://setupforretell-hk7yl5xf.livekit.cloud'
