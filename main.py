import csv
import json
import requests
import re
import time
import traceback
import os
import pymysql  # 替换为MySQL模块
from datetime import datetime  # 添加datetime模块
from playwright.sync_api import sync_playwright


def block_images(route):
    if route.request.resource_type == "image":
        route.abort()  # 取消请求
    else:
        route.continue_()  # 允许其他请求


# 初始化浏览器
def initialize_browser(p):
    browser = p.chromium.launch(
        headless=True,  # 显示浏览器窗口
        # slow_mo=1000,    # 减慢操作速度，单位毫秒
        devtools=True    # 打开开发者工具
    )
    # browser = p.chromium.launch(headless=True,slow_mo=1000,)
    context =  browser.new_context()
    page = context.new_page()
    page.route("**/*", block_images)
    return browser, page


# 导航到目标页面
def navigate_to_target_page(page, url):
    # 导航到页面并等待加载完成
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    time.sleep(5)
    # 等待一房一价按钮可交互
    page.wait_for_selector('a#sp', state='visible')
    # 点击一房一价
    page.click('a#sp')
    # 等待数据加载完成
    page.wait_for_selector('div#content', timeout=30000)


# 处理单个楼层信息
def process_floor(page, navigation_horiz, ul_index):
    try:
        # 重新获取floor_uls
        floor_uls = navigation_horiz.query_selector_all('ul')
        if ul_index >= len(floor_uls):
            print(f"第{ul_index+1}个楼层：索引超出范围，跳过")
            return []

        # 通过索引获取对应的floor_ul
        floor_ul = floor_uls[ul_index]
        if not floor_ul:
            print(f"第{ul_index+1}个楼层：ul元素无效，跳过")
            return []

        # 获取楼层标题
        floor_title_li = floor_ul.query_selector('li:first-child')
        floor_title = floor_title_li.text_content().strip() if floor_title_li else '未知楼层'

        # 获取所有房间li
        room_lis = floor_ul.query_selector_all('li:not(:first-child)')
        rooms_info = []
        for room_li in room_lis:
            # 查找房间链接
            room_a = room_li.query_selector('a.navlink')
            if room_a:
                # 获取房间号
                room_number = room_a.text_content().strip()

                # 查找dropdown元素
                dropdown = room_li.query_selector('div.dropdown')
                if dropdown:
                    # 提取门牌号
                    door_number_p = dropdown.query_selector('p:nth-child(1)')
                    door_number = door_number_p.text_content().replace('门牌号：', '').strip() if door_number_p else room_number

                    # 提取户型
                    type_p = dropdown.query_selector('p:nth-child(2)')
                    room_type = type_p.text_content().replace('户    型: ', '').strip() if type_p else ''

                    # 提取面积
                    area_p = dropdown.query_selector('p:nth-child(3)')
                    room_area = 0
                    if area_p:
                        room_area = area_p.text_content().replace('房屋面积：', '').strip() if area_p else ''
                        room_area = float(room_area.replace('m²', ''))
                    # 提取价格
                    price_p = dropdown.query_selector('p:nth-child(4)')
                    room_price = 0
                    if price_p:
                        price_text = price_p.text_content()
                        if '预售申报价：' in price_text:
                            room_price = price_text.replace('预售申报价：', '').strip()
                            room_price = float(room_price.replace('元/㎡', ''))

                    # 计算总价
                    room_total_price = 0
                    if room_area and room_price:
                        try:
                            area = float(room_area)
                            price = float(room_price)
                            total = area * price
                            room_total_price = f'{total:.2f}'
                        except:
                            pass

                    # 提取状态
                    room_class = room_li.get_attribute('class')
                    room_status = '不可售'
                    if 'kesou' in room_class:
                        room_status = '可售'
                    elif 'yisou' in room_class:
                        room_status = '已售'
                    
                    

                    rooms_info.append({
                        'floor': floor_title,
                        'number': door_number,
                        'type': room_type,
                        'area': room_area,
                        'price': room_price,
                        'total_price': room_total_price,
                        'status': room_status
                    })
                else:
                    rooms_info.append({
                        'floor': floor_title,
                        'number': room_number,
                        'type': '',
                        'area': 0,
                        'price': 0,
                        'total_price': 0,
                        'status': ''
                    })

        return rooms_info
    except Exception as e:
        print(f"处理楼层时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        print(f"错误堆栈:\n{traceback.format_exc()}")
        return []


# 提取房间信息
def extract_rooms_info(page, unit_name):
    rooms_info = []
    try:
        # 等待房间信息加载完成
        page.wait_for_selector('div#navigation_horiz', timeout=5000)

        # 再等待两秒
        time.sleep(2)
        # 提取房间信息
        navigation_horiz = page.query_selector('div#navigation_horiz')
        if navigation_horiz:
            # 第一次获取所有楼层ul，记录数量
            floor_uls = navigation_horiz.query_selector_all('ul')
            ul_count = len(floor_uls)
            print(f"找到 {ul_count} 个楼层ul元素")

            # 使用索引循环，而不是直接遍历元素
            for ul_index in range(ul_count):
                # 每次循环都重新获取navigation_horiz
                navigation_horiz = page.query_selector('div#navigation_horiz')
                if not navigation_horiz:
                    continue

                # 处理楼层
                floor_rooms = process_floor(page, navigation_horiz, ul_index)
                rooms_info.extend(floor_rooms)

    except Exception as e:
        print(f"获取单元 {unit_name} 房间信息失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        print(f"错误堆栈:\n{traceback.format_exc()}")

    return rooms_info


# 提取单元信息
def extract_unit_info(page, building_item):
    units = []
    # 提取单元信息
    sub_menu = building_item.query_selector('ul.sub-menu')
    if sub_menu:
        unit_items = sub_menu.query_selector_all('li a')
        for unit in unit_items:
            unit_name = unit.text_content().strip()
            unit_href = unit.get_attribute('href')
            unit_params = unit_href.split('(')[1].split(')')[0].replace('\'','').split(',') if unit_href and '(' in unit_href and ')' in unit_href else []

            units.append({
                'name': unit_name,
                'params': unit_params,
                'href':unit_href,
            })
    return units


# 提取楼栋信息
def extract_building_info(page):
    building_data = []
    # 定位到楼栋导航菜单
    # 等待 div.navMenubox ul.navMenu 元素加载完成
    page.wait_for_selector('div.navMenubox ul.navMenu', timeout=5000)
    nav_menu = page.query_selector('div.navMenubox ul.navMenu')
    if nav_menu:
        # 获取所有楼栋li元素（只获取直接子节点）
        building_items = nav_menu.query_selector_all('> li')
        print(f"找到{len(building_items)}个楼栋")

        for item in building_items:
            # 提取楼栋基本信息
            a_tag = item.query_selector('a.afinve')
            if a_tag:
                # 获取预售证号
                title = a_tag.get_attribute('title')
                pre_sale_id = title.split('：')[1].strip() if '：' in title else ''

                # 获取楼栋号
                sa_span = a_tag.query_selector('span.sa')
                building_no = sa_span.text_content().strip() if sa_span else ''
            else:
                print("未找到楼栋a标签")
            # 获取单元房间信息
            units = extract_unit_info(page, item)
            # 存储楼栋信息
            building_info = {
                'pre_sale_id': pre_sale_id,
                'building_no': building_no,
                'units': units
            }
            building_data.append(building_info)
    for data in building_data:
        for unit in data['units']:
            unit_name = unit['name']
            unit_href = unit['href']
            # 获取单元房间信息
            print(f"获取{building_no} {unit_name} 的房间信息")
            if unit_href:
                # 执行 JavaScript 代码
                page.evaluate(unit_href)
                # 等待页面加载完成
                page.wait_for_load_state('domcontentloaded', timeout=60000)
            rooms_info = extract_rooms_info(page, unit_name)
            unit['rooms'] = rooms_info
            print(f"获取{building_no} {unit_name} 的房间信息完成")
    return building_data


# 主爬虫函数
def scrape_house_data():
    with sync_playwright() as p:
        # 初始化浏览器
        browser, page = initialize_browser(p)
        # 目标URL
        url = "http://www.360fc.cn/xinfang/xf_index.html?id=3003&mode=0"
        building_data = []

        try:
            # 导航到目标页面
            navigate_to_target_page(page, url)
            # 提取楼栋信息
            print("提取楼栋信息")
            building_data = extract_building_info(page)

        except Exception as e:
            print(f"爬取过程中发生错误: {e}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            print(f"错误堆栈:\n{traceback.format_exc()}")
        finally:
            browser.close()

        return building_data


# 保存数据到CSV
def save_rooms_to_csv(building_data):
    """将房间信息保存到CSV文件

    Args:
        building_data (list): 包含楼栋、单元和房间信息的数据列表

    Returns:
        bool: 保存成功返回True，失败返回False
    """
    if not building_data:
        print("没有数据可保存到CSV文件")
        return False

    csv_file = 'room_details_data.csv'
    headers = ['楼栋号', '预售证号', '单元名称', '楼层', '房间号', '户型', '面积', '单价', '总价', '销售状态']

    try:
        # 确保目录存在
        
        os.makedirs(os.path.dirname(csv_file) or '.', exist_ok=True)

        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            total_rooms = 0
            for building in building_data:
                building_no = building.get('building_no', '未知')
                pre_sale_id = building.get('pre_sale_id', '未知')

                for unit in building.get('units', []):
                    unit_name = unit.get('name', '未知')
                    rooms = unit.get('rooms', [])

                    if rooms:
                        for room in rooms:
                            row_data = [
                                building_no,
                                pre_sale_id,
                                unit_name,
                                room.get('floor', ''),
                                room.get('number', ''),
                                room.get('type', ''),
                                room.get('area', ''),
                                room.get('price', ''),
                                room.get('total_price', ''),
                                room.get('status', '')
                            ]
                            writer.writerow(row_data)
                            total_rooms += 1

            print(f"成功保存{total_rooms}条房间信息到CSV文件: {csv_file}")
            return True
    except Exception as e:
        print(f"保存CSV文件时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        return False


def save_to_database(room_list):
    """将房间信息保存到MySQL数据库，并记录销售日期

    Args:
        room_list (list): 包含房间信息的字典列表

    Returns:
        bool: 保存成功返回True，失败返回False
    """
    if not room_list:
        print("没有数据可保存到数据库")
        return False

    try:
        # 连接到MySQL数据库
        # 请根据实际情况修改MySQL连接参数
        conn = pymysql.connect(
            host='host',  # MySQL服务器地址
            port=3306,
            user='root',       # MySQL用户名
            password='root',  # MySQL密码
            database='zzfc',  # 数据库名
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        # 创建表（如果不存在）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_sales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            building_no VARCHAR(255),
            pre_sale_number VARCHAR(255),
            unit_name VARCHAR(255),
            floor VARCHAR(255),
            room_number VARCHAR(255),
            room_type VARCHAR(255),
            room_area FLOAT,
            room_price FLOAT,
            room_total_price FLOAT,
            status VARCHAR(50),
            sales_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        ''')

        # 查询数据库中已有的房间总数
        cursor.execute("SELECT COUNT(id) AS total FROM room_sales")
        result = cursor.fetchone()
        total = result['total'] if result else 0
        print(f"数据库中已有{total}条房间记录")

        all_room_list = []

        cursor.execute(f"SELECT id, building_no, unit_name, room_number, status FROM room_sales")
        results = cursor.fetchall()
        if results:
            all_room_list.extend(results)

        # 准备插入和更新的数据
        insert_data = []
        update_data = []
        update_with_sales_date = 0

        # 对比新数据和数据库中的数据
        for room in room_list:
            # 查找是否已存在相同的房间
            existing_room = next((r for r in all_room_list if 
                                  r['building_no'] == room.get('building_no', '') and 
                                  r['unit_name'] == room.get('unit_name', '') and 
                                  r['room_number'] == room.get('room_number', '')), None)

            if existing_room:
                # 房间已存在，需要更新
                # 检查状态是否从可售变为已售
                if room.get('status') == '已售' and existing_room['status'] == '可售':
                    # 更新并记录销售日期
                    update_data.append((
                        room.get('pre_sale_number', ''),
                        room.get('floor', ''),
                        room.get('room_type', ''),
                        room.get('room_area', 0),
                        room.get('room_price', 0),
                        room.get('room_total_price', 0),
                        room.get('status', ''),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 销售日期
                        existing_room['id']
                    ))
                    update_with_sales_date += 1
                else:
                    # 普通更新
                    update_data.append((
                        room.get('pre_sale_number', ''),
                        room.get('floor', ''),
                        room.get('room_type', ''),
                        room.get('room_area', 0),
                        room.get('room_price', 0),
                        room.get('room_total_price', 0),
                        room.get('status', ''),
                        None,  # 销售日期为None
                        existing_room['id']
                    ))
            else:
                # 新房间，需要插入
                insert_data.append((
                    room.get('building_no', ''),
                    room.get('pre_sale_number', ''),
                    room.get('unit_name', ''),
                    room.get('floor', ''),
                    room.get('room_number', ''),
                    room.get('room_type', ''),
                    room.get('room_area', 0),
                    room.get('room_price', 0),
                    room.get('room_total_price', 0),
                    room.get('status', ''),
                    None
                ))

        # 批量插入新数据
        if insert_data:
            cursor.executemany('''
            INSERT INTO room_sales (building_no, pre_sale_number, unit_name, floor, room_number, 
                                   room_type, room_area, room_price, room_total_price, status, 
                                   sales_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', insert_data)
            print(f"成功插入{len(insert_data)}条新房间信息")

        # 批量更新已有数据
        if update_data:
            # 区分有销售日期和没有销售日期的更新
            update_with_date = [data for data in update_data if data[-2] is not None]
            update_without_date = [data for data in update_data if data[-2] is None]

            if update_with_date:
                cursor.executemany('''
                UPDATE room_sales SET pre_sale_number=%s, floor=%s, room_type=%s, room_area=%s, 
                                     room_price=%s, room_total_price=%s, status=%s, 
                                     sales_date=%s WHERE id=%s
                ''', update_with_date)
                print(f"成功更新{len(update_with_date)}条房间信息，并记录销售日期")

            if update_without_date:
                cursor.executemany('''
                UPDATE room_sales SET pre_sale_number=%s, floor=%s, room_type=%s, room_area=%s, 
                                     room_price=%s, room_total_price=%s, status=%s 
                                     WHERE id=%s
                ''', [(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[8]) for data in update_without_date])
                print(f"成功更新{len(update_without_date)}条房间信息")

        conn.commit()
        print(f"共更新{update_with_sales_date}条房间的销售日期")
        return True
    except Exception as e:
        if 'conn' in locals() and conn.open:
            conn.rollback()
        print(f"保存数据库时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        print(f"错误堆栈:\n{traceback.format_exc()}")
        return False
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


def building_data_to_db(building_data):
    """将楼栋信息保存到数据库
    Args:
        building_data (list): 包含楼栋、单元和房间信息的数据列表

    Returns:
        bool: 保存成功返回True，失败返回False
    """
    if not building_data:
        print("没有数据可保存到数据库")
        return False
    
    room_list = [];
    for building in building_data:
        building_no = building.get('building_no', '未知')
        pre_sale_id = building.get('pre_sale_id', '未知')
        for unit in building.get('units', []):
            unit_name = unit.get('name', '未知')
            rooms = unit.get('rooms', [])
            if rooms:
                for room in rooms:
                    room_price = float(room.get('price', 0))
                    if room_price> 100000:
                        room_price = room_price * 0.1
                    row_data = {
                        'building_no':building_no,
                        'pre_sale_number':pre_sale_id,
                        'unit_name':unit_name,
                        'floor':room.get('floor', ''),
                        'room_number':room.get('number', ''),
                        'room_type':room.get('type', ''),
                        'room_area':room.get('area', ''),
                        'room_price':room_price,
                        'room_total_price':room.get('total_price', ''),
                        'status':room.get('status', '')
                    }
                    room_list.append(row_data)
    
    # 保存到数据库
    success = save_to_database(room_list)
    if success:
        print("数据成功保存到数据库")
    else:
       print("数据保存到数据库失败")

    # 使用JSON格式输出
    room_json = json.dumps(room_list, ensure_ascii=False, indent=2)
    
    # 将JSON数据保存到文件
    try:
        json_file = 'room_details_data.json'
        os.makedirs(os.path.dirname(json_file) or '.', exist_ok=True)
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(room_json)
        print(f"成功保存房间信息到JSON文件: {json_file}")
    except Exception as e:
        print(f"保存JSON文件时发生错误: {e}")
    # 发送POST请求到API
    # try:
    #     url = "https://zohoexpansion-884845023.development.catalystserverless.com/server/room_sales/"
    #     # url = "http://localhost:3000/server/room_sales/"
    #     headers = {'Content-Type': 'application/json'}
    #     response = requests.post(url, data=room_json.encode('utf-8'), headers=headers)
    #     response.raise_for_status()  # 如果状态码不是200，抛出异常
    #     print(f"数据发送成功，响应状态码: {response.status_code}")
    #     print(f"响应内容: {response.text}")
    # except requests.exceptions.RequestException as e:
    #     print(f"发送数据时出错: {e}")
    
def room_type(building_no,unit_name,room_number):
    # 声明所有户型类型
    a = "101m²"
    b="112m²"
    c="118m²"
    d="119m²"
    e = '132m²'
    f = '133m²'
    g = '144m²'






def test():
    with sync_playwright() as p:
    # 初始化浏览器
        browser, page = initialize_browser(p)
        # 目标URL
        url = "http://www.360fc.cn/xinfang/xf_index.html?id=3003&mode=0"
        try:
            # 导航到目标页面
            navigate_to_target_page(page, url)
            page.evaluate("javascript:getrooms('GX2024016','14','2','1211818983');")
            rooms_info = extract_rooms_info(page, "")
            print(rooms_info)
        except Exception as e:
            print(f"提取数据时出错: {e}")

# 执行爬虫并保存数据
if __name__ == '__main__':
    # test()
    data = scrape_house_data()
    building_data_to_db(data)
    