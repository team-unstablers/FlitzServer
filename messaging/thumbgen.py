from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from PIL import Image

def generate_thumbnail(input_file: File) -> NamedTemporaryFile:
    """
    주어진 입력 파일에 대해 썸네일을 생성합니다.
    :returns: 썸네일 파일 객체
    """
    image = Image.open(input_file)
    image.thumbnail((200, 200))

    temp_file = NamedTemporaryFile()
    image.save(temp_file, format="JPEG")

    temp_file.seek(0)
    return temp_file