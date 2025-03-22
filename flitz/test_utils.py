from django.contrib.auth import get_user_model
from user_auth.models import UserSession
from card.models import Card
from location.models import UserLocation, DiscoverySession

User = get_user_model()

def create_test_user(index=1, **kwargs):
    """
    테스트용 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        **kwargs: 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        User: 생성된 사용자 객체
    """
    defaults = {
        'username': f'testuser{index}',
        'display_name': f'Test User {index}',
        'password': f'testpassword{index}'
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)

def create_test_session(user, **kwargs):
    """
    테스트용 사용자 세션을 생성합니다.
    
    Args:
        user: 세션의 소유자 (User 객체)
        **kwargs: 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        UserSession: 생성된 세션 객체
    """
    defaults = {
        'description': 'Test Session',
        'initiated_from': '127.0.0.1',
        'apns_token': 'test_token'
    }
    defaults.update(kwargs)
    return UserSession.objects.create(user=user, **defaults)

def create_test_card(user, **kwargs):
    """
    테스트용 카드를 생성합니다.
    
    Args:
        user: 카드의 소유자 (User 객체)
        **kwargs: 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        Card: 생성된 카드 객체
    """
    defaults = {
        'title': 'Test Card',
        'content': {"schema_version": "v1.0-test", "background": None, "elements": [], "properties": {}}
    }
    defaults.update(kwargs)
    return Card.objects.create(user=user, **defaults)

def create_test_user_location(user, **kwargs):
    """
    테스트용 사용자 위치 정보를 생성합니다.
    
    Args:
        user: 위치 정보의 소유자 (User 객체)
        **kwargs: 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        UserLocation: 생성된 위치 정보 객체
    """
    defaults = {
        'latitude': 37.5665,
        'longitude': 126.9780,
        'altitude': 10.0,
        'accuracy': 5.0,
        'timezone': 'Asia/Seoul'
    }
    defaults.update(kwargs)
    return UserLocation.objects.create(user=user, **defaults)

def create_test_discovery_session(user, is_active=True, **kwargs):
    """
    테스트용 디스커버리 세션을 생성합니다.
    
    Args:
        user: 세션의 소유자 (User 객체)
        is_active: 세션 활성화 여부
        **kwargs: 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        DiscoverySession: 생성된 디스커버리 세션 객체
    """
    defaults = {
        'is_active': is_active
    }
    defaults.update(kwargs)
    return DiscoverySession.objects.create(user=user, **defaults)

# 복합 헬퍼 함수

def create_test_user_with_session(index=1, **kwargs):
    """
    세션이 있는 테스트 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        **kwargs: User 생성 시 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        tuple: (User, UserSession) 생성된 사용자와 세션 객체
    """
    user = create_test_user(index, **kwargs)
    session = create_test_session(user)
    return user, session

def create_test_user_with_card(index=1, set_as_main=True, **kwargs):
    """
    카드가 있는 테스트 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        set_as_main: 생성된 카드를 메인 카드로 설정할지 여부
        **kwargs: User 생성 시 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        tuple: (User, Card) 생성된 사용자와 카드 객체
    """
    user = create_test_user(index, **kwargs)
    card = create_test_card(user)
    if set_as_main:
        user.main_card = card
        user.save()
    return user, card

def create_test_user_with_location(index=1, **kwargs):
    """
    위치 정보가 있는 테스트 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        **kwargs: User 생성 시 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        tuple: (User, UserLocation) 생성된 사용자와 위치 정보 객체
    """
    user = create_test_user(index, **kwargs)
    location = create_test_user_location(user)
    return user, location

def create_test_user_with_discovery_session(index=1, is_active=True, **kwargs):
    """
    디스커버리 세션이 있는 테스트 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        is_active: 세션 활성화 여부
        **kwargs: User 생성 시 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        tuple: (User, DiscoverySession) 생성된 사용자와 디스커버리 세션 객체
    """
    user = create_test_user(index, **kwargs)
    session = create_test_discovery_session(user, is_active=is_active)
    return user, session

def create_complete_test_user(index=1, with_card=True, with_session=True, 
                             with_location=True, with_discovery=True, **kwargs):
    """
    모든 관련 객체를 포함한 완전한 테스트 사용자를 생성합니다.
    
    Args:
        index: 사용자명/표시이름에 추가될 번호 (고유성 확보용)
        with_card: 카드 생성 여부
        with_session: 세션 생성 여부
        with_location: 위치 정보 생성 여부
        with_discovery: 디스커버리 세션 생성 여부
        **kwargs: User 생성 시 기본값을 오버라이드할 추가 파라미터
    
    Returns:
        dict: 생성된 모든 객체를 포함하는 딕셔너리
        {
            'user': User 객체,
            'card': Card 객체 (with_card=True인 경우),
            'session': UserSession 객체 (with_session=True인 경우),
            'location': UserLocation 객체 (with_location=True인 경우),
            'discovery_session': DiscoverySession 객체 (with_discovery=True인 경우)
        }
    """
    result = {'user': create_test_user(index, **kwargs)}
    
    if with_card:
        card = create_test_card(result['user'])
        result['user'].main_card = card
        result['user'].save()
        result['card'] = card
        
    if with_session:
        result['session'] = create_test_session(result['user'])
        
    if with_location:
        result['location'] = create_test_user_location(result['user'])
        
    if with_discovery:
        result['discovery_session'] = create_test_discovery_session(result['user'])
        
    return result
