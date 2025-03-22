from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from safety.models import UserBlock
from safety.serializers import UserBlockSerializer
from user.models import User


class UserBlockViewSet(viewsets.ModelViewSet):
    serializer_class = UserBlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # 요청한 사용자가 생성한 차단 정보만 반환하며, BY_TRIGGER는 제외합니다
        return UserBlock.objects.filter(
            blocked_by=self.request.user,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER  # BY_TRIGGER는 제외
        )
    
    def create(self, request, *args, **kwargs):
        # 차단할 사용자 ID 필요
        user_id = request.data.get('user_id')
        
        # 사용자 존재 확인
        try:
            user_to_block = User.objects.get(id=user_id, disabled_at=None, fully_deleted_at=None)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # 이미 차단한 사용자인지 확인
        existing_block = UserBlock.objects.filter(
            user=user_to_block,
            blocked_by=request.user
        ).first()
        
        if existing_block:
            # 이미 존재하는 경우 새로운 정보로 업데이트하지 않고 기존 차단 정보 반환
            serializer = self.get_serializer(existing_block)
            return Response(serializer.data)
        
        # 새로운 차단 생성 (항상 BLOCK 타입으로만 생성)
        block = UserBlock.objects.create(
            user=user_to_block,
            blocked_by=request.user,
            type=UserBlock.Type.BLOCK,  # 항상 BLOCK 타입으로 설정
            reason=UserBlock.Reason.BY_USER
        )
        
        serializer = self.get_serializer(block)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        # 전체 업데이트 지원하지 않음
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def partial_update(self, request, *args, **kwargs):
        # 부분 업데이트도 지원하지 않음
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # 트리거에 의한 차단은 삭제 불가
        if instance.reason == UserBlock.Reason.BY_TRIGGER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        # 직접 삭제 수행
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
