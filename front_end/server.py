from flask import Flask, send_file, jsonify, request, send_from_directory
import os
import json
import traceback

app = Flask(__name__)

# 配置存储
config = {
    'config_file': None,
    'image_output_path': None,
    'video_download_path': None,
    'username': None,
    'root_dir': None  # 存储项目根目录路径
}

def serve_file(file_path, content_type, as_attachment=False):
    """通用文件服务功能"""
    if not os.path.exists(file_path):
        return {'error': 'File not found'}, 404
    return send_file(file_path, mimetype=content_type, as_attachment=as_attachment)

@app.route('/')
def serve_editor():
    """服务主页面"""
    front_end_dir = os.path.dirname(os.path.abspath(__file__))
    editor_path = os.path.join(front_end_dir, 'editor.html')
    return send_file(editor_path)

@app.route('/config')
def serve_config():
    """服务配置文件"""
    config_path = os.path.join(config['root_dir'], config['config_file'])
    if not os.path.exists(config_path):
        return {'error': 'Config file not found'}, 404
    return send_file(config_path, mimetype='application/json')

@app.route('/username')
def serve_username():
    """服务用户名"""
    return config['username']

@app.route('/images/<path:filename>')
def serve_image(filename):
    """服务生成的图片"""
    # 将相对路径转换为基于项目根目录的完整路径
    image_path = os.path.join(config['root_dir'], config['image_output_path'], filename)
    return serve_file(image_path, 'image/png')

@app.route('/asset/images/<path:filename>')
def serve_asset_image(filename):
    """服务静态资源图片"""
    images_dir = os.path.join(config['root_dir'], "images")
    image_path = os.path.join(images_dir, filename)
    return serve_file(image_path, 'image/png')

@app.route('/videos/<path:filename>')
def serve_video(filename):
    """服务视频文件，支持范围请求"""
    # 将相对路径转换为基于项目根目录的完整路径
    video_path = os.path.join(config['root_dir'], config['video_download_path'], filename)
    if not os.path.exists(video_path):
        return {'error': 'Video not found'}, 404

    range_header = request.headers.get('Range')
    if not range_header:
        return send_file(video_path, mimetype='video/mp4')

    # 处理范围请求
    try:
        file_size = os.path.getsize(video_path)
        bytes_range = range_header.replace('bytes=', '').split('-')
        start = int(bytes_range[0])
        end = int(bytes_range[1]) if bytes_range[1] else file_size - 1

        if start >= file_size:
            return {'error': 'Requested range not satisfiable'}, 416

        # 使用 send_file 时不指定 request_range，而是设置正确的 headers
        response = send_file(
            video_path,
            mimetype='video/mp4',
            conditional=True
        )
        
        # 手动设置范围请求相关的 headers
        response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = str(end - start + 1)
        response.status_code = 206  # Partial Content

        return response
    except Exception as e:
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/save', methods=['POST'])
def save_config():
    """保存配置文件"""
    if not config['config_file']:
        return {'error': 'Config file not specified'}, 404

    try:
        updated_config = request.get_json()
        config_path = os.path.join(config['root_dir'], config['config_file'])
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(updated_config, f, ensure_ascii=False, indent=4)
        return {'status': 'success'}
    except Exception as e:
        return {'error': str(e)}, 500

def run_server(config_file, image_output_path, video_download_path, username):
    """初始化配置并运行服务器"""
    # 获取项目根目录（server.py 所在目录的上一级）
    front_end_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(front_end_dir)
    
    config.update({
        'config_file': config_file,  # 保持相对路径
        'image_output_path': image_output_path,  # 保持相对路径
        'video_download_path': video_download_path,  # 保持相对路径
        'username': username,
        'root_dir': root_dir  # 项目根目录路径
    })
    
    print(f"Front End Server running at http://localhost:8000")
    print(f"Using config file: {os.path.join(root_dir, config_file)}")
    app.run(port=8000)