## 爬虫引擎数据存储说明
#### 数据库
*resultdb*

#### 表名
*resultdb_`项目名`*

#### 表结构
| url | type | param | seed_url | status | updatatime |
|:---:|:----:|:-----:|:--------:|:------:|:----------:|
| 'www.baidu.com/1/' | 'get' | {'data': {'arg1': 'value1'}} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'post' | {'data': {'arg1': 'value1'}} | 'www.baidu.com' | 0 |  datatime |
| 'www.baidu.com/2/' | 'link' | {'data': {}} | 'www.baidu.com' | 0 |  datatime |

#### 字段说明
- *url*：*[ varchar(1024) ]* 爬虫结果url
- *type*：*[ varchar(64) ]* url类型
  - get
  - post
  - link：无参数的链接
- *param*：*[ MEDIUMBLOB ]* url的参数，所有参数以字典存储于data中
- *seed_url*：*[ varchar(1024) ]* url的父级url
- *status*：*[ TINYINT ]* 项目状态
  - 0：未完成
  - 1：已完成
- *updatetime*：*[ double(16, 4) ]* 结果更新时间
