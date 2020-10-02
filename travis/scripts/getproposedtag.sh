#!/usr/bin/env bash

# Get base version
BASE_VERSION=`grep "FROM" $1 | cut -d " " -f 2 | cut -d ":" -f 2`

# Get all version ENV vars
ENV_VERSIONS=`grep "^ENV .*_VERSION .*" $1 | cut -d " " -f 3`

if [ -z "${ENV_VERSIONS:-}" ]; then
  echo ${BASE_VERSION}
else
  echo ${ENV_VERSIONS//$'\n'/'-'}-${BASE_VERSION}
fi
