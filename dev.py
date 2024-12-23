from lxml import etree
import json
from utils.dxnet_extension import ChartManager
from pre_gen_int import iterate_songs, parse_html_to_json

with open('./raw.html', 'r', encoding="utf-8") as f:
    raw_html = f.read()

# 第一步：解析初始 HTML
tree = etree.fromstring(raw_html, etree.HTMLParser())

# 第二步：提取所有 <td class="line-content"> 的内容并修复 HTML
line_contents = tree.xpath('//td[@class="line-content"]')
html_snippets = []

for td in line_contents:
    # 提取伪 HTML 并修复 HTML 实体
    text_content = ''.join(td.xpath('.//text()')).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    html_snippets.append(text_content)

# 第三步：拼接所有内容为一个完整的 HTML 字符串
full_html = ''.join(html_snippets)

def read(b50_raw, username):
    html_tree = etree.HTML(b50_raw)
    # Locate B35 and B15
    b35_screw = html_tree.xpath('//div[text()="Songs for Rating(Others)"]')
    b15_screw = html_tree.xpath('//div[text()="Songs for Rating(New)"]')
    if not b35_screw:
        raise Exception(f"Error: B35 not found.")
    if not b15_screw:
        raise Exception(f"Error: B15 not found.")

    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
        "username": username
    }
    manager = ChartManager()
    song_id_placeholder = 0 # Avoid same file names for downloaded videos
    for song in iterate_songs(html_tree, b35_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["sd"].append(song_json)
    for song in iterate_songs(html_tree, b15_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["dx"].append(song_json)

    # Write b50 JSON to raw file
    with open("./b50_datas/test.json", 'w', encoding="utf-8") as f:
        json.dump(b50_json, f, ensure_ascii = False, indent = 4)
    return b50_json


# 第四步：解析拼接后的 HTML 字符串
read(full_html, "tester")

# # 提取所有包含内容的 <td class="line-content">
# line_contents = tree.xpath('//td[@class="line-content"]')
# # 遍历内容
# for td in line_contents:
#     # 提取 <td> 内的文本内容
#     text_content = ''.join(td.xpath('.//text()')).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
#     print(text_content)

#     # 判断是否是数据单元起始标志
#     if 'music_' in text_content and '_score_back' in text_content:
#         if current_unit:  # 如果已有未处理的单元，先处理它
#             # 解析当前单元
#             unit_tree = etree.HTML(''.join(current_unit))
#             result = {}

#             # 提取 diff 信息
#             diff_img = unit_tree.xpath(".//img[contains(@src, 'diff_')]/@src")
#             if diff_img:
#                 result['diff'] = diff_img[0].split('_')[-1].split('.')[0]

#             # 提取 music 类型
#             music_img = unit_tree.xpath(".//img[contains(@src, 'music_')]/@src")
#             if music_img:
#                 result['music_type'] = music_img[0].split('_')[-1].split('.')[0]

#             # 提取等级
#             lv_block = unit_tree.xpath(".//div[contains(@class, 'music_lv_block')]/text()")
#             if lv_block:
#                 result['level'] = lv_block[0].strip()

#             # 提取音乐名称
#             name_block = unit_tree.xpath(".//div[contains(@class, 'music_name_block')]/text()")
#             if name_block:
#                 result['name'] = name_block[0].strip()

#             # 提取得分
#             score_block = unit_tree.xpath(".//div[contains(@class, 'music_score_block')]/text()")
#             if score_block:
#                 result['score'] = score_block[0].strip()

#             # 保存结果
#             results.append(result)

#         # 开始新的单元
#         current_unit = [text_content]
#     else:
#         # 向当前单元追加内容
#         current_unit.append(text_content)

# # 处理最后一个单元
# if current_unit:
#     unit_tree = etree.HTML(''.join(current_unit))
#     result = {}
#     diff_img = unit_tree.xpath(".//img[contains(@src, 'diff_')]/@src")
#     if diff_img:
#         result['diff'] = diff_img[0].split('_')[-1].split('.')[0]
#     music_img = unit_tree.xpath(".//img[contains(@src, 'music_')]/@src")
#     if music_img:
#         result['music_type'] = music_img[0].split('_')[-1].split('.')[0]
#     lv_block = unit_tree.xpath(".//div[contains(@class, 'music_lv_block')]/text()")
#     if lv_block:
#         result['level'] = lv_block[0].strip()
#     name_block = unit_tree.xpath(".//div[contains(@class, 'music_name_block')]/text()")
#     if name_block:
#         result['name'] = name_block[0].strip()
#     score_block = unit_tree.xpath(".//div[contains(@class, 'music_score_block')]/text()")
#     if score_block:
#         result['score'] = score_block[0].strip()
#     results.append(result)

# # 输出结果
# i = 0
# for r in results:
#     i += 1
#     print(i, r)
