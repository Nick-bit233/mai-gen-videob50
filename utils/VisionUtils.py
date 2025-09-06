import cv2
import numpy as np
import traceback

def find_circle_center(frame):
    """
    使用霍夫圆变换检测视频帧中圆形区域的中心。
    
    Args:
        frame (numpy.ndarray): 从moviepy获取的视频帧 (RGB格式)。
        
    Returns:
        tuple: (x, y) 格式的圆形中心坐标。如果未检测到，则返回None。
    """
    try:
        # Moviepy的帧是RGB格式，OpenCV需要BGR格式，因此需要转换
        img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 使用中值滤波降噪
        gray = cv2.medianBlur(gray, 5)
        # 二值化处理，将非黑色部分转为白色
        # 参数: src, threshold_value, max_value, threshold_type
        _, gray = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

        # debug: 存储预处理后的图像到本地文件
        cv2.imwrite("debug_preprocessed.png", gray)

        # 使用霍夫圆变换检测圆形
        # 参数说明:
        #   - gray: 输入的灰度图像
        #   - cv2.HOUGH_GRADIENT: 检测方法
        #   - dp=1.2: 累加器分辨率与图像分辨率之比
        #   - minDist=gray.shape[0]: 检测到的圆心之间的最小距离，有助于消除假阳性
        #   - param1=100: Canny边缘检测的高阈值
        #   - param2=30: 圆心检测的累加器阈值，值越小，能检测到的圆越多
        #   - minRadius=0, maxRadius=0: 自动计算半径范围
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, 
                                   minDist=gray.shape[0], # 假设屏幕上只有一个主圆形
                                   param1=100, param2=30, 
                                   minRadius=0, maxRadius=0)
        
        if circles is not None:
            # # debug: 显示检测到的圆，并存储到本地图像文件中
            # debug_img = img.copy()
            # circles = np.round(circles[0, :]).astype("int")
            # for (x, y, r) in circles:
            #     cv2.circle(debug_img, (x, y), r, (0, 255, 0), 4)
            #     # 绘制红色的小十字
            #     cv2.line(debug_img, (x - 15, y), (x + 15, y), (0, 0, 255), 2)
            #     cv2.line(debug_img, (x, y - 15), (x, y + 15), (0, 0, 255), 2)
            # cv2.imwrite("debug_detected_circles.png", debug_img)

            # 提取第一个被检测到的圆的中心坐标 (x, y)
            (x, y, r) = circles[0]
            print(f"检测到圆形中心: ({x}, {y}), 半径: {r}")
            return (x, y)
            
    except Exception as e:
        print(f"[Vision] Warning: 自动检测圆形中心失败 - {str(e)}")
        traceback.print_exc()
        
    print("[Vision] Warning: 未能自动检测到圆形中心，将使用默认的几何中心。")
    return None


def draw_center_marker(frame, center_point, crop_box=None):
    """
    在视频帧上绘制中心标记和裁剪框以供调试。

    Args:
        frame (numpy.ndarray): 从moviepy获取的视频帧 (RGB格式)。
        center_point (tuple): (x, y) 格式的中心点坐标。
        crop_box (tuple, optional): (x1, y1, x2, y2) 格式的裁剪框坐标。默认为None。

    Returns:
        numpy.ndarray: 绘制了标记的视频帧 (RGB格式)。
    """
    # 将 moviepy 的 RGB 帧转换为 OpenCV 的 BGR 格式
    img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    # 绘制中心十字准星
    if center_point:
        cx, cy = int(center_point[0]), int(center_point[1])
        # 绘制红色的小十字
        cv2.line(img, (cx - 15, cy), (cx + 15, cy), (0, 0, 255), 2)
        cv2.line(img, (cx, cy - 15), (cx, cy + 15), (0, 0, 255), 2)

    # 绘制裁剪框
    if crop_box:
        x1, y1, x2, y2 = map(int, crop_box)
        # 绘制绿色的矩形框
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # 将处理后的 BGR 图像转换回 RGB 格式以兼容 moviepy 和 PIL
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)