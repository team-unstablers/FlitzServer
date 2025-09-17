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
  - ~~TODO: 조건 설정 필요~~ 이대로 두어도 될 것 같다

## Implementation status

- [x] ChronoWave Matcher의 초기 구현
- [x] ChronoWave로 교환된 카드의 오픈 조건 설정 -> 이대로 유지하기로 한다
- [x] ChronoWave Matcher의 초기 테스트
- [x] ChronoWave Matcher 기능 개선
  - [x] 매칭 확률을 더 높이기 위한 구조 개선
    현재는 UserLocation은 반드시 하나만 저장하고 있음. LocationHistory를 저장하고, 2~3개 정도의 최근 위치를 활용하는 방안 검토
  - [ ] LocationHistory 플러싱 태스크 작성 및 주기 설정
  - [ ] ChronoWave를 수동으로 옵트아웃 할 수 있도록 한다
  - [ ] **(중요)** safety zone을 존중해야 한다: 사용자가 safety zone 내부에 있다면, ChronoWave 매칭 대상에서 제외한다



