#!/bin/sh -e

export AWS_DEFAULT_PROFILE=team-unstablers
export AWS_DEFAULT_REGION=ap-northeast-2

export IMAGE_TAG=$1

if [ -z "$IMAGE_TAG" ]; then
  echo "Usage: $0 <image_tag>"
  exit 1
fi

aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin 815922082153.dkr.ecr.ap-northeast-2.amazonaws.com

# Get git commit hash
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Check if working directory is dirty
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    GIT_COMMIT="${GIT_COMMIT}-dirty"
fi

echo "Building Docker image with Git commit: $GIT_COMMIT"

docker build --build-arg GIT_COMMIT=$GIT_COMMIT -t team-unstablers/flitz-server:$IMAGE_TAG -t 815922082153.dkr.ecr.ap-northeast-2.amazonaws.com/team-unstablers/flitz-server:$IMAGE_TAG -t 815922082153.dkr.ecr.ap-northeast-2.amazonaws.com/team-unstablers/flitz-server:latest .
docker push 815922082153.dkr.ecr.ap-northeast-2.amazonaws.com/team-unstablers/flitz-server:$IMAGE_TAG
docker push 815922082153.dkr.ecr.ap-northeast-2.amazonaws.com/team-unstablers/flitz-server:latest

