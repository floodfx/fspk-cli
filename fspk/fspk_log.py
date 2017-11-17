import click
import os

class Log(object):

    def __init__(self, debug=False):
        self._debug = debug

    def debug(self, msg):
        if(self._debug):
            click.echo(click.style(msg, fg='blue', bold=False))

    def info(self, msg, bold=False):
        click.echo(click.style(msg, fg='green', bold=bold))

    def error(self, msg, exit=False):
        click.echo(click.style(msg, fg='red', bold=True))
        if(exit):
            self.exit(1)

    def exit(self, status=0):
        os._exit(0)
