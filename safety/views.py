from typing import List

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from flitz.exceptions import UnsupportedOperationException
from safety.models import UserBlock, UserContactsTrigger
from safety.serializers import UserBlockSerializer, UserContactsTriggerSerializer, UserContactsTriggerBulkCreateSerializer, \
    UserContactsTriggerEnableSetterSerializer
from safety.tasks import evaluate_block_triggers
from safety.utils.phone_number import normalize_phone_number, hash_phone_number
from user.models import User


class UserBlockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserBlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # 요청한 사용자가 생성한 차단 정보만 반환하며, BY_TRIGGER는 제외합니다
        return UserBlock.objects.filter(
            blocked_by=self.request.user,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER  # BY_TRIGGER는 제외
        )
    
class UserContactsTriggerViewSet(viewsets.ModelViewSet):
    """
    연락처 기반 차단 트리거를 관리하는 ViewSet입니다.
    """
    serializer_class = UserContactsTriggerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.contacts_triggers.all()

    def create(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    @action(detail=False, methods=['GET', 'PATCH'], permission_classes=[permissions.IsAuthenticated], url_path='enabled')
    def dispatch_enabled(self, request, *args, **kwargs):
        """
        연락처 기반 차단 트리거의 활성화 상태를 조회하거나 업데이트합니다.
        """
        if request.method == 'GET':
            return self.get_enabled(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_enabled(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_enabled(self, request, *args, **kwargs):
        """
        연락처 기반 차단 트리거의 활성화 상태를 조회합니다.
        """
        return Response({'is_enabled': request.user.contacts_blocker_enabled}, status=status.HTTP_200_OK)

    def patch_enabled(self, request, *args, **kwargs):
        """
        연락처 기반 차단 트리거의 활성화 상태를 업데이트합니다.
        """

        serializer = UserContactsTriggerEnableSetterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request.user.contacts_blocker_enabled = serializer.validated_data['is_enabled']
        request.user.save(update_fields=['contacts_blocker_enabled'])

        return Response({'is_enabled': request.user.contacts_blocker_enabled}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['POST'], permission_classes=[permissions.IsAuthenticated], url_path='bulk-create')
    def bulk_create(self, request, *args, **kwargs):
        """
        연락처 기반 차단 트리거를 일괄 생성합니다.
        """

        serializer = UserContactsTriggerBulkCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_numbers: List[str] = serializer.validated_data['phone_numbers']

        existing_hashes = UserContactsTrigger.objects.filter(
            user=request.user
        ).values_list('phone_number_hashed', flat=True)

        # 모든 전화번호를 normalize하고 hash
        hashed_phone_numbers = []
        for phone_number in phone_numbers:
            try:
                normalized_phone_number = normalize_phone_number(phone_number, request.user.country)
                hashed_phone_number = hash_phone_number(normalized_phone_number)

                if hashed_phone_number == self.request.user.phone_number_hashed:
                    # 자신의 전화번호는 트리거로 추가할 수 없도록 한다
                    continue

                hashed_phone_numbers.append(hashed_phone_number)
            except Exception as e:
                # TODO: report to sentry and continue
                print(e)
                continue


        # 이미 존재하는 항목들 조회 (사용자별 + 전체에서 unique)
        existing_hashes = set(existing_hashes)

        # 새로 생성할 항목들만 필터링
        triggers_to_create = [
            UserContactsTrigger(
                user=request.user,
                phone_number_hashed=hashed_phone_number
            )
            for hashed_phone_number in hashed_phone_numbers
            if hashed_phone_number not in existing_hashes
        ]

        triggers_to_delete = [
            existing_hash for existing_hash in existing_hashes if existing_hash not in hashed_phone_numbers
        ]

        # bulk_create로 한 번에 생성
        if triggers_to_create:
            print(f"Creating {len(triggers_to_create)} new triggers for user {request.user.id}")
            UserContactsTrigger.objects.bulk_create(triggers_to_create, ignore_conflicts=True)

        # 트리거에는 존재하지만, phone_numbers에는 없는 항목들은 삭제
        if triggers_to_delete:
            UserContactsTrigger.objects.filter(
                user=request.user,
                phone_number_hashed__in=triggers_to_delete
            ).delete()

        # 트리거를 평가하여 차단 수행
        evaluate_block_triggers.delay_on_commit(request.user.id)

        return Response({'is_success': True}, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['DELETE'], permission_classes=[permissions.IsAuthenticated], url_path='all')
    def delete_all(self, request, *args, **kwargs):
        """
        연락처 기반 차단 트리거를 일괄 삭제합니다.
        """

        # 모든 연락처 기반 차단 트리거 삭제
        UserContactsTrigger.objects.filter(user=request.user).delete()
        return Response({'is_success': True}, status=status.HTTP_204_NO_CONTENT)
