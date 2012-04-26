
import yaml
import pytest
import os, sys, time

from copy import deepcopy
from shutil import rmtree
from tempfile import mkdtemp
from functools import partial
from subprocess import call, check_call
from os.path import dirname, abspath, join as pjoin, isdir
from contextlib import contextmanager

from lxml import etree
from pytest import raises, set_trace, mark, fail
from jenkins import Jenkins


here = abspath(dirname(__file__))

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO


def teardown_module_(module, jenkins, repo):
    print('Removing all jobs ...')
    for job in jenkins.getjobs():
        jenkins.py.delete_job(job)

    # print('Stopping Jenkins ...')
    # jenkins.shutdown()
    # jenkins.clean()

    print('Removing temporary repo: %s' % repo.dir)
    repo.clean()

def teardown_function_(f, jenkins):
    if hasattr(f, 'job'):
        print('Removing temporary job: %s' % f.job)
        try: jenkins.delete_job(f.job)
        except: pass


class JenkinsControl(object):
    war=pjoin(here, 'tmp/jenkins.war')
    cli=pjoin(here, 'tmp/jenkins-cli.jar')
    home=pjoin(here, 'tmp/jenkins')

    def __init__(self, addr='127.0.0.1:60888', cport='60887'):
        self.addr, self.port = addr.split(':')
        self.url = 'http://%s' % addr
        self.py = Jenkins(self.url)

    def start_server(self):
        cmd = pjoin(here, './bin/start-jenkins.sh 1>/dev/null 2>&1')
        env={'JENKINS_HOME'  : self.home,
             'JENKINS_PORT'  : self.port,
             'JENKINS_CPORT' : self.cport,
             'JENKINS_ADDR'  : self.addr}
        check_call(cmd, shell=True, env=env)

    def shutdown_server(self):
        cmd = 'echo 0 | nc %s %s' % (self.addr, self.cport)
        check_call(cmd, shell=True)

    def clean_home(self):
        rmtree(self.home)

    def createjob(self, name, configxml_fn):
        self.py.create_job(name, open(configxml_fn).read())

    def getjobs(self):
        return {i['name'] : i for i in self.py.get_jobs()}

    def enabled(self, name):
       return self.py.get_job_info(name)['buildable']

    def job_etree(self, job):
        res = self.py.get_job_config(job)
        res = etree.fromstring(res)
        return res




class TmpRepo(object):
    def __init__(self, d=pjoin(here, 'tmp/repos')):
        if not os.path.exists(d): os.makedirs(d)
        self.dir = mkdtemp(dir=d)
        self.url = 'file://%s' % abspath(self.dir)

    def clean(self):
        rmtree(self.dir)

    def chdir(self):
        os.chdir(self.dir)


class GitRepo(TmpRepo):
    def __init__(self, d=pjoin(here, 'tmp/repos')):
        super(GitRepo, self).__init__()
        self.gitcmd = ['git', '--git-dir=%s/.git' % self.dir]

    def init(self):
        cmd = ('git', 'init', self.dir)
        check_call(cmd)

        cmd = self.gitcmd + ['commit', '--allow-empty', '-m', '++']
        check_call(cmd)

    def mkbranch(self, name, base='master'):
        cmd = self.gitcmd + ['branch', name, base]
        check_call(cmd)

    def rmbranch(self, name):
        cmd = self.gitcmd + ['branch', '-D', name]
        check_call(cmd)

    @contextmanager
    def branch(self, name, base='master'):
        self.mkbranch(name, base)
        yield
        self.rmbranch(name)


class SvnRepo(TmpRepo):
    def __init__(self, d=pjoin(here, 'tmp/repos')):
        super(SvnRepo, self).__init__()

    def init(self):
        cmd = ('svnadmin', 'create', self.dir)
        check_call(cmd)

        cmd = 'svn mkdir {url}/trunk {url}/branches {url}/experimental -m ++'.format(url=self.url)
        check_call(cmd, shell=True)

    def mkbranch(self, name):
        cmd = ('svn', 'cp', '--parents', '%s/trunk/' % self.url,
               '%s/%s' % (self.url, name),
               '-m', '++')
        check_call(cmd)

    def rmbranch(self, name):
        cmd = ('svn', 'rm', '%s/%s' % (self.url, name), '-m', '++')
        check_call(cmd)

    @contextmanager
    def branch(self, name):
        self.mkbranch(name)
        yield
        self.rmbranch(name)
