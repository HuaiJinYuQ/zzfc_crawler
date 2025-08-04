# 郑轨云麓销售数据爬取与分析项目

## 项目简介
使用playwright 爬取 http://www.360fc.cn的销售数据.
代码中爬取郑轨云麓的销售数据 可以修改代码中url来实现爬取不同楼盘的数据
url = "http://www.360fc.cn/xinfang/xf_index.html?id=3003&mode=0"

1. 克隆项目到本地
2. 进入项目目录: `cd /Users/xxx/project/python_project/zzfc`
3. 创建虚拟环境: `python -m venv venv`
4. 激活虚拟环境:
   - macOS/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
5. 安装依赖库: `pip install playwright`
