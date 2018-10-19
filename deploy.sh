#!/bin/bash

HASH=`git log --pretty=format:'%H' -n 1`

docker build -t evilben/telegraph_smtp:$HASH -f Dockerfile.smtp .
docker push evilben/telegraph_smtp:$HASH
#cat kubes/django.yaml | sed "s/(hash)/$HASH/g" | kubectl apply -f -
#kubectl -n wwfypc rollout status deployment/wwyfpc-django-test

