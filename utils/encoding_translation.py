import os
import subprocess
import json
from pathlib import Path

def get_video_codec(file_path: str) -> str:
    """
    使用 ffprobe 获取视频的编码格式
    
    Args:
        file_path (str): 视频文件路径
    
    Returns:
        str: 视频编码格式，如果获取失败则返回空字符串
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',  # 只显示错误信息
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'json',
            str(file_path)
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        data = json.loads(result.stdout)
        return data['streams'][0]['codec_name']
    except Exception as e:
        print(f"获取视频编码信息失败: {str(e)}")
        return ""

def needs_conversion(file_path: Path) -> bool:
    """
    检查视频是否需要转换
    
    Args:
        file_path (Path): 视频文件路径
    
    Returns:
        bool: 是否需要转换
    """
    # 检查文件扩展名
    extension = file_path.suffix.lower()
    if extension != '.mp4':
        return True
    
    # 检查视频编码
    codec = get_video_codec(str(file_path))
    # 需要转换的编码列表
    codecs_to_convert = ['av1', 'vp8', 'vp9']
    return codec.lower() in codecs_to_convert

def convert_videos_to_avc1_mp4(directory_path: str) -> None:
    """
    遍历指定目录，将非mp4格式或非H.264编码的视频文件转换为mp4格式（H.264编码）
    
    Args:
        directory_path (str): 需要处理的目录路径
    """
    try:
        directory = Path(directory_path)
        
        # 遍历目录下的所有文件
        for file_path in directory.rglob('*'):
            # 跳过非视频文件
            if not file_path.is_file() or file_path.suffix.lower() not in \
                ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                continue
                
            if needs_conversion(file_path):
                print(f"正在处理文件: {file_path}")
                
                # 构建输出文件路径
                output_path = file_path.with_suffix('.mp4')
                temp_output_path = file_path.with_suffix('.temp.mp4')
                
                try:
                    # 使用 ffmpeg 进行转码，重定向输出
                    process = subprocess.run([
                        'ffmpeg',
                        '-hide_banner',  # 隐藏 ffmpeg 版本信息
                        '-loglevel', 'error',  # 只显示错误信息
                        '-i', str(file_path),
                        '-c:v', 'libx264',     
                        '-preset', 'medium',    
                        '-crf', '23',          
                        '-c:a', 'aac',         
                        '-b:a', '192k',        
                        '-y',                  
                        str(temp_output_path)
                    ], 
                    stdout=subprocess.PIPE,  # 捕获标准输出
                    stderr=subprocess.PIPE,  # 捕获错误输出
                    text=True)
                    
                    # 如果有错误输出，打印错误信息
                    if process.stderr:
                        print(f"转码警告/错误: {process.stderr}")
                    
                    if process.returncode == 0:
                        if file_path != output_path:
                            file_path.unlink()
                        if output_path.exists():
                            output_path.unlink()
                        temp_output_path.rename(output_path)
                        print(f"成功转换: {file_path} -> {output_path}")
                    else:
                        raise subprocess.CalledProcessError(process.returncode, process.args)
                    
                except subprocess.CalledProcessError as e:
                    print(f"转换失败 {file_path}: {str(e)}")
                    # 清理临时文件
                    if temp_output_path.exists():
                        temp_output_path.unlink()
                except Exception as e:
                    print(f"处理文件时出错 {file_path}: {str(e)}")
                    # 清理临时文件
                    if temp_output_path.exists():
                        temp_output_path.unlink()
            else:
                print(f"跳过文件（无需转换）: {file_path}")
                    
    except Exception as e:
        print(f"遍历目录时出错: {str(e)}")

if __name__ == "__main__":
    # 使用示例
    directory_to_process = r"E:\Test\mai-gen-videob50_release_v03_1\videos\downloads"
    convert_videos_to_avc1_mp4(directory_to_process)
