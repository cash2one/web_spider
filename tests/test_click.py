#coding:utf8
import click


@click.group()
@click.pass_context
def cli(ctx, **kwargs):
   print "cli"
   return ctx

#子命令，用法：dtest_click.py  subcmd --name=dt
@cli.command()
@click.option("--name", default="jx")
@click.pass_context
def subcmd(ctx, name):
   print "subcmd",name
if __name__ == '__main__':
    cli()
   