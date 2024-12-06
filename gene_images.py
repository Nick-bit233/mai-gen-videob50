import os
import json
from PIL import Image, ImageDraw, ImageFont
from utils.Utils import Utils
from copy import deepcopy


def generate_single_image(background_path, record_detail, user_id, prefix, index):
    function = Utils()
    with Image.open(background_path) as background:
        # 生成并调整单个成绩图片
        single_image = function.GenerateOneAchievement(record_detail)
        new_size = (int(single_image.width * 0.55), int(single_image.height * 0.55))
        single_image = single_image.resize(new_size, Image.LANCZOS)
        
        # 粘贴图片
        background.paste(single_image, (940, 170), single_image.convert("RGBA"))
        
        # 添加文字
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("./font/FOT_NewRodin_Pro_EB.otf", 50)
        draw.text((940, 100), f"{prefix} {index + 1}", fill=(255, 255, 255), font=font)
        
        # 保存图片
        background.save(f"./b50_images/{user_id}/{prefix}_{index + 1}.png")

def generate_b50_images(UserID, b35_data, b15_data, output_dir):
    print("生成B50图片中...")
    os.makedirs(output_dir, exist_ok=True)

    def _check_mask_waring(acc_string, cnt, warned=False):
        if len(acc_string.split('.')[1]) >= 4 and acc_string.split('.')[1][-3:] == "000":
            cnt = cnt + 1
            if cnt > 5 and not warned:
                print(f"Warning： 检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
                warned = True
        return cnt, warned

    def _gene_images_batch(data, user_id, prefix):
        mask_check_cnt = 0
        mask_warn = False
        for index, record_detail in enumerate(data):
            acc_string = f"{record_detail['achievements']:.4f}"
            mask_check_cnt, mask_warn = _check_mask_waring(acc_string, mask_check_cnt, mask_warn)
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            generate_single_image(
                "./images/B50ViedoBase.png",
                record_for_gene_image,
                user_id,
                prefix,
                index,
            )

    # 生成历史最佳图片
    _gene_images_batch(b35_data, UserID, "PastBest")
    
    # 生成最新最佳图片
    _gene_images_batch(b15_data, UserID, "NewBest")

    print(f"已生成 {UserID} 的 B50 图片，请在 b50_images/{UserID} 文件夹中查看。")


