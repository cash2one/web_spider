## 爬虫引擎数据存储说明
#### 数据库
*resultdb*

#### 表名
*resultdb_`项目名`*

#### 表结构
| url | type | param | seed_url | status | updatatime |
|:---:|:----:|:-----:|:--------:|:------:|:----------:|
| 'www.baidu.com/1/' | 'get' | {'data': 'string'} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'post' | {'data': 'string'} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'link' | {'data': ' '} | 'www.baidu.com' | 0 |  datatime |

#### 字段说明
- *url*：爬虫结果url
- *type*：url类型
  - get
  - post
  - link：无参数的链接
- *param*：url的参数，所有参数以string存储于data中
- *seed_url*：url的父级url
- *status*：项目状态
  - 0：未完成
  - 1：已完成
- *updatetime*：结果更新时间
