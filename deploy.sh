#!/bin/bash

HASH=`git log --pretty=format:'%H' -n 1`

docker build -t evilben/telegraph_smtp:$HASH -f Dockerfile.smtp .
docker build -t evilben/telegraph_webhook:$HASH -f Dockerfile.http .
docker push evilben/telegraph_smtp:$HASH
docker push evilben/telegraph_webhook:$HASH
cat kubes/smtp.yaml | sed "s/(hash)/$HASH/g" | kubectl apply -f -
cat kubes/http.yaml | sed "s/(hash)/$HASH/g" | kubectl apply -f -
kubectl -n telegraph rollout status deployment/smtp
kubectl -n telegraph rollout status deployment/http

