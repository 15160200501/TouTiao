import requests
from urllib.parse import urlencode
import json
from bs4 import BeautifulSoup
import re
from requests.exceptions import RequestException
import pymongo
import os
from hashlib import md5
from multiprocessing import Pool

MONGO_URL = 'localhost'
MONGO_DB = 'toutiao'
MONGO_TABLE = 'toutiao'

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

headers = {
    'referer': 'https://www.toutiao.com/search/?keyword=%E8%A1%97%E6%8B%8D',
    'cookie': 'tt_webid=6741580036883301901; WEATHER_CITY=%E5%8C%97%E4%BA%AC; __tasessionId=uthwjgcvi1569646429442; tt_webid=6741580036883301901; csrftoken=22882f942604650099034bfe8636766a; s_v_web_id=3fa020c7425a1ebabcf947ef5b12327e',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'
}

def get_page_index(offset):
    params = {
        'aid': '24',
        'app_name': 'web_search',
        'offset': offset,
        'format': 'json',
        'keyword': '街拍',
        'autoload': 'true',
        'count': '20',
        'en_qc': '1',
        'cur_tab': '1',
        'from': 'search_tab',
        'pd': 'synthesis',
    }
    url = 'https://www.toutiao.com/api/search/content/?' + urlencode(params)
    #print(url)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
    except RequestException:
        print('请求索引页失败')
        return None

def parse_page_index(html):
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('share_url')

def get_page_detail(url):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页出错',url)
        return None

def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    title = soup.select('title')[0].get_text()
    #print(title)
    image_pattern = re.compile('gallery: JSON.parse\(\"(.*?)\"\)')
    result = re.search(image_pattern, html)     #查找是否存在image_pattern
    #print(result)
    if result:                                          #如果result存在
        newresult = result.group(1).replace('\\','')    #因为得到的数据中许多地方被插入了\，替换为空格即可得到正确格式
        data = json.loads(newresult)
        #print(data)
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')         #获取键名为sub_images的值
            images = [item.get('url') for item in sub_images]   #以数组形式得到组图中的每张图片的url
            detail_images = list(map(lambda x: re.sub('u002F', '/', x), images))        #请教群里人问的，emmm
            # for detail_image in detail_images:
            for detail_image in detail_images:
                download_image(detail_image)
            return{
                'title': title,
                'url': url,
                'detail_images': detail_images
            }
                # print(detail_image)

def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print("存储到MongoDB成功", result)
        return True
    return False

def download_image(url):
    print('正在下载图片', url)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            save_image(response.content)
            #return response.text
        return None
    except RequestException:
        print('请求图片出错',url)
        return None

def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(),md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset)
    #print(html)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result:
                save_to_mongo(result)
            #print(result)

GROUP_START = 1
GROUP_END = 20

if __name__ == '__main__':
    #main()
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main, groups)
    pool.close()
    pool.join()
