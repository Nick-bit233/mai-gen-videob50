from gene_video import create_video_segment, create_info_segment, create_full_video, combine_full_video_from_existing_clips
import json
import os
import traceback

FONT_PATH = "./font/SOURCEHANSANSSC-BOLD.OTF"

def generate_one_video_clip(config, video_output_path, video_res, video_bitrate, font_path=FONT_PATH):
    print(f"正在合成视频片段: {config['id']}")
    try:
        clip = create_video_segment(config, resolution=video_res, font_path=font_path)
        clip.write_videofile(os.path.join(video_output_path, f"{config['id']}.mp4"), 
                             fps=30, threads=4, preset='ultrafast', bitrate=video_bitrate)
        clip.close()
        return {"status": "success", "info": f"合成视频片段{config['id']}成功"}
    except Exception as e:
        print(f"Error: 合成视频片段{config['id']}时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成视频片段{config['id']}时发生异常: {traceback.print_exc()}"}
    
def generate_complete_video(configs, username,
                            video_output_path, video_res, video_bitrate,
                            video_trans_enable, video_trans_time, full_last_clip,
                            font_path=FONT_PATH):
    print(f"正在合成完整视频")
    try:
        final_video = create_full_video(configs, resolution=video_res, font_path=font_path, 
                                        auto_add_transition=video_trans_enable, 
                                        trans_time=video_trans_time, 
                                        full_last_clip=full_last_clip)
        final_video.write_videofile(os.path.join(video_output_path, f"{username}_B50.mp4"), 
                                    fps=30, threads=4, preset='ultrafast', bitrate=video_bitrate)
        final_video.close()
        return {"status": "success", "info": f"合成完整视频成功"}
    except Exception as e:
        print(f"Error: 合成完整视频时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成完整视频时发生异常: {traceback.print_exc()}"}

@DeprecationWarning
def video_generation_test():
    username = "c1ty"

    video_output_path = "./videos/test"
    if not os.path.exists(video_output_path):
        os.makedirs(video_output_path)

    config_output_file = f"./b50_datas/video_configs_{username}.json"
    if not os.path.exists(config_output_file) or not config_output_file:
        print(f"Error: 没有找到配置文件{config_output_file}，请检查预处理步骤是否完成")

    # 读取配置文件
    with open(config_output_file, "r", encoding="utf-8") as f:
        configs = json.load(f)

    intro_configs = configs['intro']
    main_configs = configs['main'][20:21]
    ending_configs = configs['ending']

    test_resources = {
        'intro': intro_configs,
        'main': main_configs,
        'ending': ending_configs
    }

    for resource in intro_configs:
        clip = create_info_segment(resource, resolution=(1920, 1080), font_path=FONT_PATH)
        # clip.write_videofile(os.path.join(video_output_path, f"{resource['id']}.mp4"), fps=30, codec='h264_nvenc', threads=4, preset='fast', bitrate='5000k')
        clip.show()
    
    # for resource in main_configs:
    #     clip = create_video_segment(resource, resolution=(1920, 1080), font_path=FONT_PATH)
    #     clip.write_videofile(os.path.join(video_output_path, f"{resource['id']}.mp4"), 
    #                          fps=30, threads=4, preset='ultrafast', bitrate='5000k')
    # clip.show()
    
    # for resource in ending_configs:
    #     clip = create_info_segment(resource, resolution=(1920, 1080), font_path=FONT_PATH)
    #     clip.show()

    # generate full video
    # full_video = create_full_video(test_resources, resolution=(1920, 1080), 
    #                                font_path=FONT_PATH, auto_add_transition=True, trans_time=1)
    # full_video.write_videofile(os.path.join(video_output_path, f"{username}_B50.mp4"), 
    #                            fps=30, threads=4, preset='ultrafast', bitrate='5000k')
    # full_video.show()

@DeprecationWarning
def combine_video_test(username):
    print(f"Start: 正在合并{username}的B50视频")
    video_clip_path = f"./videos/{username}"
    video_output_path = f"./videos"
    full_video = combine_full_video_from_existing_clips(video_clip_path, resolution=(1920, 1080), trans_time=1.5)
    full_video.write_videofile(os.path.join(video_output_path, f"{username}_B50.mp4"), fps=30, codec='h264_nvenc', threads=4, preset='fast', bitrate='5000k')

