<section name="about-project">

이 프로젝트는 Flitz라는 남성 동성애자를 위한 데이팅 앱 서비스의 백엔드 서버입니다. 

Flitz 서비스에 대해서는 #service-description 섹션을 참고해주세요.
개발 관련 사항은 #development 섹션을 참고해주세요.

</section>
<section name="service-description">

# NAME

Flitz - 남성 동성애자를 위한 데이팅 앱 서비스

# SYNOPSIS

Flitz는 남성 동성애자를 위한 데이팅 앱 서비스입니다. 포토 카드를 통해 자기 자신을 표현할 수 있고, Bluetooth를 사용한 포토 카드 교환 기능을 통해 사용자들이 실제로 마주쳤거나 지나친 사람들을 발견하고, 소통할 수 있습니다. 

# KEY FEATURES

## 포토 카드 (프로필 카드)

Flitz에서는 사용자 자신을 나타내는 프로필 카드를 생성할 수 있습니다.
프로필 카드는 기존 게이 데이팅 앱에서의 정형화된 형식의 프로필이 아닌, 사용자가 자유롭게 꾸밀 수 있는 형태로 제공되며 **3D로 렌더링**되어 사용자에게 보여집니다.

- 카드 앞면에서는 Instagram의 스토리나 Twitter의 Fleet처럼, 자신을 나타내는 사진과 텍스트 등의 컨텐츠를 자유롭게 배치할 수 있습니다.
- 카드 뒷면에는 Jack'd나 Grindr처럼 프로필의 상세 정보 필드를 기재할 수 있습니다.
- 카드 프레임 또한 데코레이션 아이템을 사용하여 자유롭게 꾸밀 수 있습니다.

## 데코레이션 아이템

카드 앞면이나 프레임 등에 사용되는 데코레이션 아이템은 **유료**로 구매할 수 있으며, 일부 아이템은 **이벤트** 등을 통해 무료로 획득할 수 있습니다.

- **카드 프레임**
- **스티커**
- **코팅 효과**

또한, **그래픽 디자이너, 아티스트, 브랜드와의 콜라보레이션 상품도 판매**될 수 있습니다.

---

# 카드 교환 시스템

Flitz에서 사용자들이 서로를 발견하는 방법은 간단합니다. 단지 휴대폰에 Flitz 앱을 설치해놓고, 바깥을 돌아다니다 보면 **어느새 프로필 카드가 교환**되어 있는 것을 발견할 수 있습니다.

Flitz 앱은 **Bluetooth LE + GPS**를 사용하여 주변에 있는 Flitz 사용자들과 프로필 카드를 자동으로 교환합니다. 사용자는 교환된 카드를 확인하고, 상대방에게 호감을 표시할 수 있습니다. 상대방도 마찬가지로 사용자의 카드를 확인하고 호감을 표시할 수 있습니다.

호감이 서로 교환되면, 사용자들은 서로 매칭되어 채팅을 할 수 있습니다.

## DELAYED EXCHANGE

**Flitz 앱은 다른 사용자와 카드가 교환되었더라도, 곧바로 상대방의 카드를 표시하지 않습니다. 카드가 교환된 후 사용자에게 표시되려면 아래 조건을 만족해야 합니다.**

> TODO: 인스턴트하지 않은, 슬로우한 카드 교환을 의도하고 있는데, 이대로도 괜찮을까요? 사용자가 질려할 수도 있을 것 같은데요.

### soft condition

이 조건을 **전부** 만족하면 사용자에게 카드가 표시됩니다.

- 카드 교환 지점으로부터 2km 이상 멀어져야 함
- 카드 교환 시점으로부터 2시간 이상 경과해야 함

### hard condition

soft condition을 만족할 수 없는 경우, 이 조건 중 하나를 만족하면 사용자에게 카드가 표시됩니다.

- 카드 교환 지점으로부터 15km 이상 멀어져야 함
- 카드 교환 시점으로부터 24시간 이상 경과해야 함

### assertive condition

사용자의 안전을 최우선으로 하기 위해, 이 조건을 만족하지 않으면 앞의 조건들이 만족하더라도 사용자에게 카드가 표시되지 않습니다.

- opponent가 여전히 가까이 있으면 카드 표시하지 않음
- opponent가 **차단/제한 목록**에 등록되어 있으면 카드 표시하지 않음
- opponent가 **shadowban** 처리되어 있으면 카드 표시하지 않음

## PHASED REVEAL

- 첫 30분~1시간 이내에는 아예 표시가 안 되지만, 이후에는 (예: 1시간 후 + 1km 거리) 점진적으로 (blurry) 표시 가능.
- 구현이 복잡해질 수 있지만, “만나자마자 바로 공개되지 않는다” + “너무 오래 기다리지도 않는다”는 중간 솔루션이 될 수 있음.

phase = 0:
    완전 블러 이미지, 혹은 “기본 실루엣 + 닉네임/태그만” 표기
    예: 교환 직후 ~ 30분 (혹은 1시간) 이내

phase = 1:
    블러가 조금 줄어든 이미지, 혹은 “낮은 해상도” / “흐릿한 미리보기” 정도
    예: 1시간 ~ 2시간 경과 시점

phase = 2:
    완전한 카드 정보 공개 (Delayed Exchange 최종 상태)
    예: 2시간 이후 & 안전 거리(Soft Condition) 만족 시

---

# 사용자 보호 시스템

Flitz에서는 의도치 않은 아웃팅 방지를 위해, 사용자 자신을 보호할 수 있는 여러 보호 장치를 제공합니다. 이 보호 장치들은 사용이 강제 되지 않기 때문에 선택적으로 사용이 가능합니다.

현재 구상 중인 보호 시스템은 다음과 같습니다.

## FUZZY LOCATION

- Flitz 앱은 다른 게이 데이팅 앱과 다르게, 주변 사용자의 위치를 미터 거리 등의 수치로 표시하지 않습니다.
- 대신, Flitz 앱은 사용자의 위치를 "매우 가까움", "가까움", "중간", "멈", "매우 멈" 등의 텍스트로 표시합니다.

## 연락처 차단 및 제한

### 연락처 차단

- 사용자는 자신의 휴대폰에 저장된 연락처들을 Flitz 앱에 **차단 목록**으로 등록할 수 있습니다.
- 차단된 연락처에게는 Flitz 앱을 통해 사용자의 프로필 카드가 완전히 노출되지 않습니다.

### 연락처 제한

- 사용자는 자신의 휴대폰에 저장된 연락처들을 Flitz 앱에 **제한 목록**으로 등록할 수 있습니다.
- 제한 목록에 있는 연락처에게는 사용자의 프로필 카드가 표시되지만, 아래와 같은 제한이 적용됩니다.
    - 사용자의 프로필 카드가 회색 (단색)으로만 표시됨
    - 카드 중앙에 아래와 같은 메시지가 표시됨
    - 카드를 표시하려면 상대방에게 자신이 이 사용자의 카드를 조회했다는 알림이 전달됨

> 표시 제한된 사용자
> 
> 
> 당신이 알 수도 있는 사용자이기 때문에 이 프로필 카드는 표시가 제한되었습니다.
> 
> 아래 버튼을 누르면 카드를 표시할 수 있지만, 당신이 이 사용자의 카드를 조회했다는 사실이 상대방에게 알림으로 전달됩니다.
> 
> [표시하기]
> 

## 스토킹 방지

- Flitz 앱은 특정한 사용자가 자신의 프로필 카드를 비정상적으로 많이 조회하는 경우, 이 행위를 **스토킹**으로 간주하고, 해당 사용자를 shadowban 처리합니다.
- 추후 같은 휴대폰 번호나 같은 기기로 Flitz 앱을 다시 설치하여 사용하는 경우, 자동으로 shadowban 처리하고 스토킹 대상 사용자의 프로필 카드를 절대 표시하지 않습니다.

## 자동 오프라인 모드

- Flitz 앱은 사용자가 자신을 노출해선 안되는 상황에서 자신을 완전히 노출하지 않는 오프라인 모드로 전환합니다.
- 사용자가 오프라인 모드로 전환되면, 주변 사람들과의 프로필 카드 교환을 중단하고 채팅 알림 등을 완전히 표시하지 않습니다.
- 자동 오프라인 모드는 아래와 같은 트리거 조건을 설정할 수 있도록 하는 것을 구상하고 있습니다.
    - 사용자가 특정한 **위치**에 체류하고 있을 때 (예: 집, 회사, 학교 등)

## 사진 도용 방지 (옵트 아웃) 시스템

- 기존 데이팅 앱에서는 인플루언서나 일반 SNS 사용자들의 사진을 도용하는 악성 유저가 많았습니다.
- Flitz 앱에서는 이러한 도용 행위으로 인한 피해를 줄이기 위해 **사진 도용 방지 시스템**을 고안하였습니다.
    - 도용 피해를 겪고 있는 사람들로부터 자신을 증명할 수 있는 서류와 사진을 전달받으면, 사진으로부터 DNA를 추출(ResNet 등을 통한 feature map extract) 하여 **등록 금지 리스트**에 올립니다.
    - **등록 금지 리스트**에 올라간 사진들은 Flitz 앱 내에서 완전히 사용할 수 없게 됩니다.
- 사진에 담긴 얼굴을 인식하여, 해당 부분에 대한 DNA만을 추출해 사용하기 때문에 아래와 같은 이점이 있습니다.
    - 사진 자체가 서버에 저장되지 않습니다. (DNA가 저장되지만, DNA만으로는 절대 원본 사진을 만들어낼 수 없습니다)
    - 리사이즈나 필터를 사용해도 잡아낼 수 있습니다.
    *다만, 스티커나 얼굴 위에 낙서 등으로 덧칠을 한, 변형이 심한 것은 못 잡을 가능성이 있습니다..*

**사진 도용 방지 시스템**은 이러한 시나리오로 동작될 수 있습니다.

1. 지훈은 인스타그램에서 활동하는 인플루언서입니다. 그러나 데이팅 앱에서 자신의 사진을 도용하는 사람들이 가끔 있어 난감함을 겪고 있는 상황입니다.
2. 철호는 지훈의 사진을 도용하여 Flitz 앱에서 프로필을 생성하였고, 지훈 행세를 하고 다닙니다.
3. 지훈은 누군가 Flitz 앱에서 자신을 사칭하는 인물이 있다는 얘기를 들었습니다.
4. 지훈은 Flitz 앱의 고객 지원에 문의하여, 사진 도용 방지 시스템에 자신의 인스타그램 계정을 연동하였습니다.
5. Flitz 서버는 지훈의 인스타그램에 등록된 사진들로부터 **사진의 DNA**를 추출하여 블랙리스트에 올렸고, 철호의 계정은 곧바로 정지되었습니다.
6. 철호는 그 이후 다른 계정을 생성하여 같은 사진을 올리려 했지만, Flitz 서버에서 등록을 거부하여 도용을 포기하였습니다.
- 위 시나리오와 같은 케이스 외에도, 미리 선제적으로 옵트 아웃 신청을 해둠으로써 사진 도용을 사전에 차단할 수도 있습니다.

</section>
<section name="development">

# TECHNOLOGY STACK

## Backend Framework
- Django 5.1.3 (https://docs.djangoproject.com/en/5.1/)
- Django REST Framework 3.15.2 (https://www.django-rest-framework.org/)
- Django Channels 4.0.0 (https://channels.readthedocs.io/en/stable/)
- Python 3.12

## Database
- 개발환경: SQLite
- 프로덕션(예정): PostgreSQL (GinIndex 등의 PostgreSQL 전용 기능 사용 중)

## Storage
- S3 호환 객체 스토리지 (django-storages + boto3)
- MinIO 사용 (개발 환경)

## 비동기 작업 처리
- Celery 5.4.0 (Redis 브로커 사용)
- 푸시 알림 및 기타 백그라운드 작업 처리
- Django Channels + Redis 기반 실시간 WebSocket 통신

## 인증 및 알림
- 커스텀 JWT 기반 인증 (user_auth.authentication.UserSessionAuthentication)
- APNS(Apple Push Notification Service) 사용

## 의존성 관리
- Poetry (pyproject.toml, poetry.lock)

# PROJECT STRUCTURE

## 코어 앱 구조
- **flitz**: 프로젝트 설정, URL 라우팅, 공통 모델, 유틸리티
- **user**: 사용자 모델 및 프로필 관리, 매칭 기능
- **user_auth**: 인증 및 세션 관리
- **card**: 프로필 카드 및 에셋 관리
- **messaging**: 채팅 및 메시지 관리
- **location**: 위치 기반 기능, 사용자 발견 시스템
- **safety**: 사용자 보호 기능 (차단, 연락처 기반 제한, 자동 오프라인 모드)

# CODE CONVENTIONS

## 모델 구조
- 모든 모델은 `flitz.models.BaseModel` 상속 (UUIDv7 기반 ID 사용)
- Soft Delete 패턴: 실제 삭제 대신 `deleted_at`, `banned_at`, `disabled_at` 등의 필드 사용
- 타임스탬프 필드: `created_at`, `updated_at` 자동 추가

## 데이터 타입 및 모델링
- 복잡한 JSON 구조는 `dataclass`와 `TypedDict`로 타입 정의 (각 앱의 `objdef.py` 파일)
- `dacite` 라이브러리로 dict에서 dataclass로 변환
- 모델 관계: ForeignKey를 통한 명확한 관계 설정, related_name 적극 활용

## API 설계
- ViewSet 기반 REST API 구현
- 커서 기반 페이지네이션 (flitz.pagination.CursorPagination)
- 일관된 JSON 응답 포맷

## 비동기 작업
- Celery 태스크를 통한 푸시 알림 처리
- `delay_on_commit` 패턴: 트랜잭션 완료 후 태스크 실행

## 파일 관리
- 파일 저장 시 `object_key`와 `public_url` 함께 관리
- 자동 썸네일 생성 (이미지 첨부파일)
- 파일 삭제 시 스토리지에서도 함께 삭제하는 메서드 구현

# MODEL ARCHITECTURE

## Core Models (flitz 앱)
### BaseModel
- 모든 모델의 기본 클래스
- UUIDv7 기반 ID (시간순 정렬 가능)
- `created_at`, `updated_at` 자동 타임스탬프

## User Models (user 앱)
### User
- Django AbstractUser 상속
- 프로필 정보: `username`, `display_name`, `bio`, `hashtags`
- 프로필 이미지: 자동 썸네일 생성 및 S3 저장
- 코인 시스템: `free_coins`, `paid_coins`
- 연락처 차단 기능: `contacts_blocker_enabled`
- 관계: `main_card` (메인 프로필 카드), `primary_session` (주 세션)

### UserIdentity
- 사용자 성별 및 선호도 정보
- `gender`: 성별 (비트 마스크)
- `is_trans`, `display_trans_to_others`: 트랜스젠더 관련 설정
- `preferred_genders`: 선호 성별 (비트 마스크)
- `is_acceptable()`: 매칭 가능 여부 판단

### UserLike & UserMatch
- `UserLike`: 단방향 좋아요
- `UserMatch`: 양방향 좋아요 시 자동 생성
- 매칭 시 자동으로 대화방 생성 및 푸시 알림

## Authentication Models (user_auth 앱)
### UserSession
- JWT 기반 세션 관리
- APNS 토큰 저장 (`apns_token`)
- `create_token()`: JWT 토큰 생성
- `send_push_message()`: 푸시 알림 전송

## Card Models (card 앱)
### Card
- 프로필 카드 데이터 (JSON 구조)
- `content`: 카드 디자인 정보 (background, elements 등)
- `remove_orphaned_assets()`: 미사용 에셋 정리
- `get_content_with_url()`: S3 URL이 포함된 카드 데이터 반환

### CardDistribution
- 카드 교환 내역 및 공개 상태 관리
- `reveal_phase`: 공개 단계 (HIDDEN → BLURRY → FULLY_REVEALED)
- 위치 정보: `latitude`, `longitude`, `altitude`, `accuracy`
- 공개 조건 체크: `is_okay_to_reveal_soft/hard/assertive`

### OfficialCardAsset & UserCardAsset
- `OfficialCardAsset`: 공식 에셋 (유료 구매)
- `UserCardAsset`: 사용자 업로드 에셋
- 파일 자동 삭제 메서드 구현

## Messaging Models (messaging 앱)
### DirectMessageConversation
- 대화방 관리
- `latest_message`: 최신 메시지 참조
- `create_conversation()`: 대화방 생성 (중복 체크)

### DirectMessage
- 메시지 데이터 (JSON 구조)
- GinIndex로 검색 최적화
- `send_push_notification()`: 푸시 알림 자동 전송

### DirectMessageAttachment
- 첨부파일 메타데이터
- 자동 썸네일 생성 (이미지)
- S3 파일 관리

## Location Models (location 앱)
### UserLocation
- 사용자 현재 위치
- 자동 타임존 감지 (`update_timezone()`)
- `distance_to()`: 거리 계산 (haversine)

### DiscoverySession & DiscoveryHistory
- `DiscoverySession`: 사용자 발견 세션
- `DiscoveryHistory`: 발견 이력 (Bluetooth 교환 기록)

## Safety Models (safety 앱)
### UserWaveSafetyZone
- 자동 오프라인 모드 설정
- 특정 위치 반경 내 자동 비활성화

### UserBlock
- 사용자 차단/제한
- 차단 유형: BLOCK (완전 차단), LIMIT (제한)
- 차단 사유: BY_USER, BY_TRIGGER

### UserContactsTrigger
- 연락처 기반 자동 차단
- SHA256 해시된 전화번호 저장
- `evaluate()`: 트리거 평가
- `perform_block()`: 자동 차단 실행

# APP SPECIFIC FEATURES

## Card System (card 앱)
- 카드는 JSON 구조로 저장 (background, elements 등으로 구성)
- 3D 렌더링을 위한 데이터 구조 제공 (Transform, Position, ElementSize 등)
- 카드 에셋 시스템: 공식 에셋과 사용자 업로드 에셋 구분
- 에셋 구매 시스템 구현

## Messaging System (messaging 앱)
- 대화방(DirectMessageConversation)과 메시지(DirectMessage) 분리
- 메시지 내용은 JSON 형태로 저장 (텍스트, 첨부파일 등)
- 첨부파일 시스템 구현 (이미지, 동영상, 오디오 등)
- 메시지 신고 기능 구현 (DirectMessageFlag 모델)

### WebSocket 실시간 메시징
- **엔드포인트**: `ws/direct-messages/{conversation_id}/`
- **인증**: JWT 토큰을 쿼리 파라미터로 전달 (`?token=...`)
- **이벤트 타입**:
  - `message`: 새로운 메시지 수신
  - `read_event`: 읽음 상태 업데이트
- **자동 읽음 처리**: WebSocket 연결 시 및 메시지 수신 시 자동으로 읽음 상태 업데이트
- **채널 그룹**: `direct_message_{conversation_id}` 형태로 대화방별 그룹 관리

### 메시지 콘텐츠 타입 (objdef.py)
- **텍스트 메시지**: `{ type: 'text', text: string }`
- **첨부파일 메시지**: `{ type: 'attachment', attachment_type: string, attachment_id: string, public_url?: string, thumbnail_url?: string }`
- `load_direct_message_content()` 함수로 타입별 객체 변환

### REST API 엔드포인트
- **대화방 관리**: `/api/conversations/`
  - 대화방 생성 시 중복 체크 (이미 존재하는 대화방이면 409 Conflict)
  - Soft Delete 방식으로 삭제 처리
- **메시지 관리**: `/api/conversations/{conversation_id}/messages/`
  - 메시지 전송 시 WebSocket으로 실시간 이벤트 발송
  - `mark_as_read` 액션으로 읽음 상태 업데이트
- **첨부파일 관리**: `/api/conversations/{conversation_id}/attachments/`
  - 이미지 첨부 시 자동 썸네일 생성
  - 첨부파일 업로드 시 자동으로 메시지 생성

### 주요 모델 구조
- **DirectMessageConversation**: 대화방 (latest_message 참조)
- **DirectMessageParticipant**: 대화 참여자 (read_at 필드로 읽음 상태 관리)
- **DirectMessage**: 메시지 (content는 JSON, GinIndex로 검색 최적화)
- **DirectMessageAttachment**: 첨부파일 메타데이터 (S3 키와 URL 관리)

## User Matching (user 앱)
- 양방향 좋아요 시 자동 매칭 시스템
- 매칭 시 자동 대화방 생성 및 푸시 알림
- 유저 차단 기능

## Location & Discovery (location 앱)
- Bluetooth LE + GPS 기반 사용자 발견 시스템
- 지연된 카드 표시 (delayed exchange)
- 위치 정보 퍼지 처리 (정확한 거리 대신 상대적 표현)

## Safety System (safety 앱)
- 연락처 기반 자동 차단/제한
- 자동 오프라인 모드 (특정 위치 반경)
- 사용자 차단 관리

# API ENDPOINTS

## 인증
- `POST /auth/token` - JWT 토큰 발급

## 사용자
- `/users/` - 사용자 정보 조회 (PublicUserViewSet)

## 카드
- `/cards/` - 카드 관리 (PublicCardViewSet)
- `/cards/distribution/` - 카드 배포 관리 (CardDistributionViewSet)

## 메시징
- `/conversations/` - 대화방 관리
- `/conversations/{id}/messages/` - 메시지 관리
- `/conversations/{id}/attachments/` - 첨부파일 관리
- WebSocket: `ws/direct-messages/{conversation_id}/`

## 위치/발견
- `/wave/` - Wave (발견) 기능 (FlitzWaveViewSet)

## 안전
- `/blocks/` - 사용자 차단 관리 (UserBlockViewSet)
- `/contact-triggers/` - 연락처 트리거 관리 (UserContactsTriggerViewSet)

# DEVELOPMENT COMMANDS

## 개발 환경 설정
```bash
# Docker 컨테이너 실행 (MinIO, Redis)
cd flitz-devenv
docker-compose up -d

# Poetry 의존성 설치
poetry install
```

> ⚠️ **중요:** OpenAI Codex 에이전트가 로컬 CLI가 아닌 클라우드 컨테이너(예: GitHub Actions, Codespaces 등)에서 동작하는 경우, `.github/workflows/django-tests.yml`에서 수행하는 것처럼 `flitz-devenv` 디렉터리에서 `docker compose pull` 및 `docker compose up -d`를 반드시 실행해야 합니다. 그렇지 않으면 테스트 실행 시 필수 개발용 서비스가 준비되지 않아 실패합니다.

## 주요 개발 명령어
```bash
# 개발 서버 실행
poetry run python manage.py runserver

# 마이그레이션 생성
poetry run python manage.py makemigrations

# 마이그레이션 적용
poetry run python manage.py migrate

# 테스트 실행
poetry run python manage.py test

# 특정 앱 테스트만 실행
poetry run python manage.py test user
poetry run python manage.py test messaging.tests.test_views

# 특정 테스트 케이스 실행
poetry run python manage.py test user.tests.test_models.UserModelTest

# Shell 접속
poetry run python manage.py shell

# 관리자 계정 생성
poetry run python manage.py createsuperuser

# Celery 워커 실행 (백그라운드 작업)
poetry run celery -A flitz worker -l info

# Flower 실행 (Celery 모니터링)
poetry run celery -A flitz flower
```

## Swagger API 문서
- 개발 환경에서만 접근 가능
- `/swagger/` - Swagger UI
- `/redoc/` - ReDoc UI
- `/swagger.yaml` - OpenAPI 스키마

# DEVELOPMENT NOTES

## 코드 문서화
- 주요 메서드와 클래스에 대한 한국어 주석 작성
- TODO 주석으로 미완성 기능 표시 (예: 위치 기반 기능)

## 보안 및 프라이버시
- 사용자 보호 기능 구현 시 테스트 케이스 작성 권장
- 위치 정보, 사용자 데이터 처리 시 프라이버시 고려

## 확장성 고려사항
- 에셋 시스템 확장 시 타입 체계 유지
- 메시지 타입 확장 시 objdef.py 파일 업데이트 필요

## 환경 설정
- 개발 환경: docker-compose 사용 (devenv/docker-compose.yaml)
- MinIO, Redis 등의 서비스 포함

## 테스트 작성

### 테스트 유틸리티
- 테스트 객체 생성을 위한 공통 유틸리티는 `flitz/test_utils.py`에 정의
- 기본 객체 생성 함수:
  - `create_test_user(index=1, **kwargs)`: 테스트 사용자 생성
  - `create_test_session(user, **kwargs)`: 테스트 세션 생성
  - `create_test_card(user, **kwargs)`: 테스트 카드 생성
  - `create_test_user_location(user, **kwargs)`: 테스트 위치 정보 생성
  - `create_test_discovery_session(user, is_active=True, **kwargs)`: 테스트 디스커버리 세션 생성
- 복합 객체 생성 함수:
  - `create_test_user_with_session(index=1, **kwargs)`: 세션이 있는 테스트 사용자 생성
  - `create_test_user_with_card(index=1, set_as_main=True, **kwargs)`: 카드가 있는 테스트 사용자 생성
  - `create_test_user_with_location(index=1, **kwargs)`: 위치 정보가 있는 테스트 사용자 생성
  - `create_test_user_with_discovery_session(index=1, is_active=True, **kwargs)`: 디스커버리 세션이 있는 테스트 사용자 생성
  - `create_complete_test_user(index=1, with_card=True, with_session=True, with_location=True, with_discovery=True, **kwargs)`: 모든 관련 객체를 포함한 테스트 사용자 생성

### 테스트 유틸리티 사용 패턴
- 각 앱의 테스트 파일에서 테스트 유틸리티 가져오기:
  ```python
  from flitz.test_utils import create_test_user, create_test_user_with_card, ...
  ```
- 테스트 케이스 내에서의 기본 사용법:
  ```python
  class YourTestCase(TestCase):
      def setUp(self):
          self.user1 = create_test_user(1)  # testuser1
          self.user2 = create_test_user(2)  # testuser2
          # 또는
          test_objects = create_complete_test_user(with_card=True, with_session=True)
          self.user = test_objects['user']
          self.card = test_objects['card']
          self.session = test_objects['session']
  ```
- 모든 함수는 `**kwargs`를 지원하여 필요한 경우 기본값을 오버라이드 가능
- 로그인/회원가입/토큰 발급 테스트를 제외한 모든 테스트에서 이 유틸리티 사용 권장

### 테스트 모범 사례
- 각 테스트는 독립적으로 실행 가능해야 함
- 테스트 간 상태 공유 지양 (각 테스트 케이스는 자체적으로 필요한 상태 설정)
- 테스트 실행 속도를 위한 최소한의 객체만 생성 (예: 위치 테스트에 카드가 필요 없다면 생성하지 않음)
- 동일한 테스트 객체를 여러 테스트에서 반복 생성 시 테스트 유틸리티 활용

</section>
