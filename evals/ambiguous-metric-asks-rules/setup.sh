#!/bin/sh
# 공통 준비 스크립트(evals/_scaffold/olist.sh)를 부른다. eval 은 케이스 폴더 안의 스크립트만 받는다.
exec sh "$(dirname "$0")/../_scaffold/olist.sh"
