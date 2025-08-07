from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from PIL import Image

def generate_thumbnail(input_file: File, max_height: int = 768, jpeg_quality: int = 85) -> (File, (int, int)):
    """
    주어진 입력 파일에 대해 썸네일을 생성합니다.
    원본의 aspect ratio를 유지하며, 높이가 max_height를 초과하는 경우에만 리사이징합니다.
    EXIF 데이터는 보안과 프라이버시를 위해 제거됩니다.
    
    :param input_file: 입력 이미지 파일
    :param max_height: 최대 높이 (픽셀). 이보다 작은 이미지는 리사이징하지 않음
    :param jpeg_quality: JPEG 품질 (1-100, 기본값 85)
    :returns: 썸네일 파일 객체 (EXIF 데이터 제거됨)
    """
    image = Image.open(input_file)
    
    # EXIF 방향 정보에 따라 이미지 회전 (카메라 촬영 이미지 대응)
    try:
        from PIL import ImageOps
        image = ImageOps.exif_transpose(image)
    except:
        pass
    
    # 원본 크기 확인
    original_width, original_height = image.size
    
    # 높이가 max_height보다 작거나 같으면 리사이징하지 않음
    if original_height <= max_height:
        # 리사이징 없이 원본 유지
        resized_image = image
    else:
        # aspect ratio 유지하면서 높이 기준으로 리사이징
        aspect_ratio = original_width / original_height
        new_height = max_height
        new_width = int(new_height * aspect_ratio)
        
        # 고품질 리샘플링 사용
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # RGBA 이미지를 RGB로 변환 (JPEG는 알파 채널 미지원)
    if resized_image.mode in ('RGBA', 'LA', 'P'):
        # 흰색 배경 생성
        background = Image.new('RGB', resized_image.size, (255, 255, 255))
        if resized_image.mode == 'P':
            resized_image = resized_image.convert('RGBA')
        background.paste(resized_image, mask=resized_image.split()[-1] if resized_image.mode in ('RGBA', 'LA') else None)
        resized_image = background
    elif resized_image.mode not in ('RGB', 'L'):
        resized_image = resized_image.convert('RGB')
    
    temp_file = NamedTemporaryFile()
    # JPEG로 저장할 때 EXIF 데이터를 포함하지 않음
    # save 메서드에 exif 파라미터를 명시적으로 제공하지 않으면 EXIF가 제거됨
    resized_image.save(temp_file, format="JPEG", quality=jpeg_quality, optimize=True)
    
    temp_file.seek(0)
    return File(temp_file), (resized_image.width, resized_image.height)