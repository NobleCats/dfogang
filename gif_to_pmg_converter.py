# gif_to_png_converter.py

import os
from PIL import Image, UnidentifiedImageError
from pathlib import Path

# 검색을 시작할 최상위 폴더를 지정합니다.
ROOT_ASSETS_FOLDER = "assets/characters"

def convert_gifs_to_pngs(root_folder):
    """
    지정된 폴더와 그 하위 폴더를 모두 탐색하여
    모든 .gif 파일의 첫 프레임을 .png 파일로 저장합니다.
    """
    
    # Path 객체로 변환
    base_path = Path(root_folder)

    if not base_path.is_dir():
        print(f"오류: '{root_folder}' 폴더를 찾을 수 없습니다. 스크립트가 올바른 위치에 있는지 확인해주세요.")
        return

    print(f"'{root_folder}' 폴더에서 .gif 파일 검색을 시작합니다...")

    # .rglob('*.gif')를 사용하여 모든 하위 폴더의 .gif 파일을 찾습니다.
    gif_files = list(base_path.rglob('*.gif'))
    
    if not gif_files:
        print(".gif 파일을 찾지 못했습니다.")
        return

    total_files = len(gif_files)
    converted_count = 0
    
    for i, gif_path in enumerate(gif_files):
        # 출력될 .png 파일의 경로를 생성합니다. (예: .../berserker.gif -> .../berserker.png)
        png_path = gif_path.with_suffix('.png')
        
        # 이미 .png 파일이 존재하면 건너뜁니다.
        if png_path.exists():
            print(f"[{i+1}/{total_files}] 건너뛰기: '{png_path.name}' 파일이 이미 존재합니다.")
            continue
            
        try:
            # GIF 이미지 열기
            with Image.open(gif_path) as img:
                # 첫 프레임으로 이동 (기본적으로 첫 프레임이 로드됨)
                img.seek(0)
                
                # PNG로 저장
                img.save(png_path, 'PNG')
                converted_count += 1
                print(f"[{i+1}/{total_files}] 성공: '{gif_path.name}' -> '{png_path.name}'")

        except (UnidentifiedImageError, FileNotFoundError, Exception) as e:
            print(f"[{i+1}/{total_files}] 실패: '{gif_path.name}' 처리 중 오류 발생 - {e}")

    print(f"\n변환 완료! 총 {total_files}개의 GIF 파일 중 {converted_count}개를 PNG로 변환했습니다.")


if __name__ == "__main__":
    convert_gifs_to_pngs(ROOT_ASSETS_FOLDER)