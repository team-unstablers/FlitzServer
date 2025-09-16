# ChronoWave

## Why ChronoWave?

- Flitz는 사람들이 같은 시간에, 같은 공간에 있어야만 즐길 거리가 생기는 앱인데, 지금은 사람이 없으니 즐길 거리가 당연히 없다 -> 사람들이 안 모인다 -> **악순환**
- → 조금이라도 사람들이 매칭될 확률을 높여야 한다 -> **시간과 공간의 제약을 완화**해야 한다

## What is ChronoWave?

- ChronoWave는 일반 Wave와 달리, 시간과 공간의 제약을 어느 정도 완화한 매칭 시스템입니다.
  - 일반 Wave는 BLE를 주로 활용하기 때문에, 같은 시간에, 같은 공간에 있어야지만 매칭이 가능합니다. 
  - ChronoWave는 GPS Geohash를 활용하여, 같은 공간 판정의 범위를 넓히고, 시간의 제약도 완화하여 매칭 확률을 높입니다.

## Limitations of ChronoWave

- ChronoWave로 교환된 카드는, 일반 Wave로 교환된 카드보다 느리게 열립니다.
  - TODO: 조건 설정 필요

## Implementation status

- [x] ChronoWave Matcher의 초기 구현
- [ ] ChronoWave로 교환된 카드의 오픈 조건 설정 
- [ ] ChronoWave Matcher의 초기 테스트
- [ ] ChronoWave Matcher 기능 개선
  - [ ] 매칭 확률을 더 높이기 위한 구조 개선
    현재는 UserLocation은 반드시 하나만 저장하고 있음. LocationHistory를 저장하고, 2~3개 정도의 최근 위치를 활용하는 방안 검토
  - [ ] LocationHistory 플러싱 태스크 작성 및 주기 설정



