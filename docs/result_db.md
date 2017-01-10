####爬虫引擎数据存储说明
----

**表名**
resultdb_项目名

**表结构**
| url | type | param | seed_url | status | updatatime |
|:---:|:----:|:-----:|:--------:|:------:|:----------:|
| 'www.baidu.com/1/' | 'get' | {'data': 'data'} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'post' | {'data': 'data'} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'link' | {'data': ' '} | 'www.baidu.com' | 0 |  datatime |

**字段说明**
- **url**：爬虫结果url
- **type**：url类型
	- get
	- post
	- link：无参数的链接
- **param**：url的参数，所有参数以string存在data中
- **seed_url**：url的父级url
- **status**：项目状态
	- 0：未完成
	- 1：已完成
- **updatetime**：结果更新时间