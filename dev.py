from lxml import etree

# 假设 raw_html 是包含 HTML 的字符串
raw_html = '''
<tr>
    <td class="line-number" value="168"></td>
    <td class="line-content">
        <span class="html-tag">&lt;div <span class="html-attribute-name">class</span>="<span class="html-attribute-value">music_master_score_back pointer w_450 m_15 p_3 f_0</span>"&gt;</span>
    </td>
</tr>
<tr>
    <td class="line-number" value="169"></td>
    <td class="line-content">
        <span class="html-tag">&lt;img <span class="html-attribute-name">src</span>="<a class="html-attribute-value html-resource-link" href="https://maimaidx-eng.com/maimai-mobile/img/diff_master.png">https://maimaidx-eng.com/maimai-mobile/img/diff_master.png</a>" /&gt;</span>
    </td>
</tr>
<tr>
    <td class="line-number" value="170"></td>
    <td class="line-content">
        <span class="html-tag">&lt;div <span class="html-attribute-name">class</span>="<span class="html-attribute-value">music_lv_block f_r t_c f_14</span>"&gt;</span>13+<span class="html-tag">&lt;/div&gt;</span>
    </td>
</tr>
<tr>
    <td class="line-number" value="171"></td>
    <td class="line-content">
        <span class="html-tag">&lt;div <span class="html-attribute-name">class</span>="<span class="html-attribute-value">music_name_block t_l f_13 break</span>"&gt;</span>バカ通信<span class="html-tag">&lt;/div&gt;</span>
    </td>
</tr>
<tr>
    <td class="line-number" value="172"></td>
    <td class="line-content">
        <span class="html-tag">&lt;div <span class="html-attribute-name">class</span>="<span class="html-attribute-value">music_score_block w_120 t_r f_r f_12</span>"&gt;</span>100.6286%<span class="html-tag">&lt;/div&gt;</span>
    </td>
</tr>
'''

with open('./raw.html', 'r', encoding="utf-8") as f:
    raw_html = f.read()

# 解析 HTML
parser = etree.HTMLParser()
tree = etree.fromstring(raw_html, parser)

# 提取所有包含内容的 <td class="line-content">
line_contents = tree.xpath('//td[@class="line-content"]')

# 定义结果列表
results = []

# 用于存储当前数据单元的 HTML 片段
current_unit = []

# 遍历内容
for td in line_contents:
    # 提取 <td> 内的文本内容
    text_content = ''.join(td.xpath('.//text()')).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

    # 判断是否是数据单元起始标志
    if 'music_' in text_content and '_score_back' in text_content:
        if current_unit:  # 如果已有未处理的单元，先处理它
            # 解析当前单元
            unit_tree = etree.HTML(''.join(current_unit))
            result = {}

            # 提取 diff 信息
            diff_img = unit_tree.xpath(".//img[contains(@src, 'diff_')]/@src")
            if diff_img:
                result['diff'] = diff_img[0].split('_')[-1].split('.')[0]

            # 提取 music 类型
            music_img = unit_tree.xpath(".//img[contains(@src, 'music_')]/@src")
            if music_img:
                result['music_type'] = music_img[0].split('_')[-1].split('.')[0]

            # 提取等级
            lv_block = unit_tree.xpath(".//div[contains(@class, 'music_lv_block')]/text()")
            if lv_block:
                result['level'] = lv_block[0].strip()

            # 提取音乐名称
            name_block = unit_tree.xpath(".//div[contains(@class, 'music_name_block')]/text()")
            if name_block:
                result['name'] = name_block[0].strip()

            # 提取得分
            score_block = unit_tree.xpath(".//div[contains(@class, 'music_score_block')]/text()")
            if score_block:
                result['score'] = score_block[0].strip()

            # 保存结果
            results.append(result)

        # 开始新的单元
        current_unit = [text_content]
    else:
        # 向当前单元追加内容
        current_unit.append(text_content)

# 处理最后一个单元
if current_unit:
    unit_tree = etree.HTML(''.join(current_unit))
    result = {}
    diff_img = unit_tree.xpath(".//img[contains(@src, 'diff_')]/@src")
    if diff_img:
        result['diff'] = diff_img[0].split('_')[-1].split('.')[0]
    music_img = unit_tree.xpath(".//img[contains(@src, 'music_')]/@src")
    if music_img:
        result['music_type'] = music_img[0].split('_')[-1].split('.')[0]
    lv_block = unit_tree.xpath(".//div[contains(@class, 'music_lv_block')]/text()")
    if lv_block:
        result['level'] = lv_block[0].strip()
    name_block = unit_tree.xpath(".//div[contains(@class, 'music_name_block')]/text()")
    if name_block:
        result['name'] = name_block[0].strip()
    score_block = unit_tree.xpath(".//div[contains(@class, 'music_score_block')]/text()")
    if score_block:
        result['score'] = score_block[0].strip()
    results.append(result)

# 输出结果
i = 0
for r in results:
    i += 1
    print(i, r)
