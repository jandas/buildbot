# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.python import log
from twisted.internet import defer

from buildbot.process.buildstep import LoggedRemoteCommand, RemoteShellCommand
from buildbot.steps.source import Source
from buildbot.status.results import FAILURE

class Mercurial(Source):
    """ Class for Mercurial with all the smarts """
    name = "hg"

    def __init__(self, repourl=None, baseurl=None, mode='incremental',defaultBranch=None,
                 branchType='inrepo', clobberOnBranchChange=True, **kwargs):

        """
        @type  repourl: string
        @param repourl: the URL which points at the Mercurial repository.
                        This uses the 'default' branch unless defaultBranch is
                        specified below and the C{branchType} is set to
                        'inrepo'.  It is an error to specify a branch without
                        setting the C{branchType} to 'inrepo'.

        @param baseurl: if 'dirname' branches are enabled, this is the base URL
                        to which a branch name will be appended. It should
                        probably end in a slash.  Use exactly one of C{repourl}
                        and C{baseurl}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly.
                              For 'dirname' branches, It will simply be
                              appended to C{baseurl} and the result handed to
                              the 'hg update' command.
                              For 'inrepo' branches, this specifies the named
                              revision to which the tree will update after a
                              clone.

        @param branchType: either 'dirname' or 'inrepo' depending on whether
                           the branch name should be appended to the C{baseurl}
                           or the branch is a mercurial named branch and can be
                           found within the C{repourl}

        @param clobberOnBranchChange: boolean, defaults to True. If set and
                                      using inrepos branches, clobber the tree
                                      at each branch change. Otherwise, just
                                      update to the branch.
        """
        
        self.repourl = repourl
        self.baseurl = baseurl
        self.branch = defaultBranch
        self.branchType = branchType
        self.clobberOnBranchChange = clobberOnBranchChange
        Source.__init__(self, **kwargs)
        self.mode = mode
        self.addFactoryArguments(repourl=repourl,
                                 baseurl=baseurl,
                                 mode=mode,
                                 defaultBranch=defaultBranch,
                                 branchType=branchType,
                                 )

        if repourl and baseurl:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseurl")

    def startVC(self, branch, revision, patch):

        slavever = self.slaveVersion('hg')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about hg")

        if branch:
            assert self.branchType == 'dirname' and not self.repourl
            # The restriction is we can't configure named branch here.
            # that's why 'not self.repourl'.
            self.repourl = self.computeRepositoryURL(self.baseurl) + (branch or '')
            self.branch = branch
        else:
            assert self.branchType == 'inrepo' and not self.baseurl
            self.repourl = self.computeRepositoryURL(self.repourl)
            
        assert self.mode in ['incremental', 'clobber', 'fresh', 'clean']
        self.stdio_log = self.addLog("stdio")

        if self.mode == 'incremental':
            d = self.incremental()
        elif self.mode == 'clobber':
            d = self.doClobber()
        elif self.mode == 'fresh':
            d = self.fresh()
        elif self.mode == 'clean':
            d = self.clean()

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        return d

    def _dovccmd(self, command):
        cmd = RemoteShellCommand(self.workdir, ['hg', '--verbose'] + command)
        cmd.useLog(self.stdio_log, False)
        log.msg("Mercurial command : %s" % ("hg ".join(command), ))
        d = self.runCommand(cmd)
        d.addCallback(lambda _: self.evaluateCommand(cmd)) 
        d.addErrback(self.failed)
        return d

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            log.msg("Closing log, sending result of the command %s " % (self.cmd))
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        d.addErrback(self.failed)
        return d
        
    def _sourcedirIsUpdatable(self):
        cmd = LoggedRemoteCommand('stat', {'file': self.workdir + '/.hg'})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _fail(tmp):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(_fail)
        return d

    def doVCUpdate(self, _):
        d = self._sourcedirIsUpdatable()
        def cmd(updatable):
            if updatable:
                command = ['pull', '--update' , self.repourl]
            else:
                command = ["clone", self.repourl, "."]

            if self.branch:
                command += ['--branch', self.branch]
            return command

        d.addCallback(cmd)
        d.addCallback(self._dovccmd)
        return d

    def doClobber(self):
        cmd = LoggedRemoteCommand('rmdir', {'dir': self.workdir})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        d.addCallback(lambda _: self._dovccmd(["clone", self.repourl, "."]))
        return d

    def parseGotRevision(self, _):
        d = self._dovccmd(['identify', '--id', '--debug'])
        def _setrev(res):
            revision = self.getLog('stdio').readlines()[-1].strip()
            if len(revision) != 40:
                return FAILURE
            log.msg("Got Mercurial revision %s" % (revision, ))
            self.setProperty('got_revision', revision, 'Source')
            return res
        d.addCallback(_setrev)
        return d

    def _getCurrentBranch(self):
        d = self._dovccmd(['identify', '--branch'])
        def _getbranch(_):
            branch = self.getLog('stdio').readlines()[-1].strip()
            log.msg("Current branch is %s" % (branch, ))
            return branch
        d.addCallback(_getbranch)
        return d

    def incremental(self):
        clobber = False
        d = self._getCurrentBranch()
        def _compare(current_branch):
            if current_branch != self.branch:
                msg = "Working dir is on in-repo branch '%s' and build needs '%s'." % \
                    (current_branch, self.branch)
                if self.clobberOnBranchChange:
                    msg += ' Cloberring.'
                    clobber = True
                else:
                    msg += ' Updating.'
                log.msg(msg)

        d.addCallback(_compare)

        # Fix me
        if clobber:
            d.addCallback(self.doClobber)
        else:
            d.addCallback(self.doVCUpdate)
        
        return d

    def clean(self):
        command = ['--config', 'extensions.purge=', 'purge']
        d =  self._dovccmd(command)
        d.addCallback(self._checkPurge)
        return d

    def fresh(self):
        command = ['--config', 'extensions.purge=', 'purge', '--all']
        d = self._dovccmd(command)
        d.addCallback(self._checkPurge)
        return d
    
    def _checkPurge(self, res):
        if res != 0:
            log.msg("'hg purge' failed. Clobbering.")
            # fallback to clobber
            return self.doClobber(res)

        return  self._dovccmd(['pull', '--update', self.repourl])
