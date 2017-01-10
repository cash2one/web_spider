#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click, time
from libs.constant import *

__title__ = ""
__author__ = "jx"
__mtime__ = "16-12-7"
__version__ = "0.1"
__prog_name__ = '再来一瓶'

from libs import constant

from libs import utils
import logging, copy
import logging.config
from result.result_worker import ResultWorker
from processor.processor import Processor
from fetcher.tornado_fetcher import Fetcher
from scheduler.scheduler import Scheduler

from database import  connect_database
from message_queue import connect_message_queue
def connect_db(ctx, param, value):
    if not value:
        return
    return utils.Get(lambda: connect_database(value))

def read_config(ctx, param, value):
    if not value:
        return {}

    def underline_dict(d):
        '''把配置文件中的 - 换成 _ '''
        if not isinstance(d, dict):
            return d
        return dict((k.replace("-", "_"), underline_dict(v)) for k, v in d.iteritems())
    import json

    config = underline_dict(json.load(value))
    ctx.obj = utils.ObjectDict(ctx.obj or {})
    ctx.obj['instances'] = []
    ctx.obj.update(config)
    return config

@click.group(invoke_without_command=True)#允许子命令为空
@click.option("-c", "--config", callback=read_config, type=click.File("r"))
@click.option('--logging-config', default=os.path.join(constant.CONF_DIR, "logging.conf"),
              help="logging config file for built-in python logging module", show_default=True)
@click.option('--queue-maxsize', envvar='QUEUE_MAXSIZE', default=100,
              help='maxsize of queue')
@click.option('--taskdb', envvar='TASKDB', callback=connect_db,
              help='database url for taskdb, default: sqlite')
@click.option('--projectdb', envvar='PROJECTDB', callback=connect_db,
              help='database url for projectdb, default: sqlite')
@click.option('--resultdb', envvar='RESULTDB', callback=connect_db,
              help='database url for resultdb, default: sqlite')
@click.option('--message-queue', envvar='AMQP_URL',
              help='connection url to message queue, '
              'default: builtin multiprocessing.Queue')
@click.option('--amqp-url', help='[deprecated] amqp url for rabbitmq. '
              'please use --message-queue instead.')
@click.option('--phantomjs-proxy', envvar='PHANTOMJS_PROXY', help="phantomjs proxy ip:port")
@click.option('--data-path', default=DATA_DIR, help='data dir path')
@click.option('--add-sys-path/--not-add-sys-path', default=True, is_flag=True,
              help='add current working directory to python lib search path')
@click.version_option(version=__version__, prog_name=__prog_name__)
@click.pass_context
def cli(ctx, **kwargs):
    '''根据参数配置运行环境'''


    if not kwargs.get('config'):
        print "usage: webspider.py -c sqlite.conf"
        return

    if not os.path.exists(kwargs['data_path']):
        os.mkdir(kwargs['data_path'])

    #连接数据库
    for db in ('taskdb', 'projectdb', 'resultdb'):
        if kwargs[db] is not None:#优先使用手动配置的参数
            continue
        print ctx.obj[db]
        kwargs[db] = utils.Get(lambda url=ctx.obj[db]: connect_database(url))


    # message queue, compatible with old version
    if kwargs.get('message_queue'):
        pass
    elif kwargs.get('amqp_url'):
        kwargs['message_queue'] = kwargs['amqp_url']
    elif os.environ.get('RABBITMQ_NAME'):
        kwargs['message_queue'] = ("amqp://guest:guest@%(RABBITMQ_PORT_5672_TCP_ADDR)s"
                                   ":%(RABBITMQ_PORT_5672_TCP_PORT)s/%%2F" % os.environ)
    elif kwargs.get('beanstalk'):
        kwargs['message_queue'] = "beanstalk://%s/" % kwargs['beanstalk']

    for name in ('newtask_queue', 'status_queue', 'scheduler2fetcher',
                 'fetcher2processor', 'processor2result'):
        if kwargs.get('message_queue'):
            kwargs[name] = utils.Get(lambda name=name: connect_message_queue(
                name, kwargs.get('message_queue'), kwargs['queue_maxsize']))
        else:
            kwargs[name] = connect_message_queue(name, kwargs.get('message_queue'),
                                                 kwargs['queue_maxsize'])

    kwargs["newtask_queue"]
    # phantomjs-proxy
    if kwargs.get('phantomjs_proxy'):
        pass
    elif os.environ.get('PHANTOMJS_NAME'):
        kwargs['phantomjs_proxy'] = os.environ['PHANTOMJS_PORT_25555_TCP'][len('tcp://'):]



    logging.config.fileConfig(kwargs['logging_config'])

    #保存参数
    ctx.obj = utils.ObjectDict(ctx.obj or {})
    ctx.obj['instances'] = []
    ctx.obj.update(kwargs)
    # 若用户未调用子命令，则启动默认模式
    if ctx.invoked_subcommand == None:
        ctx.invoke(all)

    return ctx

@cli.command()
@click.option('--fetcher-num', default=1, help='instance num of fetcher')
@click.option('--processor-num', default=1, help='instance num of processor')
@click.option('--result-worker-num', default=1,
              help='instance num of result worker')
@click.option('--run-in', default='subprocess', type=click.Choice(['subprocess', 'thread']),
              help='run each components in thread or subprocess. '
              'always using thread for windows.')
@click.pass_context
def all(ctx, fetcher_num, processor_num, result_worker_num, run_in):
    '''运行所有组件'''
    g = ctx.obj

    if run_in == 'subprocess' and os.name != 'nt':
        run_in = utils.run_in_subprocess
    else:
        run_in = utils.run_in_thread

    threads = []

    try:
        #1 启动 phantomjs js渲染代理服务器
        if not g.get('phantomjs_proxy'):
            phantomjs_config = g.get('phantomjs', {})
            phantomjs_config.setdefault('auto_restart', True)
            threads.append(run_in(ctx.invoke, phantomjs, **phantomjs_config))
            time.sleep(2)
            if threads[-1].is_alive() and not g.get('phantomjs_proxy'):
                g['phantomjs_proxy'] = '127.0.0.1:%s' % phantomjs_config.get('port', 25555)
        time.sleep(2)

        #2 启动result worker
        result_worker_config = g.get('result_worker', {})
        for i in range(result_worker_num):
            threads.append(run_in(ctx.invoke, result_worker, **result_worker_config))

        #3 启动processor内容处理模块
        processor_config = g.get('processor', {})
        for i in range(processor_num):
            threads.append(run_in(ctx.invoke, processor, **processor_config))

        #4 启动fetcher抓取模块
        fetcher_config = g.get('fetcher', {})
        fetcher_config.setdefault('xmlrpc_host', '127.0.0.1')
        for i in range(fetcher_num):
            threads.append(run_in(ctx.invoke, fetcher, **fetcher_config))

        #5 启动scheduler调度模块
        scheduler_config = g.get('scheduler', {})
        scheduler_config.setdefault('xmlrpc_host', '127.0.0.1')
        threads.append(run_in(ctx.invoke, scheduler, **scheduler_config))
    finally:
        for each in threads:
            each.join()
        # exit components run in threading
        for each in g.instances:
            each.quit()

        # exit components run in subprocess
        for each in threads:
            if not each.is_alive():
                continue
            if hasattr(each, 'terminate'):
                each.terminate()
            each.join()

@cli.command()
@click.option('--xmlrpc/--no-xmlrpc', default=True)
@click.option('--xmlrpc-host', default='0.0.0.0')
@click.option('--xmlrpc-port', envvar='SCHEDULER_XMLRPC_PORT', default=23333)
@click.option('--inqueue-limit', default=0,
              help='size limit of task queue for each project, '
              'tasks will been ignored when overflow')
@click.option('--delete-time', default=24 * 60 * 60,
              help='delete time before marked as delete')
@click.option('--active-tasks', default=100, help='active log size')
@click.option('--loop-limit', default=1000, help='maximum number of tasks due with in a loop')
@click.option('--threads', default=None, help='thread number for ThreadBaseScheduler, default: 4')
@click.pass_context
def scheduler(ctx, xmlrpc, xmlrpc_host, xmlrpc_port,
              inqueue_limit, delete_time, active_tasks, loop_limit,
              threads, get_object=False):
    """
    Run Scheduler, only one scheduler is allowed.
    """
    g = ctx.obj

    kwargs = dict(taskdb=g.taskdb, projectdb=g.projectdb, resultdb=g.resultdb,
                  newtask_queue=g.newtask_queue, status_queue=g.status_queue,
                  out_queue=g.scheduler2fetcher, data_path=g.get('data_path', 'data'))
    if threads:
        kwargs['threads'] = int(threads)

    scheduler = Scheduler(**kwargs)
    scheduler.INQUEUE_LIMIT = inqueue_limit
    scheduler.DELETE_TIME = delete_time
    scheduler.ACTIVE_TASKS = active_tasks
    scheduler.LOOP_LIMIT = loop_limit

    g.instances.append(scheduler)
    if g.get('testing_mode') or get_object:
        return scheduler

    if xmlrpc:
        #对外接口
        utils.run_in_thread(scheduler.xmlrpc_run, port=xmlrpc_port, bind=xmlrpc_host)
    #功能执行
    scheduler.run()

@cli.command()
@click.option('--xmlrpc/--no-xmlrpc', default=False)
@click.option('--xmlrpc-host', default='0.0.0.0')
@click.option('--xmlrpc-port', envvar='FETCHER_XMLRPC_PORT', default=24444)
@click.option('--poolsize', default=100, help="max simultaneous fetches")
@click.option('--proxy', help="proxy host:port")
@click.option('--user-agent', help='user agent')
@click.option('--timeout', help='default fetch timeout')
@click.option('--phantomjs-endpoint', help="endpoint of phantomjs, start via pyspider phantomjs")
@click.option('--splash-endpoint', help="execute endpoint of splash: http://splash.readthedocs.io/en/stable/api.html#execute")
@click.pass_context
def fetcher(ctx, xmlrpc, xmlrpc_host, xmlrpc_port, poolsize, proxy, user_agent,
            timeout, phantomjs_endpoint, splash_endpoint,
            async=True, get_object=False, no_input=False):
    """
    Run Fetcher.
    """
    g = ctx.obj

    if no_input:
        inqueue = None
        outqueue = None
    else:
        inqueue = g.scheduler2fetcher
        outqueue = g.fetcher2processor
    fetcher = Fetcher(inqueue=inqueue, outqueue=outqueue,
                      poolsize=poolsize, proxy=proxy, async=async)
    fetcher.phantomjs_proxy = phantomjs_endpoint or g.phantomjs_proxy
    fetcher.splash_endpoint = splash_endpoint
    if user_agent:
        fetcher.user_agent = user_agent
    if timeout:
        fetcher.default_options = copy.deepcopy(fetcher.default_options)
        fetcher.default_options['timeout'] = timeout

    g.instances.append(fetcher)
    if g.get('testing_mode') or get_object:
        return fetcher

    if xmlrpc:
        utils.run_in_thread(fetcher.xmlrpc_run, port=xmlrpc_port, bind=xmlrpc_host)
    fetcher.run()

@cli.command()
@click.option('--process-time-limit', default=30, help='script process time limit')
@click.pass_context
def processor(ctx,  process_time_limit, enable_stdout_capture=True, get_object=False):
    """
    Run Processor.
    """
    g = ctx.obj

    processor = Processor(projectdb=g.projectdb,
                          inqueue=g.fetcher2processor, status_queue=g.status_queue,
                          newtask_queue=g.newtask_queue, result_queue=g.processor2result,
                          enable_stdout_capture=enable_stdout_capture,
                          process_time_limit=process_time_limit)

    g.instances.append(processor)
    if g.get('testing_mode') or get_object:
        return processor

    processor.run()

@cli.command()
@click.pass_context
def result_worker(ctx, get_object=False):
    """
    子线程运行结果处理模块.默认存入数据库
    """
    g = ctx.obj
    result_worker = ResultWorker(resultdb=g.resultdb, inqueue=g.processor2result)

    g.instances.append(result_worker)
    if g.get('testing_mode') or get_object:
        return result_worker

    result_worker.run()
@cli.command()
@click.option('--phantomjs-path', default='phantomjs', help='phantomjs path')
@click.option('--port', default=25555, help='phantomjs port')
@click.option('--auto-restart', default=False, help='auto restart phantomjs if crashed')
@click.argument('args', nargs=-1)
@click.pass_context
def phantomjs(ctx, phantomjs_path, port, auto_restart, args):
    """
    运行phantomjs
    """
    args = args or ctx.default_map and ctx.default_map.get('args', [])

    import subprocess
    g = ctx.obj
    _quit = []
    phantomjs_fetcher = os.path.join(

        os.path.dirname(__file__), 'fetcher/phantomjs/phantomjs_server.js')#'fetcher/phantomjs/phantomjs_server.js'
    cmd = [phantomjs_path,
           # this may cause memory leak: https://github.com/ariya/phantomjs/issues/12903
           #'--load-images=false',
           #'--remote-debugger-port=9000',

           '--ssl-protocol=any',
           '--disk-cache=true'] + list(args or []) + [phantomjs_fetcher, str(port)]

    try:
        _phantomjs = subprocess.Popen(cmd)
    except OSError:
        logging.warning('phantomjs not found, continue running without it.')
        return None

    def quit(*args, **kwargs):
        _quit.append(1)
        _phantomjs.kill()
        _phantomjs.wait()
        logging.info('phantomjs exited.')

    if not g.get('phantomjs_proxy'):
        g['phantomjs_proxy'] = '127.0.0.1:%s' % port

    phantomjs = utils.ObjectDict(port=port, quit=quit)
    g.instances.append(phantomjs)
    if g.get('testing_mode'):
        return phantomjs

    while True:
        _phantomjs.wait()
        if _quit or not auto_restart:
            break
        _phantomjs = subprocess.Popen(cmd)



def main():
    cli()

if __name__ == "__main__":

    main()

