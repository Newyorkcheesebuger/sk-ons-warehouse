#!/usr/bin/env bash
# render-build.sh

set -o errexit  # exit on error

# 시스템 패키지 업데이트
apt-get update

# PostgreSQL 클라이언트 라이브러리 설치
apt-get install -y libpq-dev

# Python 개발 헤더 설치  
apt-get install -y python3-dev

# GCC 컴파일러 설치
apt-get install -y gcc

# pip 업그레이드
pip install --upgrade pip

# requirements.txt 설치
pip install -r requirements.txt
