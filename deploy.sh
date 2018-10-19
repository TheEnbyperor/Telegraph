#!/bin/bash

HASH=`git log --pretty=format:'%H' -n 1`

docker build -t evilben/telegraph_smtp:$HASH -f Dockerfile.smtp .
docker push evilben/telegraph_smtp:$HASH
cat kubes/smtp.yaml | sed "s/(hash)/$HASH/g" | kubectl apply -f -
#kubectl -n telegraph rollout status deployment/smtp

